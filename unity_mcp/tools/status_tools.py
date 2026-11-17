# -*- coding: utf-8 -*-
from unity_mcp.service import status
from unity_mcp.tools._common import run


def register(mcp):
    @mcp.tool(description=(
        '查看 Unity Editor 的 Pipeline 服务状态：是否在运行、项目名、Unity 版本、端口、进程是否存活、心跳新旧、可用命令数量和警告。'
        '只读。不会返回 token。其他工具报错（连不上、超时）时先调用它判断 Editor 是否还在。'))
    def unity_status() -> dict:
        return run(status)
