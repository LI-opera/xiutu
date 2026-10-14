import pytest
from app.services.template_case_history import summarize, require_open, is_closed
from app.domain.policies import DomainError

def case(closed=False):
    return {'intake_snapshot':{'workbench_flow':'template-match-v1','case_lifecycle':{'closed':closed},'template_content':{'questions':[
        {'id':'q1','area_id':'a','answer_kind':'single'}, {'id':'q2','area_id':'b','answer_kind':'single'},
        {'id':'d','area_id':'a','answer_kind':'automatic_derived'}]}}}

def test_counts_effective_records_and_keeps_pending_when_user_closes():
    records=[{'id':'old','supersedes_id':None,'payload':{'question_id':'q1'}},
             {'id':'new','supersedes_id':'old','payload':{'question_id':'q1'}}]
    rounds=[{'repair_action':'修复连接','retested_at':None,'retest_outcome':None}]
    result=summarize(case(),records,rounds)
    assert (result['recorded'],result['total'],result['state']) == (1,2,'retest_pending')
    closed=summarize(case(True),records,rounds)
    assert closed['state']=='closed' and closed['pending_retests']==1
    with pytest.raises(DomainError,match='继续此病例'): require_open(case(True))
    require_open(case())

def test_retest_never_automatically_closes_case():
    rounds=[{'repair_action':'实际动作','retested_at':'now','retest_outcome':'resolved'}]
    assert summarize(case(),[],rounds)['state']=='retested'
    assert not is_closed(case())
