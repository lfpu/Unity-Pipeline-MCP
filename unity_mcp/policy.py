# -*- coding: utf-8 -*-
'''Execution policy: deny list, Eval gate, read-only patterns and the dry-run-before-write rule.'''
import fnmatch
import json
import re
import time

from unity_mcp import config
from unity_mcp.client import UnityMcpError

_dry = {}


def _match(name, patterns):
    n = name.lower()
    return any(fnmatch.fnmatch(n, p.lower()) for p in patterns)


def is_eval(info):
    '''The real name of the Eval command is not confirmed; match the word eval in the command name or tags.'''
    words = re.split(r'[^a-z0-9]+', info['command'].lower())
    if 'eval' in words:
        return True
    return any('eval' in t.lower() for t in info.get('tags', []))


def is_denied(info):
    return _match(info['command'], config.DENY)


def is_readonly(info):
    return _match(info['command'], config.READONLY)


def is_blocked(info):
    return is_denied(info) or (is_eval(info) and not config.ALLOW_EVAL)


def check_allowed(info):
    if is_denied(info):
        raise UnityMcpError('blocked_by_policy', '命令在黑名单中: ' + info['command'], '用户在启动参数 --deny 里禁用了它')
    if is_eval(info) and not config.ALLOW_EVAL:
        raise UnityMcpError('blocked_by_policy', 'Eval 类命令默认禁用: ' + info['command'],
                            '它能执行任意 C# 代码；确认风险后再用 --allow-eval 开启')


def _key(command, params):
    p = {k: v for k, v in (params or {}).items() if k != 'dry-run'}
    return command + '|' + json.dumps(p, sort_keys=True, ensure_ascii=False, default=str)


def mark_dry_run(command, params):
    _dry[_key(command, params)] = time.time()


def has_recent_dry_run(command, params):
    ts = _dry.get(_key(command, params))
    return ts is not None and time.time() - ts <= config.DRY_RUN_TTL


def clear_dry_run(command, params):
    _dry.pop(_key(command, params), None)


def needs_dry_run(info, dry):
    '''A real call to a write command that supports dry-run must be preceded by a matching dry-run.'''
    return (not dry) and config.REQUIRE_DRY_RUN and info['supportsDryRun'] and not is_readonly(info)
