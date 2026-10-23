from sqlalchemy import func, select, tuple_

from app.domain.schemas import CaseSnapshot
from app.infrastructure.orm import cases


# Only explicit purpose labels, never the old automatically populated synthetic/demo flags.
# Ordinary complaints such as "路试测试时无力" must remain in the daily list.
TEST_CASE_LABEL = (
    r"^[ \t\r\n]*(【[^】]*(测试|模拟|验收|验证|demo|stub)[^】]*】"
    r"|\[[^\]]*(测试|模拟|验收|验证|demo|stub)[^\]]*\]"
    r"|(测试病例|模拟病例|验收病例|验证病例|独立流程核对病例)[：: \t]"
    r"|(synthetic|demo|stub)([ :：_-]|$))"
)


class CaseRepository:
    def __init__(self, connection):
        self.connection = connection

    def create(self, actor_id, data, intake_snapshot):
        return (
            self.connection.execute(
                cases.insert()
                .values(
                    owner_id=actor_id,
                    vehicle_json=data.vehicle.model_dump(mode="json"),
                    fault_description=data.fault_description,
                    fault_codes=data.fault_codes,
                    intake_snapshot=intake_snapshot,
                    revision=0,
                    status="draft",
                )
                .returning(cases)
            )
            .mappings()
            .one()
        )

    def get(self, actor_id, case_id):
        return (
            self.connection.execute(
                select(cases).where(cases.c.owner_id == actor_id, cases.c.id == case_id)
            )
            .mappings()
            .one_or_none()
        )

    def list(self, actor_id, limit, cursor=None, scope='all'):
        query = select(cases).where(cases.c.owner_id == actor_id)
        if scope not in {'all', 'daily', 'test'}:
            raise ValueError('Invalid history scope')
        if scope != 'all':
            labelled_test = func.lower(cases.c.fault_description).regexp_match(TEST_CASE_LABEL)
            query = query.where(labelled_test if scope == 'test' else ~labelled_test)
        if cursor:
            query = query.where(tuple_(cases.c.created_at, cases.c.id) < tuple_(*cursor))
        return (
            self.connection.execute(
                query.order_by(cases.c.created_at.desc(), cases.c.id.desc()).limit(limit + 1)
            )
            .mappings()
            .all()
        )


def snapshot(row):
    fields = {
        k: row[k]
        for k in [
            "id",
            "fault_description",
            "fault_codes",
            "intake_snapshot",
            "revision",
            "status",
            "created_at",
            "updated_at",
        ]
    }
    return CaseSnapshot(
        vehicle=row["vehicle_json"],
        experience={"category": "reference", "label": "历史参考",
                    "guidance": "正在核对病例状态。", "priority": 50},
        **fields,
    ).model_dump(mode="json")
