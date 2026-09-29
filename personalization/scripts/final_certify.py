#!/usr/bin/env python3
from __future__ import annotations
import hashlib, json, os, re, shutil, subprocess, sys, time, urllib.parse, urllib.request, uuid
from pathlib import Path
import yaml

HOME = Path(os.environ.get("HERMES_HOME", "/data/.hermes"))
CERT = HOME / "certification"
CERT.mkdir(parents=True, exist_ok=True)
STAGE1 = CERT / "stage1.json"
FINAL = CERT / "final.json"
SENTINEL = CERT / "persistence-sentinel.txt"
LOG_PREFIX = "[certification]"

CUSTOM = {
    "hasan-context","skill-upgrader","github-failure-doctor","autoapply-operator",
    "saudi-lead-finder","daily-operator","career-operator","hands-on-learning-coach",
    "skillspector","hermes-self-admin","website-client-operator","human-writing",
    "integration-doctor","email-delivery-operator","hermes-backup-restore","hermes-certify",
}
CURATED = {
    "llm-wiki","qmd","scrapling","publish-site","planning-with-files",
    "using-superpowers","systematic-debugging","test-driven-development",
    "writing-plans","executing-plans","verification-before-completion",
    "gstack","plan-ceo-review","plan-eng-review","design-review","review","qa",
    "investigate","ship","google-workspace",
}
REQUIRED = CUSTOM | CURATED

def log(msg: str):
    print(f"{LOG_PREFIX} {msg}", flush=True)

def run(args, timeout=90):
    try:
        p = subprocess.run(args, text=True, capture_output=True, timeout=timeout, env=os.environ.copy())
        out = ((p.stdout or "") + "\n" + (p.stderr or "")).strip()
        return {"rc": p.returncode, "output": out[-5000:]}
    except subprocess.TimeoutExpired:
        return {"rc": 124, "output": f"timeout after {timeout}s"}
    except Exception as e:
        return {"rc": 125, "output": f"{type(e).__name__}: {e}"}

def config():
    try:
        return yaml.safe_load((HOME/"config.yaml").read_text(encoding="utf-8")) or {}
    except Exception:
        return {}

def skill_names():
    """Return skill names from real directories and image-backed symlink skills."""
    names=set()
    root=HOME/"skills"
    if not root.exists():
        return names

    seen=set()
    candidates=[]
    try:
        children=list(root.iterdir())
    except Exception:
        children=[]

    for child in children:
        try:
            # Path.rglob does not reliably descend directory symlinks. Resolve
            # image-backed skills explicitly so certification matches what
            # Hermes can actually load without duplicating them onto /data.
            base=child.resolve() if child.is_symlink() else child
            if not base.exists():
                continue
            direct=base/"SKILL.md"
            if direct.exists():
                candidates.append(direct)
            if base.is_dir():
                candidates.extend(base.rglob("SKILL.md"))
        except Exception:
            continue

    # Keep compatibility with any nested persistent layout not reachable from a
    # top-level child for unusual user-created skill packs.
    try:
        candidates.extend(root.rglob("SKILL.md"))
    except Exception:
        pass

    for p in candidates:
        try:
            key=str(p.resolve())
            if key in seen:
                continue
            seen.add(key)
            head=p.read_text(encoding="utf-8", errors="ignore")[:3000]
            m=re.search(r'(?m)^name:\s*["\']?([^\n"\'#]+)', head)
            if m:
                names.add(m.group(1).strip())
            else:
                names.add(p.parent.name)
        except Exception:
            pass
    return names

def wait_for_skills(timeout=75):
    end=time.time()+timeout
    names=skill_names()
    while REQUIRED-names and time.time()<end:
        time.sleep(3)
        names=skill_names()
    return names

def check_static():
    checks={}
    required_files=[
        HOME/"SOUL.md", HOME/"memories/USER.md", HOME/"memories/MEMORY.md",
        HOME/"knowledge/hasan-operating-context.md", HOME/"config.yaml", HOME/"state.db",
    ]
    checks["hermes_home"] = str(HOME)=="/data/.hermes"
    checks["required_files"] = {str(p.relative_to(HOME)): (p.exists() and p.stat().st_size>0) for p in required_files}
    cfg=config()
    mem=cfg.get("memory") if isinstance(cfg.get("memory"),dict) else {}
    sk=cfg.get("skills") if isinstance(cfg.get("skills"),dict) else {}
    aux=cfg.get("auxiliary") if isinstance(cfg.get("auxiliary"),dict) else {}
    bg=aux.get("background_review") if isinstance(aux.get("background_review"),dict) else {}
    model=cfg.get("model") if isinstance(cfg.get("model"),dict) else {}
    checks["config"]={
        "memory_enabled": mem.get("memory_enabled") is True,
        "user_profile_enabled": mem.get("user_profile_enabled") is True,
        "memory_write_free": mem.get("write_approval") is False,
        "memory_nudge": int(mem.get("nudge_interval",0) or 0)>0,
        "skill_write_free": sk.get("write_approval") is False,
        "skill_creation_nudge": int(sk.get("creation_nudge_interval",0) or 0)>0,
        "background_review": bg.get("enabled") is True,
        "model_provider": bool(model.get("provider")),
        "model_default": bool(model.get("default") or model.get("model")),
        "fallbacks": len(cfg.get("fallback_providers") or [])>=1,
    }
    names=wait_for_skills()
    missing=sorted(REQUIRED-names)
    checks["skills"]={"found":len(names),"required":len(REQUIRED),"missing":missing,"ok":not missing}
    pp=HOME/"platforms/pairing/telegram-approved.json"
    try:
        approved=json.loads(pp.read_text(encoding="utf-8")) if pp.exists() else {}
        checks["pairing"]={"telegram_approved_users":len(approved),"ok":len(approved)>=1}
    except Exception:
        checks["pairing"]={"telegram_approved_users":0,"ok":False}
    return checks

