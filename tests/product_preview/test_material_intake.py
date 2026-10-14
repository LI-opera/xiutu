"""New intake boundaries, real PostgreSQL; all bytes are explicitly artificial fixtures."""
import json,os
from uuid import uuid4,UUID
import pytest
from fastapi.testclient import TestClient
from app.config import Settings
from app.legacy_preview.product import create_preview,SCOPE
from app.infrastructure.job_store import JobStore
from app.worker import Worker
from test_api import login,TOKEN,ORIGIN

def make(tmp_path):
 return create_preview(Settings(_env_file=None,app_mode='test',retrieval_profile='synthetic',database_url=os.environ['TEST_DATABASE_URL'],data_path=tmp_path,operator_id=uuid4(),operator_token=TOKEN,app_origin=ORIGIN,upload_max_bytes=1024,deepseek_api_key=None,tool_mode='local'))
def meta(synthetic=False):
 return dict(title='Artificial intake test file',source_kind='unverified_material',source_reference='Artificial fixture; no real manual claim',synthetic=synthetic)
def upload(c,h,raw,m):
 h=dict(h,**{'Idempotency-Key':uuid4().hex});return c.post('/api/v2/documents',headers=h,files={'file':('fixture.md',raw,'text/markdown')},data={'metadata':json.dumps(m)})
@pytest.mark.parametrize('size',[1023,1024,1025])
def test_byte_limits_and_config(tmp_path,size):
 app=make(tmp_path)
 with TestClient(app,base_url=ORIGIN) as c:
  assert c.get('/api/v2/preview/config').status_code==401
  h=login(c);assert c.get('/api/v2/preview/config').json()['upload_max_bytes']==1024
  r=upload(c,h,b'# artificial\n'+b'x'*(size-13),meta());assert r.status_code==(413 if size>1024 else 202),r.text
  if size>1024:assert c.get('/api/v2/documents').json()['items']==[]
@pytest.mark.parametrize('synthetic',[False,True])
def test_nature_metadata_parse_review_and_scope(tmp_path,synthetic,monkeypatch):
 monkeypatch.setenv("DATA_PATH",str(tmp_path))
 app=make(tmp_path)
 with TestClient(app,base_url=ORIGIN) as c:
  h=login(c);m=meta(synthetic);m['scope']=SCOPE if synthetic else {};u=upload(c,h,b'# Artificial fixture\n\nNo real repair guidance.',m).json();base=f"/api/v2/documents/{u['document_id']}/versions/{u['version_id']}"
  store=JobStore(os.environ['TEST_DATABASE_URL'])
  try:assert Worker(store).once(run_id=UUID(u['run_id']))
  finally:store.engine.dispose()
  v=c.get(base).json();assert v['parse_status']=='review_pending';assert v['metadata']['synthetic'] is synthetic;assert v['metadata']['license_status']=='unknown';assert v['metadata']['source_status']=='unknown'
  if not synthetic:assert all(x is None for x in v['metadata']['scope'].values())
  assert c.get(base+'/content').status_code==200;assert c.get(base+'/chunks').json()['items']
  review=dict(decision='approved',scope=SCOPE,source_status='verified',license_status='private_use',review_note='synthetic test only')
  r=c.post(base+'/review',json=review,headers=dict(h,**{'Idempotency-Key':uuid4().hex}))
  if synthetic:assert r.status_code==202,r.text
  else:
   assert r.status_code==403 and r.json()['error']['code']=='PREVIEW_REVIEW_SYNTHETIC_ONLY'
   latest=c.get(base).json();assert latest['review_status']=='pending' and latest['active_index_id'] is None and latest['index_exclusion']=='review_not_approved'
   case=c.post('/api/v2/cases',headers=dict(h,**{'Idempotency-Key':uuid4().hex}),json=dict(vehicle=dict(model='HT-2.0',year=2021,engine_family='SYNTH-F',engine_code='SYNTH-C'),fault_description='Artificial test',fault_codes=[]));assert case.status_code==201;assert case.json()['corpus_manifest']==[]
