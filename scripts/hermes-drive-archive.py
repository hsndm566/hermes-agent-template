#!/usr/bin/env python3
"""
Hermes -> Google Drive archival worker.

Keeps the Railway volume small while preserving durable state externally.
- Creates archives in /tmp (never on the persistent volume).
- Uses Hermes' own Google OAuth token/client files under /data/.hermes.
- Never archives .env, auth.json, OAuth tokens/client secrets, or other credential files.
- Uploads state snapshots and logs to pre-created Drive folders.
- Prunes only disposable local logs/caches after a successful upload.
"""
from __future__ import annotations

import io
import json
import os
import shutil
import sqlite3
import sys
import tarfile
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path

HERMES_HOME = Path(os.getenv("HERMES_HOME", "/data/.hermes"))
TOKEN = HERMES_HOME / "google_token.json"
CLIENT = HERMES_HOME / "google_client_secret.json"

BACKUPS_FOLDER = os.getenv("HERMES_DRIVE_BACKUPS_FOLDER_ID", "").strip()
LOGS_FOLDER = os.getenv("HERMES_DRIVE_LOGS_FOLDER_ID", "").strip()

SCOPES = [
    "https://www.googleapis.com/auth/drive.file",
    "https://www.googleapis.com/auth/drive",
]

SECRET_NAMES = {
    ".env",
    "auth.json",
    "google_token.json",
    "google_client_secret.json",
    "google_oauth_pending.json",
}

BACKUP_PATHS = [
    "state.db",
    "shared-state.db",
    "kanban.db",
    "memories",
    "knowledge",
    "workspace",
    "plans",
    "cron",
    "platforms",
    "pairing",
    "gateway_state.json",
    "active_sessions.json",
    "SOUL.md",
    "USER.md",
    "MEMORY.md",
]

def utc_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")

def google_service():
    if not TOKEN.exists():
        raise RuntimeError("google_token.json missing")
    try:
        from google.oauth2.credentials import Credentials
        from google.auth.transport.requests import Request
        from googleapiclient.discovery import build
    except Exception as exc:
        raise RuntimeError(f"Google API libraries unavailable: {exc}")

    creds = Credentials.from_authorized_user_file(str(TOKEN))
    if creds.expired and creds.refresh_token:
        creds.refresh(Request())
        TOKEN.write_text(creds.to_json(), encoding="utf-8")
        try:
            os.chmod(TOKEN, 0o600)
        except OSError:
            pass
    if not creds.valid:
        raise RuntimeError("Google OAuth credentials are not valid")
    return build("drive", "v3", credentials=creds, cache_discovery=False)

def upload_file(service, local_path: Path, folder_id: str, remote_name: str, mime_type: str):
    from googleapiclient.http import MediaFileUpload
    meta = {"name": remote_name, "parents": [folder_id]}
    media = MediaFileUpload(str(local_path), mimetype=mime_type, resumable=True)
    return service.files().create(
        body=meta,
        media_body=media,
        fields="id,name,size,createdTime",
        supportsAllDrives=True,
    ).execute()

def safe_add(tf: tarfile.TarFile, path: Path, arcname: str):
    if path.name in SECRET_NAMES:
        return
    if path.is_symlink():
        return
    if path.is_dir():
        for child in path.iterdir():
            safe_add(tf, child, f"{arcname}/{child.name}")
        return
    tf.add(path, arcname=arcname, recursive=False)

def snapshot_sqlite(src: Path, dest: Path) -> bool:
    if not src.exists():
        return False
    try:
        con = sqlite3.connect(f"file:{src}?mode=ro", uri=True)
        out = sqlite3.connect(dest)
        con.backup(out)
        out.close()
        con.close()
        return True
    except Exception:
        shutil.copy2(src, dest)
        return True

