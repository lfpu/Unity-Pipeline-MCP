# -*- coding: utf-8 -*-
'''List the tools registered by the MCP server (no Unity needed).  python scripts/list_tools.py'''
import asyncio
import inspect
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.argv = ['x', '--project', os.getcwd()]

from unity_mcp.server import mcp, register_all  # noqa: E402


def main():
    register_all()
    fn = getattr(mcp, 'list_tools', None)
    if fn is None:
        print('SDK object has no list_tools(); attributes:', [a for a in dir(mcp) if 'tool' in a.lower()])
        return 1
    res = fn()
    if inspect.isawaitable(res):
        res = asyncio.run(res)
    tools = getattr(res, 'tools', res)
    names = sorted(getattr(t, 'name', str(t)) for t in tools)
    for t in sorted(tools, key=lambda x: getattr(x, 'name', '')):
        schema = getattr(t, 'inputSchema', None) or getattr(t, 'input_schema', None) or {}
        print('%s  params=%s' % (getattr(t, 'name', t), sorted((schema.get('properties') or {}).keys())))
    expected = ['unity_commands', 'unity_exec', 'unity_status']
    print('OK' if names == expected else 'UNEXPECTED: %s' % names)
    return 0 if names == expected else 1


if __name__ == '__main__':
    sys.exit(main())
