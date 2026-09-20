import argparse
import base64
import json
import os
import subprocess
import tempfile
import time
import urllib.request
import urllib.error

SUPABASE_URL = os.getenv("WA_PERSIST_URL", "").rstrip("/")
SUPABASE_KEY = os.getenv("WA_PERSIST_KEY", "")
BACKUP_SECRET = os.getenv("WA_BACKUP_SECRET", "")
INTERVAL = max(15, int(os.getenv("WA_BACKUP_INTERVAL_SECONDS", "30")))

DATABASES = {
    "booking": "booking",
    "evolution": "evolution",
}

def enabled():
    return bool(SUPABASE_URL and SUPABASE_KEY and BACKUP_SECRET)

def rpc(name, payload):
    req = urllib.request.Request(
        f"{SUPABASE_URL}/rest/v1/rpc/{name}",
        data=json.dumps(payload).encode("utf-8"),
        method="POST",
        headers={
            "Content-Type": "application/json",
            "apikey": SUPABASE_KEY,
            "Authorization": f"Bearer {SUPABASE_KEY}",
        },
    )
    with urllib.request.urlopen(req, timeout=60) as res:
        raw = res.read()
        return json.loads(raw.decode("utf-8")) if raw else None

def run(cmd):
    subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)

def backup_one(kind, database):
    fd, path = tempfile.mkstemp(prefix=f"wa-{kind}-", suffix=".dump")
    os.close(fd)
    try:
        run([
            "pg_dump", "-Fc", "-Z", "6",
            "-h", "127.0.0.1", "-p", "5432", "-U", "postgres",
            "-d", database, "-f", path,
        ])
        with open(path, "rb") as f:
            encoded = base64.b64encode(f.read()).decode("ascii")
        rpc("wa_backup_store", {
            "p_secret": BACKUP_SECRET,
            "p_kind": kind,
            "p_payload_b64": encoded,
        })
        print(f"[persistence] backup ok: {kind}", flush=True)
    finally:
        try:
            os.remove(path)
        except FileNotFoundError:
            pass

def backup_all():
    if not enabled():
        print("[persistence] remote persistence is not configured", flush=True)
        return False
    for kind, database in DATABASES.items():
        backup_one(kind, database)
    return True

def load_one(kind):
    data = rpc("wa_backup_load", {
        "p_secret": BACKUP_SECRET,
        "p_kind": kind,
    })
    if not data:
        return None
    if isinstance(data, list):
        if not data:
            return None
        row = data[0]
    else:
        row = data
    return row.get("payload_b64")

def restore_one(kind, database):
    payload = load_one(kind)
    if not payload:
        print(f"[persistence] no remote backup yet: {kind}", flush=True)
        return False
    fd, path = tempfile.mkstemp(prefix=f"wa-restore-{kind}-", suffix=".dump")
    os.close(fd)
    try:
        with open(path, "wb") as f:
            f.write(base64.b64decode(payload))
        run([
            "pg_restore",
            "--clean", "--if-exists", "--no-owner", "--no-privileges",
            "-h", "127.0.0.1", "-p", "5432", "-U", "postgres",
            "-d", database, path,
        ])
        print(f"[persistence] restore ok: {kind}", flush=True)
        return True
    finally:
        try:
            os.remove(path)
        except FileNotFoundError:
            pass

def restore_all():
    if not enabled():
        print("[persistence] remote persistence is not configured", flush=True)
        return False
    restored = False
    for kind, database in DATABASES.items():
        try:
            restored = restore_one(kind, database) or restored
        except Exception as exc:
            print(f"[persistence] restore failed for {kind}: {type(exc).__name__}", flush=True)
            raise
    return restored

def loop():
    # Give migrations / Evolution a few seconds to settle after startup.
    time.sleep(12)
    while True:
        try:
            backup_all()
        except Exception as exc:
            print(f"[persistence] backup cycle failed: {type(exc).__name__}", flush=True)
        time.sleep(INTERVAL)

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=["backup", "restore", "loop"])
    args = parser.parse_args()
    if args.action == "backup":
        backup_all()
    elif args.action == "restore":
        restore_all()
    else:
        loop()

if __name__ == "__main__":
    main()
