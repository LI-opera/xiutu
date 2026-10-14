import argparse
import importlib
import json
import sys
from pathlib import Path
from uuid import UUID

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

Settings = importlib.import_module("app.config").Settings
create_app = importlib.import_module("app.main").create_app


OUTPUT = ROOT / "docs" / "api" / "openapi.wp14.json"


def render() -> str:
    app = create_app(
        Settings(
            _env_file=None,
            app_mode="test",
            retrieval_profile="formal",
            database_url=None,
            data_path=ROOT / ".local-data" / "openapi-export",
            operator_id=UUID("00000000-0000-4000-8000-000000000014"),
            operator_token="openapi-export-token-value-000014",
            app_origin="http://localhost:5214",
            deepseek_api_key=None,
            tool_mode="local",
        )
    )
    return json.dumps(app.openapi(), ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    expected = render()
    if args.check:
        if not OUTPUT.exists() or OUTPUT.read_text(encoding="utf-8") != expected:
            print(f"OpenAPI drift: run {Path(__file__).name}", file=sys.stderr)
            return 1
        print(f"OpenAPI current: {OUTPUT.relative_to(ROOT)}")
        return 0
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(expected, encoding="utf-8", newline="\n")
    print(OUTPUT.relative_to(ROOT))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
