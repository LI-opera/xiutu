"""One bounded Compose startup and real permissions/MCP check on isolated fixtures.

Never retries container startup, rebuilds a database, changes old credentials or deletes volumes.
Run with the project venv/PYTHONPATH after building a NEW code-matching image.
"""

import argparse
import asyncio
import hashlib
import json
import os
import socket
import subprocess
import time
from datetime import datetime
from pathlib import Path
from uuid import uuid4

import httpx
from app.infrastructure.mcp_client import ClientConfig, ManualMCPClient
from app.mcp_server.config import ServerConfig, read_config

ROOT = Path(__file__).resolve().parents[2]


def verify(server_path, client_path, image, output):
    cfg = read_config(server_path, ServerConfig)
    client = read_config(client_path, ClientConfig)
    assert cfg.retrieval_profile == "synthetic" and cfg.database.name.startswith("xiutu_test_")
    assert cfg.authenticate("Bearer " + client.token.get_secret_value()) == client.binding
    output.mkdir()  # New evidence directory only; never overwrite a failed run.
    private = server_path.parent / ("compose-" + uuid4().hex)
    private.mkdir(mode=0o700)
    secret = private / "server-secret.json"
    project = "xiutu-wp08-fix-" + uuid4().hex[:12]
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    model, manuals = cfg.embedding_path, cfg.data_path
    body = cfg.model_dump(mode="json")
    body["database"]["password"] = cfg.database.password.get_secret_value()
    body["database"]["deployment"] = "compose"
    body.update(
        embedding_path="/models/e5",
        data_path="/manuals",
        hosts=[f"127.0.0.1:{port}", "127.0.0.1:8031", "manual-mcp:8031"],
    )
    secret.write_text(json.dumps(body), encoding="utf8")
    if os.name != "nt":
        secret.chmod(0o600)
    secrets = [cfg.database.password.get_secret_value(), client.token.get_secret_value()]
    commands, probes = [], []
    env = dict(
        os.environ,
        XIUTU_DB_PASSWORD="unused-config-placeholder",
        MANUAL_MCP_CONFIG_FILE=str(secret),
        MANUAL_MCP_MODEL_PATH=str(model),
        MANUAL_MCP_DATA_PATH=str(manuals),
        MANUAL_MCP_DEBUG_PORT=str(port),
    )

    def safe(raw):
        for value in secrets:
            raw = raw.replace(value, "<redacted>")
        return raw

    def save():
        (output / "commands.json").write_text(json.dumps(commands, indent=2), encoding="utf8")
        (output / "probes.json").write_text(json.dumps(probes, indent=2), encoding="utf8")

    def run(args, timeout=20):
        start = datetime.now().astimezone().isoformat()
        p = subprocess.run(
            args,
            cwd=ROOT,
            env=env,
            capture_output=True,
            text=True,
            encoding="utf8",
            errors="replace",
            timeout=timeout,
        )
        commands.append(
            dict(
                command=args,
                start=start,
                end=datetime.now().astimezone().isoformat(),
                exit=p.returncode,
                output=safe(p.stdout + p.stderr),
            )
        )
        save()
        assert p.returncode == 0, "See command evidence; no credential-bearing exceptions printed"
        return p.stdout

    # Inspect only existing database/network; never create or recreate either.
    postgres = json.loads(
        run(
            [
                "docker",
                "inspect",
                "xiutu-v5-postgres-1",
                "--format",
                '{"labels":{{json .Config.Labels}},"state":{{json .State}}}',
            ]
        )
    )
    assert postgres["labels"]["com.docker.compose.project"] == "xiutu-v5"
    assert postgres["labels"]["com.docker.compose.service"] == "postgres"
    assert postgres["state"]["Running"] and postgres["state"]["Health"]["Status"] == "healthy"
    network = json.loads(run(["docker", "network", "inspect", "xiutu-v5_default"]))[0]
    assert network["Labels"]["com.docker.compose.project"] == "xiutu-v5"
    image_info = json.loads(run(["docker", "image", "inspect", image]))[0]
    assert (
        image_info["Id"]
        != "sha256:19557fb97b20ca5cc263a7f63dc14fd085a6dfe77944b57ffe9881d6001ad054"
    )
    assert not run(
        [
            "docker",
            "ps",
            "-a",
            "--filter",
            "label=com.docker.compose.project=" + project,
            "--format",
            "{{.ID}}",
        ]
    ).strip()
    # Derive actual hardening/mount config from released Compose, not a hand-written substitute.
    base = ["docker", "compose", "-f", "deploy/compose.yaml"]
    normal = json.loads(run(base + ["--profile", "manual-mcp", "config", "--format", "json"]))
    debug = json.loads(
        run(
            base
            + [
                "-f",
                "deploy/compose.mcp-debug.yaml",
                "--profile",
                "manual-mcp",
                "config",
                "--format",
                "json",
            ]
        )
    )
    service = debug["services"]["manual-mcp"]
    assert not normal["services"]["manual-mcp"].get("ports")
    assert all(x["host_ip"] == "127.0.0.1" for x in service["ports"])
    service.pop("build", None)
    service.pop("profiles", None)
    service["image"] = image
    service["networks"] = {"database": None}
    compose = dict(
        services={"manual-mcp": service},
        networks={"database": dict(external=True, name="xiutu-v5_default")},
    )
    composefile = output / "compose.json"
    composefile.write_text(json.dumps(compose, indent=2), encoding="utf8")
    command = ["docker", "compose", "-p", project, "-f", str(composefile)]
    ident = None
    started = False
    try:
        # Exactly one startup. A stopped/crashed process is failure, never restarted here.
        deadline = time.monotonic() + 60

        def remaining():
            seconds = deadline - time.monotonic()
            assert seconds > 0, "60-second startup deadline exceeded"
            return seconds

        run(command + ["up", "-d", "--no-build", "--no-deps", "manual-mcp"], timeout=remaining())
        started = True
        ident = run(command + ["ps", "-q", "manual-mcp"], timeout=remaining()).strip()
        assert ident
        while True:
            state = json.loads(
                run(
                    ["docker", "inspect", ident, "--format", "{{json .State}}"],
                    timeout=min(10, remaining()),
                )
            )
            logs = safe(
                run(["docker", "logs", "--tail", "40", ident], timeout=min(10, remaining()))
            )
            attempt = dict(at=datetime.now().astimezone().isoformat(), state=state, logs=logs)
            probes.append(attempt)
            save()
            assert state["Running"], "Container exited; no automatic restart"
            left = remaining()
            try:
                response = httpx.get(
                    f"http://127.0.0.1:{port}/health", trust_env=False, timeout=min(2, left)
                )
                attempt["http_status"] = response.status_code
                if response.status_code == 200:
                    assert response.json()["status"] == "ready"
                    attempt["health"] = response.json()
                    save()
                    break
                assert response.status_code == 503, "Unexpected health rejection"
            except (
                httpx.ConnectError,
                httpx.ConnectTimeout,
                httpx.ReadError,
                httpx.ReadTimeout,
                httpx.RemoteProtocolError,
            ) as exc:
                # Documented startup transport failures only; never suppress assertions/config/SQL failures.
                attempt["transport_error"] = type(exc).__name__
            save()
            assert time.monotonic() < deadline, "60-second startup deadline exceeded"
            time.sleep(min(0.25, max(0, deadline - time.monotonic())))
        state = json.loads(run(["docker", "inspect", ident]))[0]
        assert state["Config"]["Labels"]["com.docker.compose.project"] == project
        assert state["Image"] == image_info["Id"]
        assert state["Config"]["User"] == "10001:10001" and state["HostConfig"]["ReadonlyRootfs"]
        assert "ALL" in state["HostConfig"]["CapDrop"]
        assert "no-new-privileges:true" in state["HostConfig"]["SecurityOpt"]
        assert all(
            not x["RW"]
            for x in state["Mounts"]
            if x["Destination"] in ["/manuals", "/models/e5", "/run/secrets/manual-mcp.json"]
        )
        hashes = json.loads(
            run(
                [
                    "docker",
                    "exec",
                    ident,
                    "python",
                    "-c",
                    "import pathlib,hashlib,json;print(json.dumps({str(p.relative_to('/app')):hashlib.sha256(p.read_bytes()).hexdigest() for p in pathlib.Path('/app/backend').rglob('*.py')}))",
                ]
            )
        )
        assert len(hashes) > 50 and all(
            hashlib.sha256((ROOT / p).read_bytes()).hexdigest() == h for p, h in hashes.items()
        )
        writes = run(
            [
                "docker",
                "exec",
                ident,
                "python",
                "-c",
                "import os,uuid;from pathlib import Path\nassert os.getuid()==10001\nfor root in ['/manuals','/models/e5','/']:\n p=Path(root)/('wp08-probe-'+uuid.uuid4().hex)\n try:\n  with p.open('x') as f:f.write('synthetic probe')\n  p.unlink();raise AssertionError('write unexpectedly succeeded')\n except OSError as e:assert e.errno==30;print(root,e.errno)",
            ]
        )
        denial = run(
            [
                "docker",
                "exec",
                ident,
                "python",
                "-c",
                "from app.mcp_server.config import read_config,ServerConfig;from sqlalchemy import text;from sqlalchemy.exc import DBAPIError\ncfg=read_config('/run/secrets/manual-mcp.json',ServerConfig);e=cfg.database.engine()\nfor q in ['DELETE FROM chunks WHERE false','UPDATE cases SET revision=revision WHERE false','CREATE TABLE wp08_denied(x int)','SELECT * FROM tool_calls LIMIT 1','SELECT * FROM tool_executions LIMIT 1']:\n try:\n  with e.begin() as c:c.execute(text('SET LOCAL transaction_read_only=off'));c.execute(text(q));raise AssertionError('unexpected privilege')\n except DBAPIError as x:assert x.orig.sqlstate=='42501';print(x.orig.sqlstate)\ne.dispose()",
            ]
        )
        remote = client.model_copy(update={"url": f"http://127.0.0.1:{port}/mcp"})
        answers = {}
        for name, arguments in [
            ("search_manuals", dict(query="voltage", vehicle_scope={}, top_k=3)),
            (
                "get_measurement_spec",
                dict(component_key="SYNTHETIC-COMPONENT", quantity="voltage", vehicle_scope={}),
            ),
        ]:
            answers[name] = asyncio.run(ManualMCPClient(remote).exchange(name, arguments))
            assert answers[name]["ok"] and not answers[name]["data"]["empty"]
        chunk = answers["search_manuals"]["data"]["chunks"][0]
        answers["get_evidence_context"] = asyncio.run(
            ManualMCPClient(remote).exchange(
                "get_evidence_context",
                dict(
                    chunk_id=chunk["chunk_id"],
                    document_version_id=chunk["document_version_id"],
                    neighbors=0,
                ),
            )
        )
        assert answers["get_evidence_context"]["data"]["chunks"][0] == chunk
        result = dict(
            project=project,
            container=ident,
            image=image,
            image_id=state["Image"],
            manifest=state.get("ImageManifestDescriptor"),
            default_no_host_port=True,
            debug_loopback_only=True,
            nonroot=True,
            readonly_root=True,
            mounts=state["Mounts"],
            write_probes=writes,
            role_denials=denial,
            answers=answers,
            source_hashes=hashes,
            startup_attempts=len(probes),
            startup_commands=1,
        )
        (output / "results.json").write_text(json.dumps(result, indent=2), encoding="utf8")
        print("New-image Compose health/three tools, role denial and readonly mounts passed")
    finally:
        if started:
            # Only this new project service; never down, rm, postgres or volume deletion.
            if ident:
                run(["docker", "logs", "--tail", "100", ident])
            run(command + ["stop", "manual-mcp"])
        save()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--server-config", type=Path, required=True)
    parser.add_argument("--client-config", type=Path, required=True)
    parser.add_argument("--image", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    verify(args.server_config, args.client_config, args.image, args.output)


if __name__ == "__main__":
    main()
