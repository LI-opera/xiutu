"""Check versioned resources and upload candidates without printing secret values."""
import json
import re
import subprocess
import sys
from pathlib import Path
from urllib.parse import quote

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / "backend")]


def main():
    from scripts.publish_independent_templates import preflight
    from scripts.seed_area_references import DEFAULT_PACKAGE, build_documents, load_manuals

    result = preflight(ROOT / "resources/templates/tayron-v2/relations.json")
    result["manuals"] = len(list(build_documents(DEFAULT_PACKAGE, load_manuals())))
    command = ["git", "-c", f"safe.directory={ROOT.as_posix()}", "ls-files", "--cached", "--others", "--exclude-standard", "-z"]
    names = sorted(set(subprocess.check_output(command, cwd=ROOT).decode("utf-8").split("\0")) - {""})
    private_values = set()
    private_env = ROOT / ".env"
    if private_env.is_file():
        for line in private_env.read_text(encoding="utf-8-sig").splitlines():
            if "=" in line and not line.lstrip().startswith("#"):
                name, value = line.split("=", 1)
                if name.strip() in {"DEEPSEEK_API_KEY", "OPERATOR_TOKEN", "XIUTU_DB_PASSWORD"}:
                    value = value.strip().strip("\"'")
                    if len(value) >= 8:
                        private_values.add(value)
    private_db = ROOT / ".local-data/wp01-postgres.json"
    if private_db.is_file():
        value = json.loads(private_db.read_text(encoding="utf-8"))["password"]
        if len(value) >= 8:
            private_values.update((value, quote(value, safe="")))
    patterns = [re.compile(r"\b(?:ghp_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{40,}|sk-[A-Za-z0-9]{24,})\b"),
                re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----")]
    blocked = []
    for name in names:
        path = ROOT / name
        parts = path.relative_to(ROOT).parts
        if (parts[0] in {".local-data", ".venv", ".test-runs", ".verification"}
                or "node_modules" in parts or "evidence" in parts
                or path.name == ".env" or path.suffix.lower() in {".dump", ".backup", ".sqlite", ".db"}):
            blocked.append({"file": name, "reason": "private_or_generated"})
            continue
        if not path.is_file():
            continue
        if path.stat().st_size > 25 * 1024 * 1024:
            blocked.append({"file": name, "reason": "large_artifact"})
        if path.suffix.lower() in {".png", ".jpg", ".jpeg", ".ico", ".woff", ".woff2"}:
            continue
        content = path.read_text(encoding="utf-8", errors="replace")
        if any(value in content for value in private_values) or any(pattern.search(content) for pattern in patterns):
            blocked.append({"file": name, "reason": "credential_match"})
    result.update(candidate_files=len(names), blocked=blocked)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if blocked:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
