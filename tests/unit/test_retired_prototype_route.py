from app.config import Settings
from app.main import create_app


def test_prototype_endpoint_is_retired_and_formal_endpoints_remain():
    app = create_app(Settings(_env_file=None, database_url=None, deepseek_api_key=None))
    paths = app.openapi()['paths']
    assert '/api/v2/prototype/ai-analysis' not in paths
    assert '/api/v2/cases/{case_id}/matched-areas/analysis' in paths
    assert '/api/v2/cases/{case_id}/template-repairs' in paths
