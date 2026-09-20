import os
import subprocess
import sys

VALUE=os.getenv("WA_PERSISTENCE_CANARY","wa-persist-canary-v1")

def psql(db, sql):
    r=subprocess.run(
        ["psql","-h","127.0.0.1","-p","5432","-U","postgres","-d",db,"-Atc",sql],
        check=True,capture_output=True,text=True
    )
    return r.stdout.strip()

def write():
    for db in ("booking","evolution"):
        psql(db, """CREATE TABLE IF NOT EXISTS _wa_persistence_probe(
          value text PRIMARY KEY,
          created_at timestamptz NOT NULL DEFAULT now()
        );""")
        safe=VALUE.replace("'","''")
        psql(db, f"INSERT INTO _wa_persistence_probe(value) VALUES('{safe}') ON CONFLICT(value) DO NOTHING;")
    print("PERSISTENCE_PROBE_WRITTEN=booking,evolution",flush=True)

def check():
    safe=VALUE.replace("'","''")
    found=[]
    for db in ("booking","evolution"):
        count=psql(db,f"SELECT count(*) FROM _wa_persistence_probe WHERE value='{safe}';")
        if count!="1":
            raise RuntimeError(f"persistence canary missing in {db}")
        found.append(db)
    print("PERSISTENCE_PROBE_PASS="+",".join(found),flush=True)

def cleanup():
    for db in ("booking","evolution"):
        psql(db,"DROP TABLE IF EXISTS _wa_persistence_probe;")
    print("PERSISTENCE_PROBE_CLEANED=booking,evolution",flush=True)

if __name__=="__main__":
    mode=sys.argv[1] if len(sys.argv)>1 else "check"
    {"write":write,"check":check,"cleanup":cleanup}[mode]()
