# -*- coding: utf-8 -*-
'''unity_status and unity_commands logic. Free of the mcp SDK so it can be tested offline.'''
import difflib
import os
from datetime import datetime, timezone

from unity_mcp import config, policy
from unity_mcp.client import UnityMcpError, parse_time, pid_alive, read_descriptor, redact
from unity_mcp.commands import find_command, get_commands


def status():
    try:
        d = read_descriptor(check_pid=False)
    except UnityMcpError as exc:
        if exc.code == 'project_not_set':
            raise
        return {'ok': True, 'running': False, 'code': exc.code, 'message': str(exc), 'hint': exc.hint}
    alive = pid_alive(d.get('pid'))
    out = {
        'ok': True,
        'running': False,
        'projectName': d.get('projectName'),
        'projectPath': d.get('projectPath'),
        'unityVersion': d.get('unityVersion'),
        'mode': d.get('mode'),
        'port': d.get('port'),
        'pid': d.get('pid'),
        'pidAlive': alive,
        'startedAt': d.get('startedAt'),
    }
    warnings = []
    info = d.get('info')
    if info:
        warnings.append(' '.join(str(info).split()))
    hb = parse_time(d.get('lastHeartbeat'))
    if hb is not None:
        age = (datetime.now(timezone.utc) - hb).total_seconds()
        out['heartbeatAgeSec'] = round(age, 1)
        if age > config.HEARTBEAT_STALE_SEC:
            warnings.append('心跳已经 %d 秒没有更新，Editor 可能在编译、重新加载，或卡在模态对话框上' % int(age))
    pp = d.get('projectPath')
    if pp and os.path.normcase(os.path.abspath(str(pp))) != os.path.normcase(config.PROJECT):
        warnings.append('端口文件里的项目路径与 --project 不一致: ' + str(pp))
    if alive is False:
        out['hint'] = 'Editor 进程已经退出，请重新打开该 Unity 项目'
    else:
        try:
            out['commandCount'] = len(get_commands(refresh=True))
            out['running'] = True
        except UnityMcpError as exc:
            out['code'] = exc.code
            out['message'] = str(exc)
            if exc.hint:
                out['hint'] = exc.hint
    out['warnings'] = warnings
    return redact(out)


def summary(c):
    desc = c['description']
    return {
        'command': c['command'],
        'description': desc if len(desc) <= 200 else desc[:200] + '...',
        'required': c['required'],
        'supportsDryRun': c['supportsDryRun'],
        'mainThreadRequired': c['mainThreadRequired'],
        'eval': policy.is_eval(c),
    }


def not_found(cmds, command):
    names = [c['command'] for c in cmds]
    near = difflib.get_close_matches(' '.join(str(command).split()), names, n=5, cutoff=0.5)
    return UnityMcpError('command_not_found', '命令不存在: ' + str(command),
                         '用 unity_commands 查询准确的命令名（分组 + 空格 + 名称）', {'suggestions': near})


def list_commands(command=None, group=None, keyword=None, limit=30, offset=0, refresh=False):
    cmds = get_commands(refresh=bool(refresh))
    if command:
        info = find_command(cmds, command)
        if info is None:
            raise not_found(cmds, command)
        full = summary(info)
        full.update({'description': info['description'], 'group': info['group'], 'tags': info['tags'],
                     'blocked': policy.is_blocked(info), 'schema': info['schema']})
        return redact({'ok': True, 'command': info['command'], 'detail': full})
    items = cmds
    if group:
        g = str(group).strip().lower()
        items = [c for c in items if c['group'].lower() == g or c['group'].lower().startswith(g + '.')]
    if keyword:
        words = str(keyword).lower().split()
        items = [c for c in items if all(w in (c['command'] + ' ' + c['description']).lower() for w in words)]
    if not group and not keyword:
        counts = {}
        for c in items:
            counts[c['group']] = counts.get(c['group'], 0) + 1
        groups = [{'group': k, 'count': counts[k]} for k in sorted(counts)]
        return {'ok': True, 'total': len(items), 'groups': groups,
                'hint': '用 group 或 keyword 缩小范围，再用 command 查看某个命令的完整参数'}
    limit = min(max(int(limit), 1), 100)
    offset = max(int(offset), 0)
    page = items[offset:offset + limit]
    return redact({'ok': True, 'total': len(items), 'offset': offset, 'limit': limit, 'commands': [summary(c) for c in page]})
