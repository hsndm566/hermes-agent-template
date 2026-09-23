import hashlib
import hmac
import httpx
from .config import settings


class EvolutionClient:
    def __init__(self):
        self.base = settings.evolution_internal_url.rstrip("/")
        self.provider = (settings.evolution_provider or "api").lower()

    @property
    def is_go(self):
        return self.provider == "go"

    def instance_token(self, instance: str) -> str:
        # Stable per-instance secret without storing another credential in the DB.
        return hmac.new(
            settings.session_secret.encode(),
            ("evolution-go:" + instance).encode(),
            hashlib.sha256,
        ).hexdigest()

    def headers(self, instance: str | None = None):
        key = self.instance_token(instance) if self.is_go and instance else settings.evolution_api_key
        return {"apikey": key, "Content-Type": "application/json"}

    async def _request(self, method: str, path: str, *, json=None, timeout=30, instance: str | None = None):
        async with httpx.AsyncClient(timeout=timeout, trust_env=False) as c:
            r = await c.request(method, f"{self.base}{path}", headers=self.headers(instance), json=json)
            r.raise_for_status()
            return r.json() if r.content else {}

    async def configure_webhook(self, instance: str):
        if self.is_go:
            # Evolution Go configures the webhook when the instance connects.
            # The URL is loopback-only in Maw3idi, so the public webhook secret
            # is not exposed to Evolution Go.
            return await self._request(
                "POST",
                "/instance/connect",
                instance=instance,
                json={
                    "webhookUrl": settings.evolution_webhook_url,
                    "subscribe": ["MESSAGE", "CONNECTION", "QRCODE"],
                    "immediate": True,
                },
            )
        payload = {
            "webhook": {
                "enabled": True,
                "url": settings.evolution_webhook_url,
                "headers": {"X-Webhook-Secret": settings.whatsapp_webhook_secret},
                "byEvents": False,
                "base64": False,
                "events": ["MESSAGES_UPSERT", "CONNECTION_UPDATE", "QRCODE_UPDATED"],
            }
        }
        return await self._request("POST", f"/webhook/set/{instance}", json=payload)

    async def find_webhook(self, instance: str):
        if self.is_go:
            return {"enabled": True, "provider": "go"}
        return await self._request("GET", f"/webhook/find/{instance}", timeout=15)

    async def create_instance(self, instance: str):
        if self.is_go:
            data = await self._request(
                "POST",
                "/instance/create",
                json={"name": instance, "token": self.instance_token(instance)},
            )
            await self.configure_webhook(instance)
            return data

        payload = {
            "instanceName": instance,
            "qrcode": True,
            "integration": "WHATSAPP-BAILEYS",
            "groupsIgnore": True,
            "alwaysOnline": False,
            "readMessages": False,
            "syncFullHistory": False,
        }
        data = await self._request("POST", "/instance/create", json=payload)
        await self.configure_webhook(instance)
        hook = await self.find_webhook(instance)
        hook_data = hook.get("webhook", hook) if isinstance(hook, dict) else {}
        if isinstance(hook_data, dict):
            nested = hook_data.get("webhook", hook_data)
            if isinstance(nested, dict) and nested.get("enabled") is False:
                raise RuntimeError("Evolution webhook was created but is disabled")
        return data

    async def connect(self, instance: str):
        if self.is_go:
            data = await self._request("GET", "/instance/qr", instance=instance)
            # Keep the dashboard contract stable: expose base64 QR as qrcode.base64.
            body = data.get("data", data) if isinstance(data, dict) else {}
            raw = body.get("code") or body.get("qrcode")
            if isinstance(raw, str) and raw.startswith("data:image"):
                base64_qr = raw
            elif isinstance(raw, str) and len(raw) > 200:
                base64_qr = "data:image/png;base64," + raw
            else:
                base64_qr = None
            out = {"qrcode": {"base64": base64_qr}, "raw": data}
            # Preserve passkey ceremony metadata for the UI/diagnostics.
            for key in ("passkeyStage", "passkeyOpenUrl", "passkey_stage", "passkey_open_url"):
                if key in body:
                    out[key] = body[key]
            return out
        return await self._request("GET", f"/instance/connect/{instance}")

    async def state(self, instance: str):
        if self.is_go:
            data = await self._request("GET", "/instance/status", timeout=15, instance=instance)
            body = data.get("data", data) if isinstance(data, dict) else {}
            logged = bool(body.get("loggedIn") or body.get("logged_in"))
            connected = bool(body.get("connected"))
            raw_state = body.get("status") or ("open" if logged and connected else "connecting" if connected else "close")
            return {"instance": {"instanceName": instance, "state": raw_state}, "raw": data}
        return await self._request("GET", f"/instance/connectionState/{instance}", timeout=15)

    async def delete_instance(self, instance: str):
        if self.is_go:
            # Instance deletion in Go is administrative and ID-based. Logout is
            # enough for Maw3idi's reconnect flow; deletion can be added after
            # resolving the instance UUID from /instance/all.
            return await self.logout(instance)
        return await self._request("DELETE", f"/instance/delete/{instance}", timeout=20)

    async def logout(self, instance: str):
        if self.is_go:
            return await self._request("DELETE", "/instance/logout", timeout=20, instance=instance, json={})
        return await self._request("DELETE", f"/instance/logout/{instance}", timeout=20)

    async def send_text(self, instance: str, number: str, text: str):
        if instance.startswith("test-biz-"):
            return {"test": True, "text": text}
        if self.is_go:
            return await self._request(
                "POST",
                "/send/text",
                instance=instance,
                json={"number": number, "text": text},
            )
        return await self._request(
            "POST",
            f"/message/sendText/{instance}",
            json={"number": number, "text": text, "delay": 300, "linkPreview": True},
        )


evolution = EvolutionClient()
