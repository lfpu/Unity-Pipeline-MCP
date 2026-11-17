# -*- coding: utf-8 -*-
'''unity_exec logic: validation, policy, dry-run rule, HTTP call, result packing.'''
import json
import time

from unity_mcp import config, policy
from unity_mcp.client import UnityMcpError, brief, exec_command, redact
from unity_mcp.commands import find_command, get_commands
from unity_mcp.service import not_found


def _message(payload):
    if isinstance(payload, dict):
        for k in ('message', 'error', 'detail'):
            v = payload.get(k)
            if isinstance(v, str) and v:
                return v
            if isinstance(v, dict) and v.get('message'):
                return str(v['message'])
    return None


def _looks_failed(payload):
    '''The /api/exec response shape is not confirmed; treat explicit failure markers as failure.'''
    if isinstance(payload, dict):
        if payload.get('success') is False or payload.get('ok') is False:
            return True
        if payload.get('error'):
            return True
    return False


def _raise_for_status(status, payload):
    if 200 <= status < 300:
        return
    msg = _message(payload) or ('HTTP %d' % status)
    extra = {'detail': brief(payload)}
    if status == 404:
        raise UnityMcpError('command_not_found', msg, '用 unity_commands 查询准确的命令名', extra)
    if status in (400, 422):
        raise UnityMcpError('invalid_parameters', msg, '用 unity_commands 指定 command 查看参数说明', extra)
    if status == 413:
        raise UnityMcpError('payload_too_large', msg, '请求体太大，减少参数内容', extra)
    if status in (408, 504):
        raise UnityMcpError('timeout', msg, '检查 Editor 是否卡在模态对话框，或加大 timeoutMs', extra)
    raise UnityMcpError('server_error', msg, '', extra)


def _pack(payload):
    payload = redact(payload)
    text = payload if isinstance(payload, str) else json.dumps(payload, ensure_ascii=False, default=str)
    if len(text) > config.MAX_CHARS:
        return text[:config.MAX_CHARS], True
    return payload, False


def _validate(info, params):
    missing = [k for k in info['required'] if k not in params]
    if missing:
        raise UnityMcpError('invalid_parameters', '缺少必填参数: ' + ', '.join(missing),
                            '用 unity_commands 指定 command 查看完整参数说明', {'missing': missing})
    if info['properties'] and info['schema'].get('additionalProperties') is False:
        unknown = [k for k in params if k not in info['properties']]
        if unknown:
            raise UnityMcpError('invalid_parameters', '不认识的参数: ' + ', '.join(unknown),
                                '参数名区分大小写，并且使用短横线写法', {'unknown': unknown})


def run_exec(command, parameters=None, dryRun=False, timeoutMs=None):
    if not isinstance(command, str) or not command.strip():
        raise UnityMcpError('invalid_parameters', 'command 不能为空')
    if parameters is not None and not isinstance(parameters, dict):
        raise UnityMcpError('invalid_parameters', 'parameters 必须是对象')
    cmds = get_commands()
    info = find_command(cmds, command)
    if info is None:
        raise not_found(cmds, command)
    policy.check_allowed(info)
    params = dict(parameters or {})
    dry = bool(dryRun) or params.get('dry-run') is True
    _validate(info, params)
    if dry:
        if not info['supportsDryRun']:
            raise UnityMcpError('dry_run_unsupported', '该命令没有 dry-run 参数: ' + info['command'],
                                '去掉 dryRun；这类命令要么只读，要么没有试运行模式')
        params['dry-run'] = True
    elif policy.needs_dry_run(info, dry) and not policy.has_recent_dry_run(info['command'], params):
        raise UnityMcpError('dry_run_required', '写操作需要先 dry-run: ' + info['command'],
                            '先用相同参数调用一次 dryRun=true，通过后再正式执行')
    timeout_ms = int(timeoutMs) if timeoutMs else config.TIMEOUT_MS
    timeout_ms = min(max(timeout_ms, 1000), 3600000)
    t0 = time.time()
    status_code, payload = exec_command(info['command'], params, timeout_ms)
    ms = int((time.time() - t0) * 1000)
    _raise_for_status(status_code, payload)
    if _looks_failed(payload):
        raise UnityMcpError('command_failed', _message(payload) or '命令执行失败', '', {'detail': brief(payload)})
    if dry:
        policy.mark_dry_run(info['command'], params)
    else:
        policy.clear_dry_run(info['command'], params)
    result, truncated = _pack(payload)
    return {'ok': True, 'command': info['command'], 'dryRun': dry, 'durationMs': ms, 'result': result, 'truncated': truncated}
