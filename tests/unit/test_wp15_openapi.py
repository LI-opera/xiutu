from scripts.export_frontend_openapi import render


def test_exported_api_has_only_current_workbench_paths():
    document = __import__('json').loads(render())
    paths = set(document['paths'])
    for path in ('/api/v2/cases', '/api/v2/cases/{case_id}/workbench-v2',
                 '/api/v2/cases/{case_id}/matched-areas/analysis', '/api/v2/area-references'):
        assert path in paths
    retired = ('/api/v2/documents', '/api/v2/runs', '/api/v2/evidence', '/api/v2/measurement',
               '/api/v2/client-config')
    assert not [path for path in paths if path.startswith(retired)]
    assert not [path for path in paths if '/diagnosis' in path or '/reports' in path
                or path.endswith('/analyses') or '/observations' in path.replace('topic-observations', '')]


def test_case_snapshot_schema_lists_no_retired_fields():
    document = __import__('json').loads(render())
    fields = set(document['components']['schemas']['CaseSnapshot']['properties'])
    assert not fields & {'diagnosis_mode', 'policy_version', 'graph_epoch', 'corpus_manifest',
                         'active_run', 'current_check', 'report_gate'}
