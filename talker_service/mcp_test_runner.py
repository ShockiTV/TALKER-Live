#!/usr/bin/env python3
"""MCP test runner for TALKER e2e tests.

Exposes pytest execution and test inspection as MCP tools so agents can run
tests and inspect captured payloads without needing shell access.

Registered in .claude/settings.json as mcpServers.talker-tests.
"""

import ast
import asyncio
import dataclasses
import functools
import json
import subprocess
import sys
import textwrap
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any

from mcp.server import Server
from mcp.server.stdio import stdio_server
import mcp.types as types

# Paths relative to this file
SERVICE_DIR = Path(__file__).parent
ARTIFACTS_DIR = SERVICE_DIR / ".test_artifacts" / "last_run"
SCENARIOS_DIR = SERVICE_DIR / "tests" / "e2e" / "scenarios"

server = Server("talker-tests")

# Thread pool for running subprocess without blocking the event loop.
_executor = ThreadPoolExecutor(max_workers=2)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

# Hard cap: if the entire pytest run exceeds this, kill it and return what we have.
_SUBPROCESS_TIMEOUT_S = 30


@dataclasses.dataclass
class _ProcResult:
    returncode: int
    stdout: str
    stderr: str


def _run_pytest_sync(*pytest_args: str) -> _ProcResult:
    """Run pytest as a blocking subprocess (called from thread pool)."""
    try:
        proc = subprocess.run(
            [sys.executable, "-m", "pytest", *pytest_args],
            cwd=SERVICE_DIR,
            stdin=subprocess.DEVNULL,
            capture_output=True,
            text=True,
            timeout=_SUBPROCESS_TIMEOUT_S,
        )
        return _ProcResult(
            returncode=proc.returncode,
            stdout=proc.stdout,
            stderr=proc.stderr,
        )
    except subprocess.TimeoutExpired as exc:
        stdout = (exc.stdout or b"").decode(errors="replace") if isinstance(exc.stdout, bytes) else (exc.stdout or "")
        stderr = (exc.stderr or b"").decode(errors="replace") if isinstance(exc.stderr, bytes) else (exc.stderr or "")
        return _ProcResult(
            returncode=-1,
            stdout=stdout + f"\n[MCP RUNNER] Subprocess killed after {_SUBPROCESS_TIMEOUT_S}s timeout.",
            stderr=stderr,
        )


async def _run_pytest(*pytest_args: str) -> _ProcResult:
    """Run pytest in a thread pool so the event loop stays responsive."""
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(
        _executor, functools.partial(_run_pytest_sync, *pytest_args)
    )


def _text(data: Any) -> list[types.TextContent]:
    """Wrap data as a single TextContent JSON response."""
    text = json.dumps(data, indent=2) if not isinstance(data, str) else data
    return [types.TextContent(type="text", text=text)]


def _extract_function_source(file_path: Path, func_name: str) -> str | None:
    """Return source lines of func_name from file_path using AST."""
    try:
        source = file_path.read_text(encoding="utf-8")
        tree = ast.parse(source)
        lines = source.splitlines()
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                if node.name == func_name:
                    start = node.lineno - 1
                    end = node.end_lineno
                    return textwrap.dedent("\n".join(lines[start:end]))
    except Exception:
        pass
    return None


# ---------------------------------------------------------------------------
# Tool definitions
# ---------------------------------------------------------------------------

