"""Windows local synthetic preview lifecycle. No dotenv, no paid model, no shared DB."""
import argparse
import ctypes
from ctypes import wintypes
import hashlib
import json
import os
from pathlib import Path
import secrets
import socket
import subprocess
import sys
import time
from urllib.parse import quote
from uuid import uuid4

ROOT=Path(__file__).resolve().parents[1]
PREVIEW_DIR=ROOT/'.local-data/product-preview'
STATE=PREVIEW_DIR/'runtime.json'
PY=ROOT/'.venv/Scripts/python.exe'
PORT=5180

def save(data):
    tmp=STATE.with_suffix('.new');tmp.write_text(json.dumps(data,indent=2),encoding='utf-8');tmp.replace(STATE)

def stamp(pid, terminate=False, expected=None):
    k=ctypes.WinDLL('kernel32',use_last_error=True)
    k.OpenProcess.argtypes=[wintypes.DWORD,wintypes.BOOL,wintypes.DWORD];k.OpenProcess.restype=wintypes.HANDLE
    k.CloseHandle.argtypes=[wintypes.HANDLE]
    k.GetProcessTimes.argtypes=[wintypes.HANDLE,*([ctypes.POINTER(wintypes.FILETIME)]*4)]
    k.TerminateProcess.argtypes=[wintypes.HANDLE,wintypes.UINT]
    handle=k.OpenProcess(0x1000 | (1 if terminate else 0),False,pid)
    if not handle:return None
    try:
        values=[wintypes.FILETIME() for _ in range(4)]
        if not k.GetProcessTimes(handle,*[ctypes.byref(v) for v in values]):return None
        value=(values[0].dwHighDateTime<<32)|values[0].dwLowDateTime
        if terminate and value==expected:
            subprocess.run(["taskkill", "/PID", str(pid), "/T", "/F"], capture_output=True, timeout=10, creationflags=subprocess.CREATE_NO_WINDOW)
        return value
    finally:k.CloseHandle(handle)

def environment(d):
    # DB credential is only loaded locally; never printed or placed in command argv.
    password=json.loads((ROOT/'.local-data/wp01-postgres.json').read_text(encoding='utf-8'))['password']
    url='postgresql://xiutu:'+quote(password,safe='')+'@127.0.0.1:5433/'+d['database']
    env={k:v for k,v in os.environ.items() if not (k.startswith(('PG','DEEPSEEK','LLM_','EMBEDDING_','MCP_','XIUTU_','TEST_DATABASE')) or k in ['DATABASE_URL','APP_MODE','DATA_PATH','RETRIEVAL_PROFILE','OPERATOR_TOKEN','OPERATOR_ID','APP_ORIGIN'])}
    env.update(PYTHONPATH=str(ROOT/'backend'),PYTHONIOENCODING='utf-8',PYTHONDONTWRITEBYTECODE='1',APP_MODE='test',RETRIEVAL_PROFILE='synthetic',DATABASE_URL=url,TEST_DATABASE_URL=url,DATA_PATH=d['storage'],OPERATOR_TOKEN=d['token'],OPERATOR_ID=d['actor'],APP_ORIGIN=f'http://127.0.0.1:{d["port"]}',EMBEDDING_PROVIDER='local_e5',EMBEDDING_PATH=str(ROOT/'.local-data/models/multilingual-e5-small/614241f622f53c4eeff9890bdc4f31cfecc418b3'),PREVIEW_INSTANCE=d['instance'],TOOL_MODE='local')
    return env

