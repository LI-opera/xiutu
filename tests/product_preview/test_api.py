"""Product slice gates against a dedicated PostgreSQL database; no model calls."""
import hashlib
import os
from pathlib import Path
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from app.config import Settings
from app.legacy_preview.product import create_preview

ORIGIN = 'http://127.0.0.1:5180'
TOKEN = 'synthetic-product-preview-test-token-123456'
NEED = {'type':'need_input','missing':['尚未检查，等待合成资料']}

@pytest.fixture
def app(tmp_path):
    settings = Settings(_env_file=None, app_mode='test', retrieval_profile='synthetic',
        database_url=os.environ['TEST_DATABASE_URL'], data_path=tmp_path,
        operator_id=uuid4(), operator_token=TOKEN, app_origin=ORIGIN,
        deepseek_api_key=None, tool_mode='local')
    return create_preview(settings)

@pytest.fixture
def client(app):
    with TestClient(app, base_url=ORIGIN) as c:
        yield c

def login(c):
    r=c.post('/api/v2/auth/login',json={'token':TOKEN},headers={'Origin':ORIGIN})
    assert r.status_code==200
    return {'Origin':ORIGIN, 'X-CSRF-Token':r.json()['csrf_token'], 'Idempotency-Key':uuid4().hex}

def case(c,h):
    r=c.post('/api/v2/cases',json={'vehicle':{'model':'SYNTHETIC','year':2021},'fault_description':'技术测试，无维修结论','fault_codes':[]},headers=h)
    assert r.status_code==201,r.text
    return r.json()

@pytest.mark.parametrize('path',['/api/v2/preview/config','/api/v2/preview/source'])
def test_preview_reads_require_auth(client,path):
    assert client.get(path).status_code==401

@pytest.mark.parametrize('headers',[{}, {'Origin':ORIGIN},{'Origin':'http://evil.invalid','X-CSRF-Token':'wrong'}])
def test_preview_write_security(client,headers):
    h=login(client); item=case(client,h)
    r=client.post(f'/api/v2/cases/{item["id"]}/proposal-preview',json=NEED,headers=headers)
    assert r.status_code==403

def test_preview_unauthenticated_write(client):
    assert client.post(f'/api/v2/cases/{uuid4()}/proposal-preview',json=NEED,headers={'Origin':ORIGIN}).status_code==401

def test_preview_real_service_no_publish_and_refresh(client):
    h=login(client); item=case(client,h); path=f'/api/v2/cases/{item["id"]}/proposal-preview'
    before=client.get('/api/v2/cases/'+item['id']).json()
    r=client.post(path,json=NEED,headers=h)
    assert r.status_code==200,r.text
    assert r.json()['disposition']=='needs_input'
    assert r.json()['published'] is False and r.json()['diagnosis'] is False
    again=client.post(path,json=NEED,headers=h)
    assert again.json()==r.json()
    assert client.get('/api/v2/cases/'+item['id']).json()==before

@pytest.mark.parametrize('field,value',[('actor','forged'),('profile','formal'),('manifest',[]),('conclusion_rules',[]),('revision',999)])
def test_preview_rejects_client_context(client,field,value):
    h=login(client); item=case(client,h)
    r=client.post(f'/api/v2/cases/{item["id"]}/proposal-preview',json=dict(NEED,**{field:value}),headers=h)
    assert r.status_code==422 and r.json()['error']['code']=='VALIDATION_ERROR'

def test_preview_cross_owner_case_404(client,app,tmp_path):
    h=login(client); item=case(client,h)
    other=create_preview(Settings(_env_file=None,app_mode='test',retrieval_profile='synthetic',
        database_url=os.environ['TEST_DATABASE_URL'],data_path=tmp_path/'other',
        operator_id=uuid4(),operator_token=TOKEN,app_origin=ORIGIN,deepseek_api_key=None,tool_mode='local'))
    with TestClient(other,base_url=ORIGIN) as c:
        h2=login(c)
        assert c.get('/api/v2/cases/'+item['id']).status_code==404
        assert c.post(f'/api/v2/cases/{item["id"]}/proposal-preview',json=NEED,headers=h2).status_code==404