@server.list_tools()
async def list_tools() -> list[types.Tool]:
    return [
        types.Tool(
            name="list_tests",
            description=(
                "List all available pytest test node IDs. "
                "Optionally restrict to a path or subdirectory."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Optional path to restrict collection (e.g. 'tests/e2e/')",
                    }
                },
            },
        ),
        types.Tool(
            name="run_tests",
            description=(
                "Run pytest and return structured results. "
                "Results are also written to .test_artifacts/last_run/results.json."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "pattern": {
                        "type": "string",
                        "description": "Test name pattern passed to -k flag",
                    },
                    "path": {
                        "type": "string",
                        "description": "Test file or directory path",
                    },
                    "verbose": {
                        "type": "boolean",
                        "description": "Enable verbose output (-v)",
                    },
                    "fail_fast": {
                        "type": "boolean",
                        "description": "Stop on first failure (-x)",
                    },
                },
            },
        ),
        types.Tool(
            name="run_single_test",
            description=(
                "Run a single test by node ID with full traceback. "
                "Results are written to .test_artifacts/last_run/results.json."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "node_id": {
                        "type": "string",
                        "description": "Full pytest node ID (e.g. 'tests/e2e/test_scenarios.py::test_e2e_scenario[death_wolf_full]')",
                    }
                },
                "required": ["node_id"],
            },
        ),
        types.Tool(
            name="get_test_source",
            description=(
                "Extract source code of a specific test function. "
                "For parametrized e2e scenario tests, also returns the scenario JSON under 'scenario_file'."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "node_id": {
                        "type": "string",
                        "description": "Full pytest node ID",
                    }
                },
                "required": ["node_id"],
            },
        ),
        types.Tool(
            name="get_last_run_results",
            description="Read cached results from the last pytest run (.test_artifacts/last_run/results.json).",
            inputSchema={"type": "object", "properties": {}},
        ),
        types.Tool(
            name="get_captured_payloads",
            description=(
                "Read wire-level payloads captured during the last e2e test run "
                "(.test_artifacts/last_run/payloads.json). "
                "Includes state_queries, http_calls, and ws_published per test."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "test_id": {
                        "type": "string",
                        "description": "Optional test node ID to filter (exact match or substring)",
                    }
                },
            },
        ),
    ]


# ---------------------------------------------------------------------------
# Tool implementations
# ---------------------------------------------------------------------------

@server.call_tool()
async def call_tool(
    name: str, arguments: dict[str, Any]
) -> list[types.TextContent]:
    if name == "list_tests":
        return await _list_tests(arguments)
    if name == "run_tests":
        return await _run_tests(arguments)
    if name == "run_single_test":
        return await _run_single_test(arguments)
    if name == "get_test_source":
        return await _get_test_source(arguments)
    if name == "get_last_run_results":
        return await _get_last_run_results(arguments)
    if name == "get_captured_payloads":
        return await _get_captured_payloads(arguments)
    raise ValueError(f"Unknown tool: {name}")


async def _list_tests(args: dict) -> list[types.TextContent]:
    extra = [args["path"]] if args.get("path") else []
    proc = await _run_pytest("--collect-only", "-q", "--no-header", *extra)

    tests = []
    for line in proc.stdout.splitlines():
        line = line.strip()
        # Lines with "::" are node IDs; skip summary/warning lines
        if "::" in line and not line.startswith(("=", "WARN", "ERROR")):
            tests.append(line)

    return _text({"tests": tests, "count": len(tests)})


async def _run_tests(args: dict) -> list[types.TextContent]:
    ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)
    results_file = ARTIFACTS_DIR / "results.json"

    # Remove stale results so we never return data from a previous run.
    if results_file.exists():
        results_file.unlink()

    extra: list[str] = []
    if args.get("pattern"):
        extra += ["-k", args["pattern"]]
    if args.get("path"):
        extra.append(args["path"])
    if args.get("verbose"):
        extra.append("-v")
    if args.get("fail_fast"):
        extra.append("-x")

    proc = await _run_pytest(
        "--json-report",
        f"--json-report-file={results_file}",
        *extra,
    )

    result: dict[str, Any] = {
        "returncode": proc.returncode,
        "passed": 0,
        "failed": 0,
        "errors": 0,
        "duration_s": 0.0,
        "failures": [],
        "stdout": proc.stdout[-2000:] if len(proc.stdout) > 2000 else proc.stdout,
    }

    if results_file.exists():
        try:
            data = json.loads(results_file.read_text())
            summary = data.get("summary", {})
            result["passed"] = summary.get("passed", 0)
            result["failed"] = summary.get("failed", 0)
            result["errors"] = summary.get("error", 0)
            result["duration_s"] = round(data.get("duration", 0.0), 3)
            for test in data.get("tests", []):
                if test.get("outcome") in ("failed", "error"):
                    result["failures"].append(
                        {
                            "nodeid": test.get("nodeid"),
                            "outcome": test.get("outcome"),
                            "longrepr": (test.get("call") or {}).get("longrepr", ""),
                        }
                    )
        except Exception as exc:
            result["parse_error"] = str(exc)

    return _text(result)


