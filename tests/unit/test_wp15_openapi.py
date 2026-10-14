from scripts.export_frontend_openapi import render


def test_wp15_read_models_are_exported_for_generated_frontend_types():
    document = __import__('json').loads(render())
    expected = {
        '/api/v2/cases/{case_id}/diagnosis': 'DiagnosisView',
        '/api/v2/cases/{case_id}/diagnosis/areas': 'DiagnosisAreaList',
        '/api/v2/cases/{case_id}/observations': 'ObservationList',
        '/api/v2/cases/{case_id}/reports': 'ReportList',
        '/api/v2/cases/{case_id}/reports/gate': 'FinalReportGate',
    }
    for path, schema in expected.items():
        response = document['paths'][path]['get']['responses']['200']['content']['application/json']['schema']
        assert response['$ref'].endswith('/' + schema)


def test_wp15_sse_remains_cookie_authenticated_and_last_event_id_is_a_header():
    document = __import__('json').loads(render())
    operation = document['paths']['/api/v2/runs/{run_id}/events']['get']
    parameters = {(item['name'], item['in']) for item in operation['parameters']}
    assert ('last-event-id', 'header') in parameters
    assert all(item[1] != 'query' or item[0] not in {'token', 'access_token'} for item in parameters)


def test_wp15_evidence_source_access_is_a_strict_generated_contract():
    document = __import__('json').loads(render())
    evidence = document['components']['schemas']['EvidenceView']
    assert 'source_access' in evidence['required']
    source = document['components']['schemas']['EvidenceSourceAccess']
    assert source['additionalProperties'] is False
    assert {'kind', 'status', 'page', 'page_count', 'content_url', 'page_image_status'} <= set(source['properties'])
