# -*- coding: utf-8 -*-
from unity_mcp.client import UnityMcpError, redact


def run(fn, *args, **kwargs):
    '''Call service logic and always return a dict with ok=true/false. The token never leaves through here.'''
    try:
        return fn(*args, **kwargs)
    except UnityMcpError as exc:
        out = {'ok': False, 'code': exc.code, 'message': redact(str(exc))}
        if exc.hint:
            out['hint'] = exc.hint
        if exc.extra:
            out.update(redact(exc.extra))
        return out
    except Exception as exc:
        return {'ok': False, 'code': 'internal_error', 'message': redact('%s: %s' % (type(exc).__name__, exc))}
