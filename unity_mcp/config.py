# -*- coding: utf-8 -*-
'''Runtime options. Command line first, UNITY_MCP_* environment variables as fallback.
NOTE: stdout is the MCP protocol channel, never print() in this package.'''
import argparse
import os
import sys

COMMAND_CACHE_TTL = 60.0
DRY_RUN_TTL = 300.0
HEARTBEAT_STALE_SEC = 120.0


def _env_bool(name, default):
    v = os.environ.get(name)
    if v is None:
        return default
    return v.strip().lower() in ('1', 'true', 'yes', 'on')


def _env_int(name, default):
    try:
        return int(os.environ.get(name, ''))
    except ValueError:
        return default


def _split(items):
    out = []
    for it in items or []:
        out += [x.strip() for x in str(it).split(',') if x.strip()]
    return out


def _parse():
    p = argparse.ArgumentParser(prog='unity-pipeline-mcp')
    p.add_argument('--project', default=os.environ.get('UNITY_MCP_PROJECT', ''), help='Unity project root directory')
    p.add_argument('--allow-eval', action=argparse.BooleanOptionalAction, default=_env_bool('UNITY_MCP_ALLOW_EVAL', False))
    p.add_argument('--require-dry-run', action=argparse.BooleanOptionalAction, default=_env_bool('UNITY_MCP_REQUIRE_DRY_RUN', True))
    p.add_argument('--timeout-ms', type=int, default=_env_int('UNITY_MCP_TIMEOUT_MS', 60000))
    p.add_argument('--max-chars', type=int, default=_env_int('UNITY_MCP_MAX_CHARS', 8000))
    p.add_argument('--deny', action='append', default=[], help='command name pattern to block')
    p.add_argument('--readonly-pattern', action='append', default=[], help='command name pattern treated as read-only')
    args, _unknown = p.parse_known_args(sys.argv[1:])
    return args


_a = _parse()
def _detect_project():
    '''No --project and no env var: use the Unity project that contains the working directory.'''
    d = os.path.abspath(os.getcwd())
    while True:
        if os.path.isfile(os.path.join(d, 'ProjectSettings', 'ProjectVersion.txt')):
            return d
        parent = os.path.dirname(d)
        if parent == d:
            return ''
        d = parent


PROJECT = os.path.abspath(_a.project) if _a.project else _detect_project()
ALLOW_EVAL = bool(_a.allow_eval)
REQUIRE_DRY_RUN = bool(_a.require_dry_run)
TIMEOUT_MS = max(1000, _a.timeout_ms)
MAX_CHARS = max(200, _a.max_chars)
DENY = _split(_a.deny + [os.environ.get('UNITY_MCP_DENY', '')])
READONLY = _split(_a.readonly_pattern + [os.environ.get('UNITY_MCP_READONLY', '')])
