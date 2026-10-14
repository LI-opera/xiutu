from unittest.mock import patch

import pytest
from app.infrastructure.uow import make_engine


@pytest.mark.parametrize(
    "query", ["?hostaddr=192.0.2.10", "?dbname=other&host=192.0.2.10&port=5544", "?service=outside"]
)
def test_new_engine_rejects_before_creation(query):
    with patch(
        "app.infrastructure.uow.create_engine", side_effect=AssertionError("No engine")
    ) as engine:
        with pytest.raises(ValueError):
            make_engine("postgresql://review@localhost:5433/xiutu_test_guard" + query)
        engine.assert_not_called()
