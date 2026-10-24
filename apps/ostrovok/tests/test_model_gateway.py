"""Exercise the gateway at its real process boundary, without provider traffic."""

import asyncio
import importlib
import importlib.util
import json
import os
from pathlib import Path
import sys

import pytest


def gateway_class():
    name = "apps.ostrovok.backend.app.agent.model_gateway"
    assert importlib.util.find_spec(name) is not None, (
        "The free-only model gateway is missing"
    )
    return importlib.import_module(name).ModelGateway


def executable(tmp_path, body):
    path = tmp_path / "fake-opencode"
    path.write_text("#!" + sys.executable + "\n" + body)
    path.chmod(0o700)
    return str(path)


def run_extract(gateway, message="Москва на 2 ночи", intent=None):
    return asyncio.run(
        gateway.extract(message, intent or {}, "2026-10-24T12:00:00+03:00")
    )


def test_offline_mode_returns_explicit_unavailable_without_spawning(monkeypatch):
    monkeypatch.setenv("LLM_MODE", "offline")
    monkeypatch.setenv("OPENCODE_BIN", "/must-not-be-executed")
    result = run_extract(gateway_class()())
    assert result == {"patch": {}, "model": None, "used": False, "reason": "offline"}


def test_paid_model_is_rejected_before_spawning(monkeypatch):
    monkeypatch.setenv("LLM_MODE", "opencode")
    monkeypatch.setenv("OPENCODE_MODEL", "opencode/deepseek-v4.1-flash")
    monkeypatch.setenv("OPENCODE_BIN", "/must-not-be-executed")
    result = run_extract(gateway_class()())
    assert result["used"] is False
    assert result["patch"] == {}
    assert result["reason"] == "paid_or_unapproved_model"


def test_success_parses_patch_and_process_receives_no_secrets_or_order_identifiers(
    tmp_path, monkeypatch
):
    capture = tmp_path / "capture.json"
    body = (
        "import json, os, pathlib, sys\n"
        f"pathlib.Path({str(capture)!r}).write_text(json.dumps({{'args':sys.argv, 'env':dict(os.environ), 'cwd':os.getcwd(), 'config':json.loads((pathlib.Path(os.environ['XDG_CONFIG_HOME'])/'opencode/opencode.json').read_text())}}))\n"
        "print(json.dumps({'type':'text','part':{'type':'text','text':json.dumps({'origin':'moscow','adults':2})}}))\n"
        "print(json.dumps({'type':'step_finish','part':{'cost':0,'finish':'stop'}}))\n"
    )
    monkeypatch.setenv("LLM_MODE", "opencode")
    monkeypatch.delenv("OPENCODE_MODEL", raising=False)
    monkeypatch.setenv("OPENCODE_BIN", executable(tmp_path, body))
    monkeypatch.setenv("OPENCODE_API_KEY", "secret-do-not-inherit")
    monkeypatch.setenv("OPENAI_API_KEY", "another-secret")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "unrelated-secret")
    result = run_extract(
        gateway_class()(),
        intent={
            "origin": None,
            "session_id": "SESSION_PRIVATE",
            "order_id": "ORDER_PRIVATE",
        },
    )
    assert result == {
        "patch": {"origin": "moscow", "adults": 2},
        "model": "opencode/deepseek-v4.1-flash-free",
        "used": True,
        "reason": None,
    }
    observed = json.loads(capture.read_text())
    assert not any(
        k in observed["env"]
        for k in ("OPENCODE_API_KEY", "OPENAI_API_KEY", "AWS_SECRET_ACCESS_KEY")
    )
    assert "SESSION_PRIVATE" not in json.dumps(observed)
    assert "ORDER_PRIVATE" not in json.dumps(observed)
    assert observed["args"][1:3] == ["run", "--standalone"]
    assert "--auto" not in observed["args"]
    assert Path(observed["cwd"]) != Path.cwd()
    config = observed["config"]
    assert {"action": "tool.use", "resource": "*", "effect": "deny"} in config[
        "policies"
    ]
    for agent in ("travel", "title", "summary", "compaction"):
        assert config["agents"][agent]["model"] == "opencode/deepseek-v4.1-flash-free"


def test_http_403_is_unavailable_and_not_a_fake_model_success(tmp_path, monkeypatch):
    count = tmp_path / "attempts"
    body = (
        "import json, pathlib\n"
        f"with pathlib.Path({str(count)!r}).open('a') as f: f.write('attempt\\n')\n"
        "print(json.dumps({'type':'step_start','part':{'type':'step-start'}}))\n"
        "print(json.dumps({'type':'error','error':{'type':'provider.auth','status':403,'message':'FreeTierError'}}))\n"
        "raise SystemExit(1)\n"
    )
    monkeypatch.setenv("LLM_MODE", "opencode")
    monkeypatch.delenv("OPENCODE_MODEL", raising=False)
    monkeypatch.setenv("OPENCODE_BIN", executable(tmp_path, body))
    result = run_extract(gateway_class()())
    assert result["used"] is False
    assert result["patch"] == {}
    assert result["reason"] == "free_model_unavailable"
    assert count.read_text().count("attempt") == 1


