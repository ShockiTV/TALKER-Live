#!/usr/bin/env python3
"""MCP Lua test runner for TALKER Expanded.

Exposes the Lua test suite (LuaUnit-based) as MCP tools so AI coding agents
can discover and run tests without needing shell access.

Registered in .vscode/mcp.json and .claude/settings.json as 'lua-tests'.

Tools provided:
  list_tests          - discover test_*.lua files
  run_tests           - run a set of test files, aggregate results
  run_single_test     - run one test file, return full output
  get_last_run_results - read cached results from most recent run
"""

import asyncio
import dataclasses
import functools
import json
import re
import shutil
import subprocess
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any

from mcp.server import Server
from mcp.server.stdio import stdio_server
import mcp.types as types

# ---------------------------------------------------------------------------
# Paths & constants
# ---------------------------------------------------------------------------

PROJECT_ROOT = Path(__file__).parent
ARTIFACTS_DIR = PROJECT_ROOT / ".test_artifacts" / "lua_last_run"
LUA_FALLBACK = Path(r"C:\Program Files (x86)\LuaRocks\lua5.1.exe")

_SUBPROCESS_TIMEOUT_S = 30

server = Server("lua-tests")
_executor = ThreadPoolExecutor(max_workers=2)


# ---------------------------------------------------------------------------
# Lua interpreter discovery
# ---------------------------------------------------------------------------


def _find_lua() -> str | None:
    """Return path to lua5.1 executable, or None if not found."""
    found = shutil.which("lua5.1")
    if found:
        return found
    if LUA_FALLBACK.exists():
        return str(LUA_FALLBACK)
    return None


# ---------------------------------------------------------------------------
# LuaUnit stdout parser
# ---------------------------------------------------------------------------

# LuaUnit summary line:  "Ran N test(s) in X.XXX seconds, Y success(es), Z failure(s)"
_SUMMARY_RE = re.compile(
    r"Ran (\d+) tests? in [\d.]+ seconds?,\s+(\d+) successes?,\s+(\d+) failures?"
)


def _parse_luaunit_output(stdout: str, stderr: str, returncode: int) -> dict[str, Any]:
    """Parse LuaUnit stdout into a structured result dict.

    Returns keys: passed, failed, errors, output.
    """
    passed = 0
    failed = 0
    errors = 0

    m = _SUMMARY_RE.search(stdout)
    if m:
        # total = int(m.group(1))  # not used directly
        passed = int(m.group(2))
        failed = int(m.group(3))
    elif returncode != 0:
        # No summary line → Lua failed to load (syntax/module error)
        errors = 1

    combined = (stdout + ("\n" + stderr if stderr.strip() else "")).strip()
    return {
        "passed": passed,
        "failed": failed,
        "errors": errors,
        "output": combined,
    }


# ---------------------------------------------------------------------------
# Subprocess runner
# ---------------------------------------------------------------------------


@dataclasses.dataclass
class _ProcResult:
    returncode: int
    stdout: str
    stderr: str
    duration_s: float


def _run_lua_sync(lua_exe: str, test_file: str) -> _ProcResult:
    """Run a single Lua test file synchronously (called from thread pool)."""
    start = time.monotonic()
    try:
        proc = subprocess.run(
            [lua_exe, test_file],
            cwd=PROJECT_ROOT,
            stdin=subprocess.DEVNULL,
            capture_output=True,
            text=True,
            timeout=_SUBPROCESS_TIMEOUT_S,
        )
        return _ProcResult(
            returncode=proc.returncode,
            stdout=proc.stdout,
            stderr=proc.stderr,
            duration_s=round(time.monotonic() - start, 3),
        )
    except subprocess.TimeoutExpired as exc:
        stdout = (
            (exc.stdout or b"").decode(errors="replace")
            if isinstance(exc.stdout, bytes)
            else (exc.stdout or "")
        )
        stderr = (
            (exc.stderr or b"").decode(errors="replace")
            if isinstance(exc.stderr, bytes)
            else (exc.stderr or "")
        )
        return _ProcResult(
            returncode=-1,
            stdout=stdout + f"\n[MCP RUNNER] Killed after {_SUBPROCESS_TIMEOUT_S}s timeout.",
            stderr=stderr,
            duration_s=float(_SUBPROCESS_TIMEOUT_S),
        )


