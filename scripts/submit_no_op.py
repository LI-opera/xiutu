"""Local operator CLI: synthetic background task only, NOT diagnosis or ingestion."""

import argparse
from uuid import UUID, uuid4

from app.config import Settings
from app.infrastructure.uow import make_engine
from app.services.run_service import RunService


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--case-id", type=UUID)
    parser.add_argument("--expected-revision", type=int)
    parser.add_argument("--seconds", type=float, default=10)
    parser.add_argument("--key", default=None)
    args = parser.parse_args()
    settings = Settings()
    engine = make_engine(
        settings.database_url.get_secret_value() if settings.database_url else None
    )
    try:
        _, body = RunService(engine).submit_no_op(
            settings.operator_id,
            {"seconds": args.seconds},
            args.key or uuid4().hex,
            args.case_id,
            args.expected_revision,
        )
        print(body["run_id"])
    finally:
        if engine is not None:
            engine.dispose()


if __name__ == "__main__":
    main()
