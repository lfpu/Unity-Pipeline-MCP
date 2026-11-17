# -*- coding: utf-8 -*-
from typing import Optional

from unity_mcp.service import list_commands
from unity_mcp.tools._common import run


def register(mcp):
    @mcp.tool(description=(
        '检索 Unity Pipeline 的可用命令（只读）。无参数时返回所有分组及命令数量；'
        'group 按分组过滤（含子分组）；keyword 在命令名和说明里检索（空格分隔多个词，需全部命中）；'
        'command 精确指定一个命令，返回它完整的参数 schema（含必填项、是否支持 dry-run）。'
        '摘要里只有名称、说明和必填参数，不会一次返回所有 schema。refresh=true 强制重新读取（刚新增了脚本命令时用）。'))
    def unity_commands(command: Optional[str] = None, group: Optional[str] = None, keyword: Optional[str] = None,
                       limit: int = 30, offset: int = 0, refresh: bool = False) -> dict:
        return run(list_commands, command=command, group=group, keyword=keyword, limit=limit, offset=offset, refresh=refresh)
