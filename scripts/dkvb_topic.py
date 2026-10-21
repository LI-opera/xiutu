"""Independent localhost topic instance; no dotenv or paid credentials."""
from contextlib import closing
import argparse, hashlib, json, os, secrets, shutil, socket, subprocess, sys, time
from pathlib import Path
from uuid import uuid4
from product_preview import environment, stamp, PY, ROOT
sys.path.insert(0,str(ROOT/'backend'))
from app.legacy_preview.dkvb import MANUALS, PDFS, VEHICLE, verify_package, safe_file
import httpx
BASE=ROOT/'.local-data/dkvb-topic'
STATE=BASE/'runtime.json'
PACKAGE=Path(r'E:\Work\v4-double\docs\参考\专题资料包\探岳DKVB-P0299演示资料-v1')
EVIDENCE=ROOT/'.local-data/evidence/product-preview/dkvb-topic'

def save(path,d):
    p=path.with_suffix('.new');p.write_text(json.dumps(d,ensure_ascii=False,indent=2),encoding='utf8');p.replace(path)

def envfor(d):
    e=environment(d)
    e.update(APP_ORIGIN=f'http://localhost:{d["port"]}',DKVB_REGISTRY=str(BASE/'registry.json'),DKVB_DIST=d['dist'],EMBEDDING_PROVIDER='local_bge_m3',EMBEDDING_MODEL='BAAI/bge-m3',EMBEDDING_DIMENSION='1024',EMBEDDING_REVISION='5617a9f61b028005a4858fdac845db406aefb181',EMBEDDING_MODEL_PATH=r'E:\AI_Cache\huggingface\models--BAAI--bge-m3\snapshots\5617a9f61b028005a4858fdac845db406aefb181')
    return e

def client(d):
    c=httpx.Client(base_url=f'http://localhost:{d["port"]}',trust_env=False,timeout=120,headers={'Origin':f'http://localhost:{d["port"]}'})
    res=c.post('/api/v2/auth/login',json={'token':d['token']});res.raise_for_status();c.headers['X-CSRF-Token']=res.json()['csrf_token'];return c

def checked(r):
    if r.status_code>=400:raise RuntimeError(f'HTTP {r.status_code}: '+r.text[:300])
    return r.json()