async def _run_lua(lua_exe: str, test_file: str) -> _ProcResult:
    """Run a Lua test file in the thread pool so the event loop stays responsive."""
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(
        _executor, functools.partial(_run_lua_sync, lua_exe, test_file)
    )


# ---------------------------------------------------------------------------
# Discovery helpers
# ---------------------------------------------------------------------------


def _discover_tests(
    path: str = "tests/",
    pattern: str | None = None,
    include_live: bool = False,
) -> list[str]:
    """Return sorted list of test file paths relative to project root.

    Excludes:
      - tests/live/ (unless include_live=True)
      - tests/utils/luaunit.lua (utility, not a test suite)
      - any file under tests/mocks/
    """
    base = PROJECT_ROOT / path
    if not base.exists():
        return []

    files: list[str] = []
    for f in sorted(base.rglob("test_*.lua")):
        rel = f.relative_to(PROJECT_ROOT).as_posix()
        if not include_live and "/live/" in rel:
            continue
        if "luaunit" in f.name.lower():
            continue
        if "/mocks/" in rel:
            continue
        if pattern and pattern.lower() not in f.name.lower():
            continue
        files.append(rel)
    return files


# ---------------------------------------------------------------------------
# Results caching
# ---------------------------------------------------------------------------


def _write_results(results: dict) -> None:
    ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)
    (ARTIFACTS_DIR / "results.json").write_text(
        json.dumps(results, indent=2), encoding="utf-8"
    )


# ---------------------------------------------------------------------------
# MCP helpers
# ---------------------------------------------------------------------------


def _text(data: Any) -> list[types.TextContent]:
    """Wrap data as a single TextContent JSON response."""
    text = json.dumps(data, indent=2) if not isinstance(data, str) else data
    return [types.TextContent(type="text", text=text)]


# ---------------------------------------------------------------------------
# Tool definitions
# ---------------------------------------------------------------------------


@server.list_tools()
async def list_tools() -> list[types.Tool]:
    return [
        types.Tool(
            name="list_tests",
            description=(
                "List all available Lua test files. "
                "Optionally restrict to a subdirectory. "
                "Excludes tests/live/ by default (requires LLM API keys)."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": (
                            "Optional subdirectory to restrict discovery "
                            "(e.g. 'tests/domain/'). Defaults to 'tests/'."
                        ),
                    },
                    "include_live": {
                        "type": "boolean",
                        "description": "Include tests/live/ tests (default: false).",
                    },
                },
            },
        ),
        types.Tool(
            name="run_tests",
            description=(
                "Run Lua test files and return structured results. "
                "Results are also written to .test_artifacts/lua_last_run/results.json."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Restrict to a subdirectory (e.g. 'tests/domain/'). Defaults to 'tests/'.",
                    },
                    "pattern": {
                        "type": "string",
                        "description": "Filter test file names by substring (e.g. 'serializer').",
                    },
                    "include_live": {
                        "type": "boolean",
                        "description": "Include tests/live/ tests (default: false).",
                    },
                    "fail_fast": {
                        "type": "boolean",
                        "description": "Stop after the first file that has failures or errors.",
                    },
                },
            },
        ),
        types.Tool(
            name="run_single_test",
            description=(
                "Run a single Lua test file and return its full output. "
                "Results are written to .test_artifacts/lua_last_run/results.json."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "file": {
                        "type": "string",
                        "description": (
                            "Relative path to the test file from the project root "
                            "(e.g. 'tests/domain/data/test_mutant_names.lua')."
                        ),
                    },
                },
                "required": ["file"],
            },
        ),
        types.Tool(
            name="get_last_run_results",
            description=(
                "Read cached results from the last run_tests or run_single_test call "
                "(.test_artifacts/lua_last_run/results.json). Does not re-execute tests."
            ),
            inputSchema={"type": "object", "properties": {}},
        ),
    ]