def hard_static_ok(ch):
    return (
        ch["hermes_home"] and all(ch["required_files"].values())
        and all(ch["config"].values()) and ch["skills"]["ok"] and ch["pairing"]["ok"]
    )

def telegram_test():
    token=os.environ.get("TELEGRAM_BOT_TOKEN","").strip()
    if not token:
        return {"ok":False,"reason":"token_missing"}
    def api(method, data=None):
        url=f"https://api.telegram.org/bot{token}/{method}"
        body=None
        headers={}
        if data is not None:
            body=urllib.parse.urlencode(data).encode()
            headers["Content-Type"]="application/x-www-form-urlencoded"
        req=urllib.request.Request(url,data=body,headers=headers)
        with urllib.request.urlopen(req,timeout=15) as resp:
            return json.loads(resp.read().decode())
    try:
        me=api("getMe")
        identity_ok=bool(me.get("ok") and me.get("result",{}).get("is_bot"))
        pp=HOME/"platforms/pairing/telegram-approved.json"
        approved=json.loads(pp.read_text(encoding="utf-8")) if pp.exists() else {}
        if not approved:
            return {"ok":False,"identity_ok":identity_ok,"reason":"no_approved_user"}
        target=max(approved.items(), key=lambda kv: (kv[1] or {}).get("approved_at",0))[0]
        sent=api("sendMessage",{
            "chat_id":target,
            "text":"Hermes final certification: Telegram outbound delivery works. No action needed."
        })
        return {
            "ok":bool(identity_ok and sent.get("ok")),
            "identity_ok":identity_ok,
            "paired_user_present":True,
            "message_id_present":bool(sent.get("result",{}).get("message_id")),
        }
    except Exception as e:
        return {"ok":False,"reason":type(e).__name__}

def backup_test():
    outdir=HOME/"backups/exports"
    outdir.mkdir(parents=True,exist_ok=True)
    target=outdir/"final-certification-backup.zip"
    target.unlink(missing_ok=True)
    r=run(["hermes","backup","-o",str(target)],timeout=120)
    ok=r["rc"]==0 and target.exists() and target.stat().st_size>0
    sha=""
    if ok:
        h=hashlib.sha256()
        with target.open("rb") as f:
            for chunk in iter(lambda:f.read(1024*1024),b""):
                h.update(chunk)
        sha=h.hexdigest()
    return {"ok":ok,"rc":r["rc"],"size":target.stat().st_size if target.exists() else 0,"sha256":sha}

def agent_test():
    prompt=(
        "/hasan-context Final certification. You MUST actually use the terminal tool to execute "
        "'printf CERT_TOOL_OK'. Based only on your injected USER.md/profile, confirm the owner's "
        "full name is Hasan Adam. If the hasan-context skill loaded, terminal returned CERT_TOOL_OK, "
        "and profile says Hasan Adam, reply exactly CERT_AGENT_OK. Otherwise reply CERT_AGENT_FAIL."
    )
    r=run(["hermes","chat","-q",prompt],timeout=150)
    return {"ok":r["rc"]==0 and "CERT_AGENT_OK" in r["output"],"rc":r["rc"],"tail":r["output"][-1200:]}

def learn_test():
    probe=HOME/"skills/cert-selflearn-probe"
    if probe.exists():
        shutil.rmtree(probe,ignore_errors=True)
    prompt=(
        "Use the skill management capability to create a temporary skill named cert-selflearn-probe. "
        "Its description should be 'Temporary certification probe' and its instructions should say "
        "'When explicitly invoked, reply CERT_LEARN_OK.' Do not merely describe the skill: persist it. "
        "After it is saved, reply exactly CERT_LEARN_OK."
    )
    r=run(["hermes","chat","-q",prompt],timeout=150)
    exists="cert-selflearn-probe" in skill_names()
    for p in list((HOME/"skills").rglob("SKILL.md")):
        try:
            if re.search(r'(?m)^name:\s*["\']?cert-selflearn-probe\s*$',p.read_text(encoding="utf-8",errors="ignore")):
                shutil.rmtree(p.parent,ignore_errors=True)
        except Exception:
            pass
    return {"ok":r["rc"]==0 and exists and "CERT_LEARN_OK" in r["output"],"rc":r["rc"],"persisted_then_cleaned":exists,"tail":r["output"][-1200:]}

