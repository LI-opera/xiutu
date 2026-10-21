"""Read-only topic verification except creating one dedicated frozen case through API."""
import sys,json,hashlib,time
from pathlib import Path
from contextlib import closing
from uuid import uuid4
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/'scripts'));sys.path.insert(0,str(ROOT/'backend'))
from dkvb_topic import BASE,STATE,client,checked,envfor,MANUALS,PDFS
import httpx
from sqlalchemy import create_engine,text
from app.infrastructure.db_target import validate_target
out=ROOT/'.local-data/evidence/product-preview/dkvb-topic'/('http-'+uuid4().hex[:8]);out.mkdir(parents=True)
d=json.loads(STATE.read_text(encoding='utf8'));reg=json.loads((BASE/'registry.json').read_text(encoding='utf8'))
start=time.time();results=[]
with closing(client(d)) as c:
    state=checked(c.get('/api/v2/topic'));assert len(state['documents'])==5
    assert sum(x['index_status']=='ready' for x in state['documents'])==2
    for x in state['documents']:
        assert x['metadata']['synthetic']==(x['name'] in MANUALS)
        assert not x['formal_usable']
        if x['name'] not in MANUALS:assert x['metadata']['source_status']=='unknown' and x['metadata']['license_status']=='unknown' and x['review_status']!='approved'
    case=checked(c.post('/api/v2/topic/cases',json={},headers={'Idempotency-Key':str(uuid4())}))
    vids={v['version_id'] for k,v in reg['documents'].items() if k in MANUALS}
    assert {x['document_version_id'] for x in case['corpus_manifest']}==vids
    questions=['增压空气系统泄漏检查为什么不能用保压下降判断？','G31的位置依据在哪里？','V465调整应查哪份原文？','演示压力跟随阈值是多少，是否属于厂家标准？']
    for q in questions:
        result=checked(c.post('/api/v2/topic/search',json={'case_id':case['id'],'query':q,'top_k':5}))
        assert result['chunks'] and all(x['document_version_id'] in vids for x in result['chunks'])
        assert result['trace']['model'][0]['dimension']==1024
        mapped=[]
        for hit in result['chunks']:
            loc=checked(c.get(f'/api/v2/topic/cases/{case["id"]}/chunks/{hit["chunk_id"]}'))
            assert loc['text']==hit['text'] and hashlib.sha256(loc['text'].encode()).hexdigest()==loc['chunk_hash']
            for page in loc['pages']:
                pdf=c.get(f'/api/v2/topic/sources/{page["source_id"]}/{page["page"]}');assert pdf.status_code==200 and hashlib.sha256(pdf.content).hexdigest()==page['sha256']
                img=c.get(f'/api/v2/topic/sources/{page["source_id"]}/{page["page"]}/image');assert img.status_code==200
                assert hashlib.sha256(img.content).hexdigest()==reg['figures'][f'figures/{page["source_id"]}-{page["page"]}.png']
            mapped.append(loc)
        results.append(dict(question=q,result=result,mappings=mapped))
    assert c.get('/api/v2/topic/sources/S02/99/image').status_code==404
    assert c.get(f'/api/v2/topic/cases/{uuid4()}/chunks/{results[0]["result"]["chunks"][0]["chunk_id"]}').status_code==404
    assert c.post('/api/v2/topic/search',json={'case_id':case['id'],'query':'G31','profile':'formal'}).status_code==422
with httpx.Client(base_url=f'http://localhost:{d["port"]}',trust_env=False) as c:
    assert c.get('/api/v2/topic').status_code==401
    assert c.get('/api/v2/topic/sources/S01/1/image').status_code==401
# Current index inventory via validated local target; no model or source mutation.
import psycopg
target=validate_target(envfor(d)['DATABASE_URL'],'test')
with psycopg.connect(**target.connect_kwargs()) as conn:
    inventory=conn.execute("SELECT config_json->>'model',config_json->>'dimension',status,count(*) FROM index_versions GROUP BY 1,2,3").fetchall()
    counts={t:conn.execute('SELECT count(*) FROM '+t).fetchone()[0] for t in ['documents','document_versions','index_versions','chunk_embeddings']}
assert counts['documents']==5 and counts['document_versions']==5 and counts['index_versions']==2
(out/'results.json').write_text(json.dumps(dict(start=start,end=time.time(),case=case,queries=results,inventory=inventory,counts=counts,unauthenticated=401,wrong_case=404),ensure_ascii=False,indent=2),encoding='utf8')
print(json.dumps(dict(output=str(out),counts=counts,questions=len(results),status='PASS'),ensure_ascii=False))
