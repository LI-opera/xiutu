import re

import pytest
from sqlalchemy import Column, Integer, MetaData, String, Table, create_engine
from app.repositories import cases as repository


@pytest.mark.parametrize("description,expected", [
    ("【模拟主诉，非实车检查】加速无力", True),
    ("【C19 独立 DEMO】加速无力", True),
    ("[验收病例] 无力", True),
    ("  SYNTHETIC no real repair", True),
    ("独立流程核对病例：非实车检查或维修", True),
    ("增压压力信号偶尔跳变", False),
    ("路试测试时发现动力不足", False),
    ("维修后验证故障仍存在", False),
    ("【客户反馈】测试时无力", False),
    ("【待体验】动力不足", False),
])
def test_explicit_labels_only(description, expected):
    assert bool(re.search(repository.TEST_CASE_LABEL, description.lower())) is expected


def test_scope_is_applied_before_pagination_and_preserves_owner(monkeypatch):
    metadata = MetaData()
    table = Table('cases', metadata, Column('id', Integer, primary_key=True),
                  Column('owner_id', String), Column('created_at', Integer),
                  Column('fault_description', String))
    engine = create_engine('sqlite://')
    metadata.create_all(engine)
    monkeypatch.setattr(repository, 'cases', table)
    with engine.begin() as connection:
        connection.execute(table.insert(), [
            dict(id=i, owner_id='other' if i == 8 else 'owner', created_at=i,
                 fault_description='【模拟病例】无力' if i in {7,6,4} else '路试测试时无力')
            for i in range(1, 9)
        ])
        repo = repository.CaseRepository(connection)
        first = repo.list('owner', 2, scope='daily')
        assert [r['id'] for r in first] == [5,3,2]  # one look-ahead row
        second = repo.list('owner', 2, (3,3), scope='daily')
        assert [r['id'] for r in second] == [2,1]
        assert [r['id'] for r in repo.list('owner', 10, scope='test')] == [7,6,4]
        assert len(repo.list('owner', 10)) == 7  # old callers still see all
    engine.dispose()
