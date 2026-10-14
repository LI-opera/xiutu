"""Explicit one-time migration of the existing private DeepSeek ledger."""

import argparse
import hashlib
from pathlib import Path

from app.infrastructure.model_budget import LIVE_LEDGER, METERED_POLICY, BudgetLedger


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true", help="migrate the existing live ledger")
    args = parser.parse_args()
    if not args.apply:
        parser.error("--apply is required; this script never initializes a ledger")
    path = Path(LIVE_LEDGER)
    if not path.is_file():
        raise FileNotFoundError("Existing live ledger required")
    before_hash = hashlib.sha256(path.read_bytes()).hexdigest()
    before = BudgetLedger(path).read()
    backup = BudgetLedger(path).migrate_to_metered()
    after = BudgetLedger(path).read()
    assert after["version"] == 2 and after["policy"] == METERED_POLICY
    assert after["authorization"] == before["authorization"]
    assert after["reserved_cny"] == before["reserved_cny"]
    assert after["calls"] == before["calls"]
    if backup is not None:
        assert hashlib.sha256(backup.read_bytes()).hexdigest() == before_hash
    print("version_before=" + str(before["version"]))
    print("version_after=" + str(after["version"]))
    print("policy=" + after["policy"])
    print("reserved_cny=" + after["reserved_cny"])
    print("call_count=" + str(len(after["calls"])))
    print("backup_name=" + (backup.name if backup is not None else "already_migrated"))
    print("backup_sha256=" + (before_hash if backup is not None else "not_created"))
    print("ledger_sha256=" + hashlib.sha256(path.read_bytes()).hexdigest())


if __name__ == "__main__":
    main()