# ---------------------------------------------------------------------------
# Tool dispatch
# ---------------------------------------------------------------------------


@server.call_tool()
async def call_tool(
    name: str, arguments: dict[str, Any]
) -> list[types.TextContent]:
    if name == "list_tests":
        return await _handle_list_tests(arguments)
    if name == "run_tests":
        return await _handle_run_tests(arguments)
    if name == "run_single_test":
        return await _handle_run_single_test(arguments)
    if name == "get_last_run_results":
        return await _handle_get_last_run_results(arguments)
    raise ValueError(f"Unknown tool: {name}")


# ---------------------------------------------------------------------------
# Tool implementations
# ---------------------------------------------------------------------------


async def _handle_list_tests(args: dict) -> list[types.TextContent]:
    files = _discover_tests(
        path=args.get("path", "tests/"),
        include_live=args.get("include_live", False),
    )
    return _text({"tests": files, "count": len(files)})


async def _handle_run_tests(args: dict) -> list[types.TextContent]:
    lua_exe = _find_lua()
    if not lua_exe:
        return _text({"error": "lua5.1 not found on PATH or at default location"})

    files = _discover_tests(
        path=args.get("path", "tests/"),
        pattern=args.get("pattern"),
        include_live=args.get("include_live", False),
    )
    fail_fast: bool = args.get("fail_fast", False)

    total_passed = 0
    total_failed = 0
    total_errors = 0
    total_duration = 0.0
    files_run_count = 0
    files_failed: list[str] = []
    failures: list[dict] = []

    for test_file in files:
        files_run_count += 1
        proc = await _run_lua(lua_exe, test_file)
        parsed = _parse_luaunit_output(proc.stdout, proc.stderr, proc.returncode)

        total_passed += parsed["passed"]
        total_failed += parsed["failed"]
        total_errors += parsed["errors"]
        total_duration += proc.duration_s

        file_bad = parsed["failed"] > 0 or parsed["errors"] > 0 or proc.returncode not in (0, 1)
        if file_bad:
            files_failed.append(test_file)
            failures.append({"file": test_file, "output": parsed["output"]})
            if fail_fast:
                break

    result: dict[str, Any] = {
        "passed": total_passed,
        "failed": total_failed,
        "errors": total_errors,
        "duration_s": round(total_duration, 3),
        "files_run": files_run_count,
        "files_failed": files_failed,
        "failures": failures,
        "returncode": 1 if (total_failed + total_errors) > 0 else 0,
    }
    _write_results(result)
    return _text(result)


async def _handle_run_single_test(args: dict) -> list[types.TextContent]:
    test_file: str = args["file"]
    full_path = PROJECT_ROOT / test_file
    if not full_path.exists():
        return _text({"error": f"File not found: {test_file}"})

    lua_exe = _find_lua()
    if not lua_exe:
        return _text({"error": "lua5.1 not found on PATH or at default location"})

    proc = await _run_lua(lua_exe, test_file)
    parsed = _parse_luaunit_output(proc.stdout, proc.stderr, proc.returncode)

    bad = parsed["failed"] > 0 or parsed["errors"] > 0 or proc.returncode not in (0, 1)
    result: dict[str, Any] = {
        "file": test_file,
        "passed": parsed["passed"],
        "failed": parsed["failed"],
        "errors": parsed["errors"],
        "duration_s": proc.duration_s,
        "returncode": proc.returncode,
        "output": parsed["output"],
        "files_run": 1,
        "files_failed": [test_file] if bad else [],
        "failures": [{"file": test_file, "output": parsed["output"]}] if bad else [],
    }
    _write_results(result)
    return _text(result)


async def _handle_get_last_run_results(args: dict) -> list[types.TextContent]:
    results_file = ARTIFACTS_DIR / "results.json"
    if not results_file.exists():
        return _text(
            {"error": "No results found. Run tests first with run_tests or run_single_test."}
        )
    try:
        return _text(json.loads(results_file.read_text(encoding="utf-8")))
    except Exception as exc:
        return _text({"error": f"Failed to read results: {exc}"})


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
