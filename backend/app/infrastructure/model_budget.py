"""Explicitly initialized, cross-process, conservative paid-attempt ledger."""

import hashlib
import json
import os
import tempfile
from contextlib import contextmanager
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

METERED_POLICY = "metered_no_cumulative_cap"
MAX_MODEL_OUTPUT_TOKENS = 16384  # Local resource ceiling, not a paid-call authorization.

ROOT = Path(__file__).resolve().parents[3]
LIVE_LEDGER = ROOT / ".local-data/wp09-budget.json"


class BudgetError(Exception):
    pass


@contextmanager
def exclusive(path):
    lock = Path(str(path) + ".lock")
    with lock.open("a+b") as f:
        f.seek(0)
        f.write(b"0")
        f.flush()
        f.seek(0)
        if os.name == "nt":
            import msvcrt

            msvcrt.locking(f.fileno(), msvcrt.LK_LOCK, 1)
        else:
            import fcntl

            fcntl.flock(f, fcntl.LOCK_EX)
        try:
            yield
        finally:
            f.seek(0)
            if os.name == "nt":
                msvcrt.locking(f.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(f, fcntl.LOCK_UN)


class BudgetLedger:
    def __init__(self, path):
        self.path = Path(path)

    def initialize(self, authorization):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with exclusive(self.path):
            with self.path.open("x", encoding="utf8") as f:
                json.dump(
                    dict(
                        version=2,
                        authorization=authorization,
                        policy=METERED_POLICY,
                        historical_limit_cny=None,
                        reserved_cny="0",
                        calls={},
                    ),
                    f,
                )

    def read(self):
        try:
            d = json.loads(self.path.read_text(encoding="utf8"))
        except (OSError, ValueError) as exc:
            raise BudgetError("BUDGET_LEDGER_INVALID") from exc
        if not isinstance(d, dict):
            raise BudgetError("BUDGET_LEDGER_INVALID")
        if d.get("version") == 1:
            valid = d.get("limit_cny") == "5"
        elif d.get("version") == 2:
            valid = d.get("policy") == METERED_POLICY
        else:
            valid = False
        try:
            amount = Decimal(d["reserved_cny"])
            valid = valid and amount.is_finite() and amount >= 0
        except (KeyError, TypeError, ValueError, ArithmeticError):
            valid = False
        if not valid or not isinstance(d.get("calls"), dict) or "authorization" not in d:
            raise BudgetError("BUDGET_LEDGER_INVALID")
        return d

    def migrate_to_metered(self):
        """One explicit, locked v1->v2 change with an intact private rollback copy."""
        with exclusive(self.path):
            old = self.read()
            if old["version"] == 2:
                return None
            raw = self.path.read_bytes()
            backup_fd, backup_name = tempfile.mkstemp(
                prefix=self.path.name + ".v1-backup-", suffix=".json",
                dir=self.path.parent,
            )
            with os.fdopen(backup_fd, "wb") as backup:
                backup.write(raw)
                backup.flush()
                os.fsync(backup.fileno())
            updated = dict(old)
            updated["version"] = 2
            updated["policy"] = METERED_POLICY
            updated["historical_limit_cny"] = updated.pop("limit_cny")
            updated["policy_authorized_at"] = datetime.now(timezone.utc).isoformat()
            self.save(updated)
            return Path(backup_name)

    def save(self, d):
        fd, n = tempfile.mkstemp(prefix="budget-", dir=self.path.parent)
        try:
            with os.fdopen(fd, "w", encoding="utf8") as f:
                json.dump(d, f, indent=2)
                f.flush()
                os.fsync(f.fileno())
            os.replace(n, self.path)
        finally:
            if os.path.exists(n):
                os.unlink(n)

    def reserve(self, key, model, payload, max_output, *, input_profile="default"):
        if model != "deepseek-flash":
            raise BudgetError("MODEL_PRICE_UNVERIFIED")
        if input_profile not in {"default", "matched_areas"}:
            raise BudgetError("MODEL_INPUT_PROFILE_INVALID")
        size = len(payload.encode("utf8"))
        if (input_profile == "default" and size > 100000) or not 1 <= max_output <= MAX_MODEL_OUTPUT_TOKENS:
            raise BudgetError("MODEL_INPUT_LIMIT")
        # UTF8-byte upper bound with 4x framing safety plus the configured output.
        tokens = size * 4 + max_output
        amount = (Decimal(tokens) * 2 + Decimal(max_output) * 8) / 1000000
        with exclusive(self.path):
            d = self.read()
            if d["version"] != 2:
                raise BudgetError("BUDGET_POLICY_MIGRATION_REQUIRED")
            if key in d["calls"]:
                raise BudgetError("MODEL_CALL_ALREADY_RESERVED")
            total = Decimal(d["reserved_cny"]) + amount
            d["reserved_cny"] = str(total)
            d["calls"][key] = dict(
                status="reserved",
                model=model,
                input_profile=input_profile,
                reserved_cny=str(amount),
                input_upper=tokens,
                output_upper=max_output,
                payload_sha256=hashlib.sha256(payload.encode()).hexdigest(),
                usage=None,
                usage_status="unknown",
                at=datetime.now(timezone.utc).isoformat(),
            )
            self.save(d)

    def finish(self, key, metadata):
        with exclusive(self.path):
            d = self.read()
            row = d["calls"][key]
            if row["status"] != "reserved":
                raise BudgetError("MODEL_CALL_TERMINAL")
            row.update(metadata)
            usage = metadata.get("usage")
            if usage is not None:
                row["usage_status"] = "reported"
                row["peak_cost_upper_cny"] = str(
                    (Decimal(usage["input_tokens"]) * 2 + Decimal(usage["output_tokens"]) * 8)
                    / 1000000
                )
                if (
                    usage["input_tokens"] > row["input_upper"]
                    or usage["output_tokens"] > row["output_upper"]
                ):
                    row["budget_anomaly"] = True
            self.save(d)