async def _run_single_test(args: dict) -> list[types.TextContent]:
    ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)
    results_file = ARTIFACTS_DIR / "results.json"
    node_id: str = args["node_id"]

    # Remove stale results so we never return data from a previous run.
    if results_file.exists():
        results_file.unlink()

    proc = await _run_pytest(
        node_id,
        "--tb=long",
        "-v",
        "--json-report",
        f"--json-report-file={results_file}",
    )

    result: dict[str, Any] = {
        "node_id": node_id,
        "returncode": proc.returncode,
        "passed": False,
        "outcome": "unknown",
        "longrepr": "",
        "stdout": (proc.stdout + proc.stderr).strip(),
    }

    if results_file.exists():
        try:
            data = json.loads(results_file.read_text())
            tests = data.get("tests", [])
            if tests:
                t = tests[0]
                result["outcome"] = t.get("outcome", "unknown")
                result["passed"] = result["outcome"] == "passed"
                result["longrepr"] = (t.get("call") or {}).get("longrepr", "")
        except Exception as exc:
            result["parse_error"] = str(exc)

    return _text(result)


async def _get_test_source(args: dict) -> list[types.TextContent]:
    node_id: str = args["node_id"]

    # node_id: "path/to/test_file.py::ClassName::func_name[param]"
    parts = node_id.split("::")
    file_part = parts[0]
    func_part = parts[-1] if len(parts) > 1 else ""

    # Strip parametrize brackets
    scenario_key: str | None = None
    if "[" in func_part:
        func_name = func_part[: func_part.index("[")]
        scenario_key = func_part[func_part.index("[") + 1 : func_part.rindex("]")]
    else:
        func_name = func_part

    file_path = SERVICE_DIR / file_part
    if not file_path.exists():
        return _text({"error": f"File not found: {file_part}"})

    source = _extract_function_source(file_path, func_name)

    result: dict[str, Any] = {
        "node_id": node_id,
        "file": file_part,
        "function": func_name,
        "source": source or f"# Function '{func_name}' not found in {file_part}",
    }

    # For parametrized e2e scenario tests, attach the scenario JSON
    if scenario_key and "e2e" in file_part:
        scenario_file = SCENARIOS_DIR / f"{scenario_key}.json"
        if scenario_file.exists():
            try:
                result["scenario_file"] = json.loads(
                    scenario_file.read_text(encoding="utf-8")
                )
            except Exception as exc:
                result["scenario_file_error"] = str(exc)

    return _text(result)


async def _get_last_run_results(args: dict) -> list[types.TextContent]:
    results_file = ARTIFACTS_DIR / "results.json"
    if not results_file.exists():
        return _text({"error": "No results found. Run tests first with run_tests or run_single_test."})

    try:
        data = json.loads(results_file.read_text())
        # Return a concise summary rather than the full (potentially very large) report
        return _text(
            {
                "created": data.get("created"),
                "duration_s": round(data.get("duration", 0.0), 3),
                "summary": data.get("summary", {}),
                "tests": [
                    {
                        "nodeid": t.get("nodeid"),
                        "outcome": t.get("outcome"),
                        "duration_s": round((t.get("call") or {}).get("duration", 0.0), 3),
                        "longrepr": (t.get("call") or {}).get("longrepr", "") if t.get("outcome") != "passed" else "",
                    }
                    for t in data.get("tests", [])
                ],
            }
        )
    except Exception as exc:
        return _text({"error": f"Failed to read results: {exc}"})


async def _get_captured_payloads(args: dict) -> list[types.TextContent]:
    payloads_file = ARTIFACTS_DIR / "payloads.json"
    if not payloads_file.exists():
        return _text(
            {"error": "No payloads found. Run e2e tests first."}
        )

    try:
        data = json.loads(payloads_file.read_text())
    except Exception as exc:
        return _text({"error": f"Failed to read payloads: {exc}"})

    test_id = args.get("test_id")
    if not test_id:
        return _text(data)

    # Exact match first, then substring
    if test_id in data:
        return _text({test_id: data[test_id]})

    matches = {k: v for k, v in data.items() if test_id in k}
    if matches:
        return _text(matches)

    return _text({"error": f"No payloads found for test_id '{test_id}'"})


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

async def main() -> None:
    async with stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            server.create_initialization_options(),
        )


if __name__ == "__main__":
    asyncio.run(main())