def cli_test():
    results={}
    for key,args,to in [
        ("skills_list",["hermes","skills","list"],60),
        ("skills_audit",["hermes","skills","audit"],120),
        ("sessions",["hermes","sessions","list"],60),
        ("cron",["hermes","cron","list"],60),
        ("doctor_live",["hermes","doctor","--live"],180),
    ]:
        r=run(args,timeout=to)
        results[key]={"ok":r["rc"]==0,"rc":r["rc"],"tail":r["output"][-1800:]}
    return results

def write_json(path,obj):
    tmp=path.with_suffix(".tmp")
    tmp.write_text(json.dumps(obj,indent=2,sort_keys=True),encoding="utf-8")
    tmp.replace(path)

def stage1():
    if not SENTINEL.exists():
        SENTINEL.write_text(str(uuid.uuid4()),encoding="utf-8")
    static=check_static()
    cli=cli_test()
    agent=agent_test()
    learn=learn_test()
    telegram=telegram_test()
    backup=backup_test()
    report={
        "stage":"stage1","created_at":time.time(),
        "sentinel_sha256":hashlib.sha256(SENTINEL.read_bytes()).hexdigest(),
        "static":static,"cli":cli,"agent":agent,"learning":learn,
        "telegram":telegram,"backup":backup,
    }
    report["ok"]=(
        hard_static_ok(static)
        and all(v["ok"] for v in cli.values())
        and agent["ok"] and learn["ok"] and telegram["ok"] and backup["ok"]
    )
    write_json(STAGE1,report)
    log(f"STAGE1 {'PASS' if report['ok'] else 'FAIL'}")
    for k,v in cli.items():
        log(f"stage1 cli {k}={'PASS' if v['ok'] else 'FAIL'} rc={v['rc']}")
    log(f"stage1 static={'PASS' if hard_static_ok(static) else 'FAIL'} agent={'PASS' if agent['ok'] else 'FAIL'} learning={'PASS' if learn['ok'] else 'FAIL'} telegram={'PASS' if telegram['ok'] else 'FAIL'} backup={'PASS' if backup['ok'] else 'FAIL'}")
    if not report["ok"]:
        for k,v in cli.items():
            if not v["ok"]: log(f"DIAG {k}: {v['tail'][-1000:]}")
        if not agent["ok"]: log(f"DIAG agent: {agent['tail'][-1000:]}")
        if not learn["ok"]: log(f"DIAG learning: {learn['tail'][-1000:]}")
    return report["ok"]

def stage2():
    prior=json.loads(STAGE1.read_text(encoding="utf-8"))
    static=check_static()
    same=SENTINEL.exists() and hashlib.sha256(SENTINEL.read_bytes()).hexdigest()==prior.get("sentinel_sha256")
    doctor=run(["hermes","doctor","--live"],timeout=180)
    skills=run(["hermes","skills","list"],timeout=60)
    telegram=telegram_test()
    report={
        "stage":"final","created_at":time.time(),
        "stage1_ok":bool(prior.get("ok")),
        "persistence_sentinel":same,
        "static":static,
        "doctor_live":{"ok":doctor["rc"]==0,"rc":doctor["rc"],"tail":doctor["output"][-1800:]},
        "skills_list":{"ok":skills["rc"]==0,"rc":skills["rc"]},
        "telegram":telegram,
    }
    report["ok"]=(
        report["stage1_ok"] and same and hard_static_ok(static)
        and report["doctor_live"]["ok"] and report["skills_list"]["ok"] and telegram["ok"]
    )
    write_json(FINAL,report)
    log(f"FINAL {'PASS' if report['ok'] else 'FAIL'} persistence={'PASS' if same else 'FAIL'} static={'PASS' if hard_static_ok(static) else 'FAIL'} doctor={'PASS' if report['doctor_live']['ok'] else 'FAIL'} telegram={'PASS' if telegram['ok'] else 'FAIL'}")
    if not report["doctor_live"]["ok"]:
        log(f"DIAG doctor_live: {report['doctor_live']['tail'][-1000:]}")
    return report["ok"]

def boot_check():
    static=check_static()
    ok=hard_static_ok(static)
    log(f"BOOT {'PASS' if ok else 'FAIL'} required_skills={static['skills']['required']} missing={len(static['skills']['missing'])}")
    return ok

if __name__=="__main__":
    try:
        if FINAL.exists():
            ok=boot_check()
        elif STAGE1.exists():
            ok=stage2()
        else:
            ok=stage1()
        sys.exit(0 if ok else 2)
    except Exception as e:
        log(f"EXCEPTION {type(e).__name__}: {e}")
        sys.exit(3)