def main():
    p=argparse.ArgumentParser();p.add_argument('action',choices=['init','start','stop','status','import']);a=p.parse_args()
    if a.action=='init':
        if STATE.exists():raise SystemExit('Existing instance retained; no replacement')
        BASE.mkdir(parents=True,exist_ok=True)
        found=json.loads(subprocess.check_output(['docker','inspect','xiutu-v5-postgres-1'],text=True))[0]
        assert found['State']['Running'] and found['Config']['Labels']['com.docker.compose.project']=='xiutu-v5'
        assert any(x['HostIp']=='127.0.0.1' and x['HostPort']=='5433' for x in found['NetworkSettings']['Ports']['5432/tcp'])
        d=dict(database='xiutu_test_preview_dkvb_'+uuid4().hex[:10],storage=str(BASE/'storage'),actor=str(uuid4()),token=secrets.token_urlsafe(36),instance='dkvb-'+uuid4().hex,port=5196,dist=str(BASE/'dist'),processes=[])
        e=envfor(d);e['DATABASE_URL']=e['DATABASE_URL'].rsplit('/',1)[0]+'/xiutu_dev'
        with (BASE/'init.log').open('x',encoding='utf8') as log:
            z=subprocess.run([str(PY),'-B','scripts/probes/prepare_database.py','--name',d['database']],cwd=ROOT,env=e,stdout=log,stderr=log)
            if z.returncode:raise SystemExit('Database creation failed; private init.log retained')
            z=subprocess.run([str(PY),'-B','-m','alembic','upgrade','head'],cwd=ROOT,env=envfor(d),stdout=log,stderr=log)
            if z.returncode:raise SystemExit('Migration failed; isolated DB retained')
        save(STATE,d);(BASE/'access.txt').write_text(d['token'],encoding='utf8');print('Created independent database/storage; private access.txt retained');return
    d=json.loads(STATE.read_text(encoding='utf8'))
    if a.action=='status':print(json.dumps({'url':f'http://localhost:{d["port"]}/#dkvb','database':d['database'],'processes':[{'label':x['label'],'alive':stamp(x['pid'])==x['stamp']} for x in d['processes']]}));return
    if a.action=='stop':
        for x in reversed(d['processes']):stamp(x['pid'],True,x['stamp'])
        d['processes']=[];save(STATE,d);print('Only own matching processes stopped; data retained');return
    if a.action=='start':
        if any(stamp(x['pid'])==x['stamp'] for x in d['processes']):raise SystemExit('Own instance already running')
        with socket.socket() as s:s.bind(('127.0.0.1',d['port']))
        d['processes']=[]
        try:
            for label,cmd in [('api',['-m','uvicorn','app.legacy_preview.dkvb:create_topic','--factory','--host','127.0.0.1','--port',str(d['port']),'--log-level','warning']),('worker',['-m','app.worker'])]:
                with (BASE/(label+'-'+uuid4().hex[:8]+'.log')).open('x',encoding='utf8') as log:
                    proc=subprocess.Popen([str(PY),'-B',*cmd],cwd=ROOT,env=envfor(d),stdout=log,stderr=log,creationflags=subprocess.CREATE_NO_WINDOW)
                d['processes'].append(dict(label=label,pid=proc.pid,stamp=stamp(proc.pid)));save(STATE,d)
            deadline=time.monotonic()+30
            with httpx.Client(trust_env=False,timeout=2) as c:
                while time.monotonic()<deadline:
                    if any(stamp(x['pid'])!=x['stamp'] for x in d['processes']):raise RuntimeError('Child exited')
                    try:
                        resp=c.get(f'http://localhost:{d["port"]}/api/v2/preview/health')
                        if resp.status_code==200 and resp.json()['instance']==d['instance']:break
                    except (httpx.ConnectError,httpx.ConnectTimeout,httpx.ReadTimeout):pass
                    time.sleep(.2)
                else:raise RuntimeError('Startup deadline exceeded')
            print(f'Ready http://localhost:{d["port"]}/#dkvb');return
        except Exception:
            for x in reversed(d['processes']):stamp(x['pid'],True,x['stamp'])
            raise
    manifest=verify_package(PACKAGE);digest=hashlib.sha256((PACKAGE/'manifest.json').read_bytes()).hexdigest()
    regpath=BASE/'registry.json';reg=json.loads(regpath.read_text(encoding='utf8')) if regpath.exists() else dict(actor=d['actor'],package_hash=digest,documents={},assets=str(BASE/'assets'),figures={},ready=False)
    assert reg['actor']==d['actor'] and reg['package_hash']==digest
    run_evidence=EVIDENCE/('import-'+uuid4().hex[:8]);run_evidence.mkdir(parents=True)
    save(run_evidence/'package-verification.json',dict(manifest_sha256=digest,verified=manifest['files'],retrieval_whitelist=list(MANUALS)))
    with closing(client(d)) as c:
        for name in [*MANUALS,*[x[0] for x in PDFS.values()]]:
            is_manual=name in MANUALS;key='dkvb-'+hashlib.sha256((digest+name).encode()).hexdigest()[:50]
            if name not in reg['documents']:
                metadata=dict(title=name,source_kind='authored_demo' if is_manual else 'pdf_pending_verification',source_reference='DKVB-P0299-DEMO-v1/'+name,source_status='unknown',license_status='unknown',scope=VEHICLE if is_manual else {},synthetic=is_manual)
                with safe_file(PACKAGE,name).open('rb') as f:
                    data=checked(c.post('/api/v2/documents',files={'file':(Path(name).name,f)},data={'metadata':json.dumps(metadata,ensure_ascii=False)},headers={'Idempotency-Key':key}))
                reg['documents'][name]=data|{'sha256':hashlib.sha256(safe_file(PACKAGE,name).read_bytes()).hexdigest()};save(regpath,reg)
            v=reg['documents'][name];url=f'/api/v2/documents/{v["document_id"]}/versions/{v["version_id"]}'
            deadline=time.monotonic()+360
            while True:
                state=checked(c.get(url))
                if state['parse_status'] not in ['pending','parsing']:break
                if time.monotonic()>deadline:raise RuntimeError('Parse deadline: '+name)
                time.sleep(.5)
            if is_manual:
                if state['parse_status']!='review_pending':raise RuntimeError('Manual parse incomplete: '+name)
                if state['review_status'] not in ['pending','approved']:raise RuntimeError('Review changed; refusing automatic reapproval: '+name)
                if state['review_status']=='pending':
                    checked(c.post(url+'/review',json=dict(decision='approved',scope=VEHICLE,source_status='unknown',license_status='unknown',review_note='用户授权的合成专题演示审核；含FACT/EDITORIAL/DEMO，不批准正式规格、规则或软件交付'),headers={'Idempotency-Key':key+'-review'}))
                deadline=time.monotonic()+600
                while True:
                    state=checked(c.get(url))
                    if state['index_status']=='ready':break
                    if state['index_status'] in ['failed','blocked'] or time.monotonic()>deadline:raise RuntimeError('Index not ready: '+name+' '+state['index_status'])
                    time.sleep(.5)
                assert not state['formal_usable']
            save(run_evidence/('version-'+hashlib.sha256(name.encode()).hexdigest()[:8]+'.json'),state)
            print(name,state['parse_status'],state['index_status'],flush=True)
    for f in manifest['files']:
        if f['path'].startswith('figures/'):
            src=safe_file(PACKAGE,f['path']);target=BASE/'assets'/f['path'];target.parent.mkdir(parents=True,exist_ok=True)
            if target.exists():assert hashlib.sha256(target.read_bytes()).hexdigest()==f['sha256']
            else:shutil.copyfile(src,target)
            reg['figures'][f['path']]=f['sha256']
    reg['ready']=True;save(regpath,reg);print('Topic ready; repeated import reuses the same versions and ready indexes')

if __name__=='__main__':main()
