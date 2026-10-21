from copy import deepcopy
import hashlib

from app.services.analysis_context import digest, enrich, model_payload


def fixture():
    questions = [{"id":"random-a","title":"现场情况"}, {"id":"random-b","title":"下一步安排"}]
    body = "## Conditions\nconditions\n## Method\nmethod and alternatives\n"
    binding = {"template_id":"unrelated-template","version":"9","content_hash":"frozen"}
    document = {"id":"unrelated-document","version":"7","body":body,
                "content_hash":hashlib.sha256(body.encode()).hexdigest()}
    config = {"version":"1","templates":[{**binding,"questions":{
        "random-a":{"definition_hash":digest(questions[0]),"role":"observation",
                    "option_roles":{"missing":"inspection_status"},"references":{document['id']:["method"]}},
        "random-b":{"definition_hash":digest(questions[1]),"role":"disposition"}}}],
        "documents":[{k:v for k,v in document.items() if k!='body'} | {
            "always_include":["conditions"],"sections":{
                "conditions":{"heading":"## Conditions","start":0,"end":body.index('## Method')},
                "method":{"heading":"## Method","start":body.index('## Method'),"end":len(body)}}}]}
    payload = {"template_binding":binding,"questions":deepcopy(questions),"documents":[document],
               "observations":[{"id":"record","question_id":"random-a","option_ids":["missing"],
                                "note":"保留不确定原文","fields":{"n":7}}],
               "unknown_question_ids":["random-b"]}
    return payload, {"questions":questions}, config


def test_arbitrary_template_uses_metadata_and_preserves_originals():
    payload, topic, config = fixture()
    before = deepcopy(payload)
    result = enrich(payload,topic,config)
    assert all(result['documents'][0][k] == v for k,v in before['documents'][0].items())
    for key,value in before['observations'][0].items():
        assert result['observations'][0][key] == value
    assert result['observations'][0]['selected_option_roles'][0]['role']=='inspection_status'
    assert result['observations'][0]['free_text_role']=='unclassified'
    assert result['unknown_question_ids']==[]
    assert result['unrecorded_decision_question_ids']==['random-b']
    sections=result['reference_reading_guide']['documents'][0]['sections']
    assert [s['section_id'] for s in sections]==['conditions','method']
    assert sections[1]['question_ids']==['random-a']


def test_stale_document_never_uses_old_offsets_or_loses_body():
    payload,topic,config=fixture()
    payload['documents'][0]['body']+='changed'
    result=enrich(payload,topic,config)
    assert result['reference_reading_guide']['documents'][0]['status']=='unconfigured_or_changed'
    assert result['documents'][0]['body'].endswith('changed')


def test_unknown_template_keeps_unknowns_without_guessing():
    payload,topic,config=fixture()
    payload['template_binding']={**payload['template_binding'],'content_hash':'changed'}
    result=enrich(payload,topic,config)
    assert result['unknown_question_ids']==['random-b']
    assert all(q['record_role']=='unclassified' for q in result['questions'])


def test_question_drift_does_not_apply_old_role():
    payload,topic,config=fixture()
    topic['questions'][1]['title']='不同含义'
    assert enrich(payload,topic,config)['unknown_question_ids']==['random-b']


def test_invalid_locator_falls_back_to_complete_source():
    payload,topic,config=fixture()
    config['documents'][0]['sections']['method']['start']=9999
    result=enrich(payload,topic,config)
    assert result['reference_reading_guide']['documents'][0]['sections']==[]
    assert result['documents'][0]['body']


def test_selected_result_is_bound_to_record_and_transport_is_nonmutating():
    payload,topic,config=fixture()
    config['templates'][0]['questions']['random-a']['option_references']={
        'missing':{'unrelated-document':['method']},
        'other':{'unrelated-document':['absent']}}
    result=enrich(payload,topic,config)
    before=deepcopy(result)
    sent=model_payload(result)
    focus=sent['reference_reading_guide']['documents'][0]['result_methods']
    assert focus[0]['selected_by']==[{'observation_id':'record','option_id':'missing'}]
    assert focus[0]['heading']=='## Method' and 'text' not in focus[0]
    # The method itself is sent once, inside the extracted body.
    assert sent['documents'][0]['body'].count('method and alternatives')==1
    assert result==before
    assert 'analysis_extracts' not in sent['documents'][0]
    assert sent['documents'][0]['full_content_hash']==result['documents'][0]['content_hash']
    assert sent['documents'][0]['content_hash']==hashlib.sha256(sent['documents'][0]['body'].encode()).hexdigest()


def test_unknown_facts_keep_their_methods_and_context_is_not_dropped():
    payload,topic,config=fixture()
    payload['observations']=[]
    payload['unknown_question_ids']=['random-a','random-b']
    result=enrich(payload,topic,config)
    sent=model_payload(result)
    assert 'conditions' in sent['documents'][0]['body']
    assert 'method and alternatives' in sent['documents'][0]['body']
    assert result['unrecorded_decision_question_ids']==['random-b']


def test_unmapped_question_retains_full_document_transport():
    payload,topic,config=fixture()
    del config['templates'][0]['questions']['random-b']
    sent=model_payload(enrich(payload,topic,config))
    assert sent['documents'][0]['body_scope']=='full_document_fallback'
    assert sent['documents'][0]['body']==payload['documents'][0]['body']


def test_only_configured_ranges_sent_while_full_snapshot_retained():
    payload,topic,config=fixture()
    body=payload['documents'][0]['body']+'## Unrelated example\nnot selected\n'
    payload['documents'][0]['body']=body
    payload['documents'][0]['content_hash']=hashlib.sha256(body.encode()).hexdigest()
    config['documents'][0]['content_hash']=payload['documents'][0]['content_hash']
    result=enrich(payload,topic,config)
    sent=model_payload(result)
    assert 'Unrelated example' in result['documents'][0]['body']
    assert 'Unrelated example' not in sent['documents'][0]['body']
