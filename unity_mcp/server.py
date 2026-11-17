# -*- coding: utf-8 -*-
import importlib
import pkgutil

# mcp SDK v2 renamed FastMCP -> MCPServer (mcp.server.mcpserver); v1 uses mcp.server.fastmcp.FastMCP.
try:
    from mcp.server.mcpserver import MCPServer as _Server
except ImportError:
    from mcp.server.fastmcp import FastMCP as _Server

from unity_mcp import tools as tools_pkg

mcp = _Server('unity-pipeline')


def register_all():
    for m in pkgutil.iter_modules(tools_pkg.__path__):
        if m.name.startswith('_'):
            continue
        mod = importlib.import_module('unity_mcp.tools.' + m.name)
        reg = getattr(mod, 'register', None)
        if reg:
            reg(mcp)


def main():
    register_all()
    mcp.run()


if __name__ == '__main__':
    main()