def test_preview_source_config_and_schema(client):
    login(client)
    body=client.get('/api/v2/preview/source').content
    assert hashlib.sha256(body).hexdigest()=='e4896ccde323186e8c2c01ca5187b3edfa25977b5a74cb6be45f1a682dedd888'
    conf=client.get('/api/v2/preview/config')
    assert conf.json()['synthetic'] and not conf.json()['rules_installed']
    assert TOKEN not in conf.text and 'database' not in conf.text
    assert conf.headers['Cache-Control']=='no-store'
    schema=client.get('/openapi.json').json()
    assert schema['paths']['/api/v2/preview/source']['get']['security']==[{'SessionCookie':[]}]
    assert schema['paths']['/api/v2/cases/{case_id}/proposal-preview']['post']['security']==[{'SessionCookie':[],'CSRFToken':[]}]

def test_preview_logout_revokes(client):
    h=login(client); item=case(client,h)
    response=client.post('/api/v2/auth/logout',headers=h)
    assert response.status_code==200 and response.json()=={'logged_out':True}
    assert client.post(f'/api/v2/cases/{item["id"]}/proposal-preview',json=NEED,headers=h).status_code==401

@pytest.mark.parametrize('overrides',[
    {'retrieval_profile':'formal'},
    {'database_url':'postgresql://test:test@127.0.0.1:5433/xiutu_test_elsewhere'},
    {'deepseek_api_key':'synthetic-not-real-secret'},
])
def test_preview_startup_fail_closed(tmp_path,overrides):
    data=dict(app_mode='test',retrieval_profile='synthetic',database_url='postgresql://test:test@127.0.0.1:5433/xiutu_test_preview_unit',data_path=tmp_path,deepseek_api_key=None)
    data.update(overrides)
    with pytest.raises(ValueError):create_preview(Settings(_env_file=None,**data))


@pytest.mark.parametrize('mode', ['current', 'old_version', 'wrong_version', 'cross_owner'])
def test_preview_source_mapping(client, app, mode):
    from app.infrastructure.orm import chunks
    from uuid import UUID
    h=login(client)
    meta={'title':'Synthetic source mapping', 'source_kind':'synthetic_preview',
          'source_reference':'isolated test', 'source_status':'unknown',
          'license_status':'private_use', 'scope':{}, 'synthetic':True}
    import json
    raw=b'# synthetic old original'
    u=client.post('/api/v2/documents',headers=h,files={'file':('source.md',raw,'text/markdown')},data={'metadata':json.dumps(meta)})
    assert u.status_code==202,u.text
    info=u.json(); chunk=uuid4(); locator={'source':'mapping-fixture','char_start':0,'char_end':len(raw)}
    with app.state.document_service.engine.begin() as conn:
        conn.execute(chunks.insert().values(id=chunk,document_version_id=UUID(info['version_id']),ordinal=0,
            text=raw.decode(),text_hash=hashlib.sha256(raw).hexdigest(),kind='paragraph',locator_json=locator))
    path=f"/api/v2/preview/versions/{info['version_id']}/chunks/{chunk}/source"
    if mode=='old_version':
        h['Idempotency-Key']=uuid4().hex
        newer=client.post('/api/v2/documents',headers=h,files={'file':('source.md',b'# synthetic new original','text/markdown')},data={'metadata':json.dumps(dict(meta,document_id=info['document_id']))})
        assert newer.status_code==202
        assert newer.json()['version_id']!=info['version_id']
    if mode=='wrong_version':path=path.replace(info['version_id'],str(uuid4()))
    if mode=='cross_owner':
        from sqlalchemy import update
        from app.infrastructure.orm import documents
        with app.state.document_service.engine.begin() as conn:
            conn.execute(update(documents).where(documents.c.id==UUID(info['document_id'])).values(owner_id=uuid4()))
    response=client.get(path)
    if mode in ('wrong_version','cross_owner'):
        assert response.status_code==404
    else:
        assert response.status_code==200,response.text
        assert response.json()==dict(document_id=info['document_id'],document_version_id=info['version_id'],chunk_id=str(chunk),sha256=hashlib.sha256(raw).hexdigest(),locator=locator)
        content=client.get(f"/api/v2/documents/{info['document_id']}/versions/{info['version_id']}/content")
        assert content.content==raw
    client.post('/api/v2/auth/logout',headers=h)
    assert client.get(path).status_code==401
