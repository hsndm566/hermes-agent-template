import httpx
from .config import settings


class EvolutionClient:
    def __init__(self):
        self.base = settings.evolution_internal_url.rstrip('/')
        self.headers = {"apikey": settings.evolution_api_key, "Content-Type": "application/json"}

    async def _request(self, method: str, path: str, *, json=None, timeout=30):
        async with httpx.AsyncClient(timeout=timeout) as c:
            r = await c.request(method, f"{self.base}{path}", headers=self.headers, json=json)
            r.raise_for_status()
            return r.json() if r.content else {}

    async def configure_webhook(self, instance: str):
        # Evolution API v2.3.x requires webhook settings inside a "webhook"
        # object and uses "byEvents" / "base64" field names.
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
        return await self._request("GET", f"/webhook/find/{instance}", timeout=15)

    async def create_instance(self, instance: str):
        # Evolution v2 uses a dedicated webhook endpoint. Keeping creation
        # independent from webhook configuration avoids legacy-field mismatches.
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
        return await self._request("GET", f"/instance/connect/{instance}")

    async def state(self, instance: str):
        return await self._request("GET", f"/instance/connectionState/{instance}", timeout=15)

    async def delete_instance(self, instance: str):
        return await self._request("DELETE", f"/instance/delete/{instance}", timeout=20)

    async def send_text(self, instance: str, number: str, text: str):
        if instance.startswith("test-biz-"):
            return {"test": True, "text": text}
        return await self._request(
            "POST",
            f"/message/sendText/{instance}",
            json={"number": number, "text": text, "delay": 300, "linkPreview": True},
        )


evolution = EvolutionClient()
