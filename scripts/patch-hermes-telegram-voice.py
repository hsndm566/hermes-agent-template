#!/usr/bin/env python3
from pathlib import Path
import py_compile

path = Path("/opt/hermes-agent/plugins/platforms/telegram/adapter.py")
src = path.read_text(encoding="utf-8")

old = '''    async def _cache_inbound_av(self, msg, event: MessageEvent, source: Any, label: str, kind: str, ext: str, mime: str) -> bool:
        """Download a voice/audio/video attachment into the local cache. Returns True when the event was
        already dispatched (oversized attachment), so the caller must return."""
        try:
            allowed, note = self._telegram_media_size_allowed(source, label)
            if not allowed:
                event.text = self._append_observed_note(event.text, note or "")
                logger.info("[Telegram] Skipped oversized user %s (size=%s)", kind, getattr(source, "file_size", None))
                await self.handle_message(event)
                return True
            file_obj = await source.get_file()
            data = await file_obj.download_as_bytearray()
            if kind == "video":
                ext = self._ext_from_path(getattr(file_obj, "file_path", None), SUPPORTED_VIDEO_TYPES, ext)
                cached_path = await cache_video_from_bytes_async(bytes(data), ext=ext)
                mime = SUPPORTED_VIDEO_TYPES.get(ext, "video/mp4")
            else:
                cached_path = await cache_audio_from_bytes_async(bytes(data), ext=ext)
            event.media_urls = [cached_path]
            event.media_types = [mime]
            logger.info("[Telegram] Cached user %s at %s", kind, cached_path)
        except Exception as e:
            logger.warning("[Telegram] Failed to cache %s: %s", kind, _redact_telegram_error_text(e), exc_info=True)
            await self._surface_media_cache_failure(msg, event, label, e)
        return False
'''

new = '''    async def _cache_inbound_av(self, msg, event: MessageEvent, source: Any, label: str, kind: str, ext: str, mime: str) -> bool:
        """Download inbound A/V reliably and pre-transcribe Telegram voice notes.

        Telegram/CDN fetches are transiently flaky, so voice downloads get bounded
        exponential retry. For native voice notes we also run STT immediately after
        caching and attach the result to the MessageEvent's existing pending-STT
        cache fields. That makes fresh Telegram voice independent of the later
        gateway enrichment handoff while still letting the central gateway retry
        normally if this eager attempt fails.
        """
        try:
            allowed, note = self._telegram_media_size_allowed(source, label)
            if not allowed:
                event.text = self._append_observed_note(event.text, note or "")
                logger.info("[Telegram] Skipped oversized user %s (size=%s)", kind, getattr(source, "file_size", None))
                await self.handle_message(event)
                return True

            attempts = 3 if kind == "voice" else 1
            last_exc = None
            file_obj = data = None
            for attempt in range(attempts):
                try:
                    file_obj = await source.get_file()
                    data = await file_obj.download_as_bytearray()
                    last_exc = None
                    break
                except Exception as exc:
                    last_exc = exc
                    if attempt + 1 < attempts:
                        delay = 1.5 * (2 ** attempt)
                        logger.warning(
                            "[Telegram] %s download attempt %d/%d failed; retrying in %.1fs: %s",
                            kind, attempt + 1, attempts, delay, _redact_telegram_error_text(exc),
                        )
                        await asyncio.sleep(delay)
            if last_exc is not None:
                raise last_exc

            if kind == "video":
                ext = self._ext_from_path(getattr(file_obj, "file_path", None), SUPPORTED_VIDEO_TYPES, ext)
                cached_path = await cache_video_from_bytes_async(bytes(data), ext=ext)
                mime = SUPPORTED_VIDEO_TYPES.get(ext, "video/mp4")
            else:
                cached_path = await cache_audio_from_bytes_async(bytes(data), ext=ext)

            event.media_urls = [cached_path]
            event.media_types = [mime]
            if kind == "voice":
                event.message_type = MessageType.VOICE
            logger.info("[Telegram] Cached user %s at %s", kind, cached_path)

            if kind == "voice":
                try:
                    from tools.transcription_tools import transcribe_audio
                    result = await asyncio.wait_for(
                        asyncio.to_thread(transcribe_audio, cached_path, None, "gateway"),
                        timeout=240,
                    )
                    transcript = (result.get("transcript") or "").strip() if result.get("success") else ""
                    if transcript:
                        original_text = (event.text or "").strip()
                        quoted = f'"{transcript}"'
                        event._gateway_pending_stt_text = (
                            f"{quoted}\n\n{original_text}" if original_text else quoted
                        )
                        event._gateway_pending_stt_transcripts = [transcript]
                        logger.info(
                            "[Telegram] Pre-transcribed user voice at %s (%d chars)",
                            cached_path, len(transcript),
                        )
                    else:
                        logger.warning(
                            "[Telegram] Eager voice STT did not succeed; central gateway will retry: %s",
                            result.get("error", "empty transcript"),
                        )
                except Exception as exc:
                    logger.warning(
                        "[Telegram] Eager voice STT failed; central gateway will retry: %s",
                        exc, exc_info=True,
                    )
        except Exception as e:
            logger.warning("[Telegram] Failed to cache %s: %s", kind, _redact_telegram_error_text(e), exc_info=True)
            await self._surface_media_cache_failure(msg, event, label, e)
            # Fail closed after the user-facing retry notice. Dispatching an
            # empty voice event creates a fake user turn and guarantees STT
            # cannot recover because there is no cached path.
            if kind == "voice":
                return True
        return False
'''

marker = "[Telegram] Pre-transcribed user voice"
if marker not in src:
    if old not in src:
        raise SystemExit("voice patch anchor not found; refusing to build against unexpected Hermes source")
    src = src.replace(old, new, 1)
    path.write_text(src, encoding="utf-8")

py_compile.compile(str(path), doraise=True)
if marker not in path.read_text(encoding="utf-8"):
    raise SystemExit("voice patch verification failed")
print("[voice-patch] Telegram eager STT + download retry installed")
