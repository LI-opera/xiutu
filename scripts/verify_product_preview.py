"""Run only this slice's tests in a new retained DB; no .env or model budget."""
import datetime,json,os,subprocess,sys
from pathlib import Path
from uuid import uuid4
sys.path.insert(0,str(Path(__file__).resolve().parent))
from product_preview import ROOT,PREVIEW_DIR,PY,environment
OUT=ROOT/'docs/implementation/product-preview/evidence'/('tests-'+uuid4().hex[:8])
OUT.mkdir(parents=True,exist_ok=False)
d=dict(database='xiutu_test_preview_'+uuid4().hex[:12],storage=str(PREVIEW_DIR/('test-storage-'+uuid4().hex)),actor=str(uuid4()),token=uuid4().hex+uuid4().hex,instance=uuid4().hex,port=5180)
env=environment(d)
commands=[]
def run(label,args,env):
    start=datetime.datetime.now().astimezone().isoformat()
    with (OUT/(label+'.log')).open('x',encoding='utf-8') as log:
        p=subprocess.run(args,cwd=ROOT,env=env,stdout=log,stderr=subprocess.STDOUT)
    commands.append(dict(label=label,command=args,cwd=str(ROOT),start=start,end=datetime.datetime.now().astimezone().isoformat(),exit_code=p.returncode))
    (OUT/'tests-commands.json').write_text(json.dumps(dict(database=d['database'],commands=commands),indent=2),encoding='utf-8')
    return p.returncode
admin=env.copy();admin['DATABASE_URL']=env['DATABASE_URL'].rsplit('/',1)[0]+'/xiutu_dev'
assert run('test-db-create',[str(PY),'-B','scripts/probes/prepare_database.py','--name',d['database']],admin)==0
assert run('test-db-migrate',[str(PY),'-B','-m','alembic','upgrade','head'],env)==0
base=ROOT/'.test-runs'/('product-preview-'+uuid4().hex);base.parent.mkdir(exist_ok=True)
result=run('targeted',[str(PY),'-B','-m','pytest','tests/product_preview/test_api.py','-q','--tb=short','--basetemp',str(base),'--junitxml',str(OUT/'targeted.xml')],env)
print(json.dumps(dict(exit_code=result,database=d['database'],evidence=str(OUT))))
sys.exit(result)
