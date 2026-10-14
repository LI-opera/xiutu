"""Bounded API checks for the two browser-created template demo cases. Zero models."""
import json
import argparse
from uuid import uuid4
import httpx

BASE = "http://localhost:5215/api/v2"
CASES = {"P0299": "7d5ac558-e812-4bbf-812f-cae4cbe7860f",
         "P0236": "d9e18ecc-50b3-481b-88da-69c06b26d4d2"}
OLD = "95b92020-ae99-418b-a7e3-b8bb7aa4e776"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--verify-correction', action='store_true', help='Update only the labelled P0299 verification case')
    args = parser.parse_args()
    with httpx.Client(base_url=BASE, trust_env=False, timeout=30) as client:
        session = client.get('/auth/session')
        session.raise_for_status()
        client.headers.update({'Origin': 'http://localhost:5215', 'X-CSRF-Token': session.json()['csrf_token']})
        checks = []
        for code, cid in CASES.items():
            response = client.get(f'/cases/{cid}/workbench-v2')
            response.raise_for_status()
            view = response.json()
            expected = 5 if code == 'P0299' else 3
            assert len(view['topic']['areas']) == expected
            assert view['case']['vehicle']['brand'] == '大众'
            assert view['case']['fault_codes'] == [code]
            assert view['plan']['intake']['symptom_condition'] == 'unprovided'
            if code == 'P0299' and args.verify_correction:
                observed = next(o for o in view['observations'] if o['question_id'] == 'AIR-01' and o['effective'])
                payload = dict(expected_revision=view['case']['revision'], topic_version=view['topic']['version'],
                               question_id='AIR-01', option_ids=['unavailable'], fields={},
                               unavailable_reason='【模拟验收记录】验证更正与刷新；不是实车检查。')
                key = 'template-correction:' + str(uuid4())
                path = f"/cases/{cid}/topic-observations/{observed['id']}/correct"
                saved = client.post(path, json=payload, headers={'Idempotency-Key': key})
                assert saved.status_code == 200, saved.text
                repeated = client.post(path, json=payload, headers={'Idempotency-Key': key})
                assert repeated.status_code == 200, repeated.text
                assert repeated.json()['observation_id'] == saved.json()['observation_id']
                restored = client.get(f'/cases/{cid}/workbench-v2').json()
                assert restored['case']['revision'] == view['case']['revision'] + 1
                assert len([o for o in restored['observations'] if o['effective']]) == 1
                view = restored
            if code == 'P0236':
                forbidden = client.post(f'/cases/{cid}/topic-observations',
                    headers={'Idempotency-Key': 'template-negative:' + str(uuid4())},
                    json={'expected_revision': view['case']['revision'], 'topic_version': view['topic']['version'],
                          'question_id': 'TUR-01', 'option_ids': ['normal']})
                assert forbidden.status_code == 422, forbidden.text
                assert client.get(f'/cases/{cid}').json()['revision'] == view['case']['revision']
            checks.append({'code': code, 'case_id': cid, 'areas': [a['title'] for a in view['topic']['areas']],
                           'revision': view['case']['revision'], 'observations': len(view['observations'])})
        baseline = dict(workbench_flow='template-match-v1', vehicle=dict(brand='大众', model='探岳', year=2019, engine_code='DKVB'),
                        fault_description='模板匹配负面测试：不应创建病例', fault_codes=['P0299'])
        for vehicle_change, codes, expected in [({'year': 2020}, ['P0299'], 'TEMPLATE_NOT_FOUND'),
                ({'engine_code': None}, ['P0299'], 'ENGINE_CONFIRMATION_REQUIRED'),
                ({'brand': '其他品牌'}, ['P0299'], 'TEMPLATE_NOT_FOUND'),
                ({}, ['P0001'], 'TEMPLATE_NOT_FOUND'),
                ({}, ['P0299', 'P0236'], 'MULTIPLE_CODES_NOT_CONFIGURED')]:
            payload = {**baseline, 'vehicle': {**baseline['vehicle'], **vehicle_change}, 'fault_codes': codes}
            result = client.post('/cases', json=payload, headers={'Idempotency-Key': 'template-negative:' + str(uuid4())})
            assert result.status_code == 422 and expected in result.text, result.text
        old = client.get(f'/cases/{OLD}/workbench-v2')
        old.raise_for_status()
        assert old.json()['topic']['version'] == '2.2.1-b02'
        assert len(old.json()['topic']['areas']) == 5
        print(json.dumps({'new_cases': checks, 'negative_matches': 5, 'out_of_subset_write_rejected': True,
                          'old_case_revision': old.json()['case']['revision'], 'model_calls': 0}, ensure_ascii=False, indent=2))


if __name__ == '__main__': main()
