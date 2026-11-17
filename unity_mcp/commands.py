# -*- coding: utf-8 -*-
'''Command list of the running Editor: fetched from GET /api/commands, normalized and cached.'''
import json
import time

from unity_mcp import config
from unity_mcp.client import UnityMcpError, api, brief, read_descriptor

_cache = {'key': None, 'at': 0.0, 'data': None}


def _normalize(raw):
    schema = raw.get('schema')
    if isinstance(schema, str):
        try:
            schema = json.loads(schema)
        except ValueError:
            schema = None
    if not isinstance(schema, dict):
        schema = {}
    props = schema.get('properties')
    props = dict(props) if isinstance(props, dict) else {}
    required = schema.get('required')
    required = [str(x) for x in required] if isinstance(required, list) else []
    if not props and isinstance(raw.get('parameters'), list):
        for p in raw['parameters']:
            if isinstance(p, dict) and p.get('name'):
                props[str(p['name'])] = p
                if p.get('required'):
                    required.append(str(p['name']))
    tags = raw.get('tags')
    tags = [str(t) for t in tags] if isinstance(tags, list) else []
    name = raw.get('command') or ' '.join(str(x) for x in (raw.get('group'), raw.get('name')) if x)
    return {
        'command': str(name),
        'group': str(raw.get('group') or ''),
        'name': str(raw.get('name') or ''),
        'description': str(raw.get('description') or ''),
        'tags': tags,
        'mainThreadRequired': bool(raw.get('mainThreadRequired')),
        'schema': schema,
        'properties': props,
        'required': required,
        'supportsDryRun': 'dry-run' in props,
    }


def get_commands(refresh=False):
    d = read_descriptor()
    key = (d.get('pid'), d.get('startedAt'))
    now = time.time()
    if (not refresh and _cache['key'] == key and _cache['data'] is not None
            and now - _cache['at'] < config.COMMAND_CACHE_TTL):
        return _cache['data']
    items = []
    for _page in range(20):
        path = '/api/commands' if not items else '/api/commands?offset=%d' % len(items)
        status, payload = api('GET', path, timeout=30.0)
        if status != 200 or not isinstance(payload, dict) or not isinstance(payload.get('commands'), list):
            raise UnityMcpError('server_error', '读取命令列表失败 (HTTP %s)' % status, 'Editor 可能正在编译或重新加载，稍后重试',
                                {'detail': brief(payload)})
        page = [_normalize(c) for c in payload['commands'] if isinstance(c, dict)]
        items += page
        total = payload.get('total')
        if not page or not isinstance(total, int) or len(items) >= total:
            break
    _cache.update({'key': key, 'at': now, 'data': items})
    return items


def find_command(cmds, name):
    want = ' '.join(str(name).split()).lower()
    for c in cmds:
        if c['command'].lower() == want:
            return c
    return None


def clear_cache():
    _cache.update({'key': None, 'at': 0.0, 'data': None})