def main():
    parser=argparse.ArgumentParser();parser.add_argument('action',choices=['init','start','stop','status']);a=parser.parse_args()
    if a.action=='init':
        if STATE.exists():raise SystemExit('Existing preview retained; use start/status. No database replaced.')
        PREVIEW_DIR.mkdir(parents=True,exist_ok=True)
        d=dict(database='xiutu_test_preview_'+uuid4().hex[:12],storage=str(PREVIEW_DIR/('storage-'+uuid4().hex)),actor=str(uuid4()),token=secrets.token_urlsafe(36),instance=uuid4().hex,port=PORT,processes=[])
        env=environment(d)
        # Ownership gate rechecked against the existing postgres service; never start it here.
        found=json.loads(subprocess.check_output(['docker','inspect','xiutu-v5-postgres-1'],text=True))[0]
        assert found['State']['Running'] and found['Config']['Labels']['com.docker.compose.project']=='xiutu-v5'
        assert any(x['HostIp']=='127.0.0.1' and x['HostPort']=='5433' for x in found['NetworkSettings']['Ports']['5432/tcp'])
        # prepare_database accepts the already validated local development target only for CREATE DATABASE.
        env['DATABASE_URL']=env['DATABASE_URL'].rsplit('/',1)[0]+'/xiutu_dev'
        with (PREVIEW_DIR/'init.log').open('x',encoding='utf-8') as log:
            p=subprocess.run([str(PY),'-B','scripts/probes/prepare_database.py','--name',d['database']],cwd=ROOT,env=env,stdout=log,stderr=log)
            if p.returncode:raise SystemExit('Create failed; see private init.log. No automatic retry.')
            env=environment(d)
            p=subprocess.run([str(PY),'-B','-m','alembic','upgrade','head'],cwd=ROOT,env=env,stdout=log,stderr=log)
            if p.returncode:raise SystemExit('Migration failed; keep isolated database for diagnosis.')
        save(d)
        (PREVIEW_DIR/'access.txt').write_text(d['token'],encoding='utf-8')
        print('Initialized isolated preview. Access token: .local-data/product-preview/access.txt (private).')
        return
    d=json.loads(STATE.read_text(encoding='utf-8'))
    if a.action=='status':
        print(json.dumps(dict(url=f'http://127.0.0.1:{d["port"]}',database=d['database'],processes=[dict(pid=x['pid'],alive=stamp(x['pid'])==x['stamp']) for x in d['processes']]),indent=2));return
    if a.action=='stop':
        for x in reversed(d['processes']):stamp(x['pid'],True,x['stamp'])
        d['processes']=[];save(d);print('Stopped only matching owned PIDs. Database/storage retained.');return
    if any(stamp(x['pid'])==x['stamp'] for x in d['processes']):raise SystemExit('Owned processes already running; use status/stop.')
    with socket.socket() as sock:
        try:sock.bind(('127.0.0.1',d['port']))
        except OSError:raise SystemExit('Port occupied; no unknown process stopped.')
    env=environment(d);d['processes']=[]
    try:
        for label,cmd in [('api',['-m','uvicorn','app.legacy_preview.product:create_preview','--factory','--host','127.0.0.1','--port',str(d['port']),'--log-level','warning']),('worker',['-m','app.worker'])]:
            log=(PREVIEW_DIR/(label+'-'+uuid4().hex[:8]+'.log')).open('x',encoding='utf-8')
            p=subprocess.Popen([str(PY),'-B',*cmd],cwd=ROOT,env=env,stdout=log,stderr=log,creationflags=subprocess.CREATE_NO_WINDOW)
            log.close();d['processes'].append(dict(pid=p.pid,stamp=stamp(p.pid),label=label));save(d)
        import httpx
        deadline=time.monotonic()+30
        with httpx.Client(trust_env=False,timeout=2) as client:
            while time.monotonic()<deadline:
                if any(stamp(x['pid'])!=x['stamp'] for x in d['processes']):raise RuntimeError('Owned child exited; inspect private logs')
                try:
                    r=client.get(f'http://127.0.0.1:{d["port"]}/api/v2/preview/health')
                    if r.status_code==200 and r.json().get('instance')==d['instance']:
                        ready=client.get(f'http://127.0.0.1:{d["port"]}/api/v2/health/ready')
                        if ready.status_code==200:break
                except (httpx.ConnectError,httpx.ConnectTimeout,httpx.ReadTimeout):pass
                time.sleep(.3)
            else:raise RuntimeError('Bounded 30 second preview startup failed')
        print(f'Preview ready: http://127.0.0.1:{d["port"]} ; token in private access.txt')
    except Exception:
        for x in reversed(d['processes']):stamp(x['pid'],True,x['stamp'])
        raise

if __name__=='__main__':main()