def make_state_archive() -> Path | None:
    tmpdir = Path(tempfile.mkdtemp(prefix="hermes-drive-"))
    stage = tmpdir / "state"
    stage.mkdir()
    added = False

    for rel in BACKUP_PATHS:
        src = HERMES_HOME / rel
        if not src.exists() or src.name in SECRET_NAMES:
            continue
        dst = stage / rel
        if src.is_file() and src.suffix == ".db":
            dst.parent.mkdir(parents=True, exist_ok=True)
            added = snapshot_sqlite(src, dst) or added
        elif src.is_file():
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)
            added = True
        elif src.is_dir():
            shutil.copytree(
                src, dst, dirs_exist_ok=True,
                ignore=shutil.ignore_patterns(
                    "*.lock", "*.tmp", "*.cache", "__pycache__",
                    ".env", "auth.json", "google_token.json",
                    "google_client_secret.json", "google_oauth_pending.json",
                ),
            )
            added = True

    if not added:
        shutil.rmtree(tmpdir, ignore_errors=True)
        return None

    archive = tmpdir / f"hermes-state-{utc_stamp()}.tar.gz"
    with tarfile.open(archive, "w:gz") as tf:
        for child in stage.iterdir():
            safe_add(tf, child, child.name)
    shutil.rmtree(stage, ignore_errors=True)
    return archive

def make_logs_archive() -> Path | None:
    log_dir = HERMES_HOME / "logs"
    if not log_dir.exists():
        return None
    files = [p for p in log_dir.iterdir() if p.is_file() and p.stat().st_size > 0]
    if not files:
        return None
    tmpdir = Path(tempfile.mkdtemp(prefix="hermes-logs-"))
    archive = tmpdir / f"hermes-logs-{utc_stamp()}.tar.gz"
    with tarfile.open(archive, "w:gz") as tf:
        for p in files:
            if p.name not in SECRET_NAMES:
                tf.add(p, arcname=p.name, recursive=False)
    return archive

def prune_after_upload():
    log_dir = HERMES_HOME / "logs"
    if log_dir.exists():
        for p in log_dir.iterdir():
            if not p.is_file():
                continue
            if ".log." in p.name or p.suffix in {".gz", ".old"}:
                try:
                    p.unlink()
                except OSError:
                    pass
            elif p.name.endswith(".log"):
                try:
                    if p.stat().st_size > 2 * 1024 * 1024:
                        data = p.read_bytes()[-2 * 1024 * 1024:]
                        p.write_bytes(data)
                except OSError:
                    pass

    for rel in ("cache/audio", "cache/images", "cache/terminal", "cache/uv"):
        d = HERMES_HOME / rel
        if d.exists():
            for child in d.iterdir():
                try:
                    if child.is_dir() and not child.is_symlink():
                        shutil.rmtree(child, ignore_errors=True)
                    else:
                        child.unlink(missing_ok=True)
                except OSError:
                    pass

def main() -> int:
    if not BACKUPS_FOLDER or not LOGS_FOLDER:
        print("[drive-archive] folder IDs not configured", file=sys.stderr)
        return 2
    if not TOKEN.exists():
        print("[drive-archive] Google OAuth not configured yet; archive skipped", file=sys.stderr)
        return 3

    service = google_service()
    uploaded = []

    state_archive = make_state_archive()
    try:
        if state_archive:
            res = upload_file(
                service, state_archive, BACKUPS_FOLDER,
                state_archive.name, "application/gzip"
            )
            uploaded.append(("state", res.get("id")))
    finally:
        if state_archive:
            shutil.rmtree(state_archive.parent, ignore_errors=True)

    logs_archive = make_logs_archive()
    try:
        if logs_archive:
            res = upload_file(
                service, logs_archive, LOGS_FOLDER,
                logs_archive.name, "application/gzip"
            )
            uploaded.append(("logs", res.get("id")))
    finally:
        if logs_archive:
            shutil.rmtree(logs_archive.parent, ignore_errors=True)

    if uploaded:
        prune_after_upload()
    print(f"[drive-archive] uploaded={','.join(k for k,_ in uploaded) or 'none'}", flush=True)
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