def test_transient_primary_failure_tries_only_approved_free_fallback(
    tmp_path, monkeypatch
):
    body = (
        "import json, sys\n"
        "model=sys.argv[sys.argv.index('--model')+1]\n"
        "if model=='opencode/deepseek-v4.1-flash-free':\n"
        " print(json.dumps({'type':'error','error':{'status':503,'message':'Unavailable'}})); raise SystemExit(1)\n"
        "print(json.dumps({'type':'text','part':{'type':'text','text':'{\"adults\":2}'}}))\n"
    )
    monkeypatch.setenv("LLM_MODE", "opencode")
    monkeypatch.delenv("OPENCODE_MODEL", raising=False)
    monkeypatch.setenv("OPENCODE_BIN", executable(tmp_path, body))
    result = run_extract(gateway_class()())
    assert result == {
        "patch": {"adults": 2},
        "model": "opencode/glm-5.3-flash-free",
        "used": True,
        "reason": None,
    }


@pytest.mark.parametrize(
    "text",
    [
        "not json",
        '{"session_id":"evil"}',
        '{"adults":"two"}',
        '{"adults":999}',
        '[{"adults":2}]',
        '{"pet_kg":' + "9" * 500 + "}",
    ],
)
def test_malformed_or_unapproved_patch_never_enters_intent(tmp_path, monkeypatch, text):
    body = (
        "import json\nprint(json.dumps({'type':'text','part':{'type':'text','text':"
        + repr(text)
        + "}}))\n"
    )
    monkeypatch.setenv("LLM_MODE", "opencode")
    monkeypatch.delenv("OPENCODE_MODEL", raising=False)
    monkeypatch.setenv("OPENCODE_BIN", executable(tmp_path, body))
    result = run_extract(gateway_class()())
    assert result["patch"] == {}
    assert result["used"] is False
    assert result["reason"] == "invalid_model_output"


def test_excessive_process_output_is_stopped_before_parsing(tmp_path, monkeypatch):
    body = "import sys\nsys.stdout.write('x'*300000)\nsys.stdout.flush()\n"
    monkeypatch.setenv("LLM_MODE", "opencode")
    monkeypatch.delenv("OPENCODE_MODEL", raising=False)
    monkeypatch.setenv("OPENCODE_BIN", executable(tmp_path, body))
    result = run_extract(gateway_class()())
    assert result["patch"] == {}
    assert result["used"] is False
    assert result["reason"] == "model_output_limit"


def test_nonzero_reported_cost_stops_without_accepting_output(tmp_path, monkeypatch):
    body = "import json\nprint(json.dumps({'type':'text','part':{'text':'{\"adults\":2}'}}))\nprint(json.dumps({'type':'step_finish','part':{'cost':0.001}}))\n"
    monkeypatch.setenv("LLM_MODE", "opencode")
    monkeypatch.delenv("OPENCODE_MODEL", raising=False)
    monkeypatch.setenv("OPENCODE_BIN", executable(tmp_path, body))
    result = run_extract(gateway_class()())
    assert result["used"] is False
    assert result["reason"] == "unexpected_model_cost"


def test_nested_usage_cost_is_not_ignored(tmp_path, monkeypatch):
    body = "import json\nprint(json.dumps({'type':'text','part':{'text':'{\"adults\":2}'},'usage':{'cost':0.01}}))\n"
    monkeypatch.setenv("LLM_MODE", "opencode")
    monkeypatch.delenv("OPENCODE_MODEL", raising=False)
    monkeypatch.setenv("OPENCODE_BIN", executable(tmp_path, body))
    result = run_extract(gateway_class()())
    assert result["used"] is False
    assert result["reason"] == "unexpected_model_cost"


def test_pet_presence_and_return_deadline_are_valid_partial_intent_fields(
    tmp_path, monkeypatch
):
    body = "import json\nprint(json.dumps({'type':'text','part':{'text':'{\"pet_requested\":true,\"return_by\":\"2026-11-14\"}'}}))\n"
    monkeypatch.setenv("LLM_MODE", "opencode")
    monkeypatch.delenv("OPENCODE_MODEL", raising=False)
    monkeypatch.setenv("OPENCODE_BIN", executable(tmp_path, body))
    result = run_extract(gateway_class()())
    assert result["used"] is True
    assert result["patch"] == {"pet_requested": True, "return_by": "2026-11-14"}


def test_timeout_terminates_process_group_and_returns_bounded_failure(
    tmp_path, monkeypatch
):
    pidfile = tmp_path / "child-pid"
    body = (
        "import pathlib, subprocess, sys, time\n"
        "child=subprocess.Popen([sys.executable,'-c','import time; time.sleep(60)'])\n"
        f"pathlib.Path({str(pidfile)!r}).write_text(str(child.pid))\n"
        "time.sleep(60)\n"
    )
    monkeypatch.setenv("LLM_MODE", "opencode")
    monkeypatch.delenv("OPENCODE_MODEL", raising=False)
    monkeypatch.setenv("OPENCODE_BIN", executable(tmp_path, body))
    result = run_extract(gateway_class()(timeout_seconds=0.3))
    assert result["used"] is False
    assert result["reason"] == "model_timeout"
    assert pidfile.exists(), "The test must actually launch a child before timing out"
    proc = Path("/proc") / pidfile.read_text()
    # A short-lived orphan zombie is already terminated and cannot perform work.
    assert not proc.exists() or ") Z " in (proc / "stat").read_text()
