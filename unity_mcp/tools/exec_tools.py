# -*- coding: utf-8 -*-
from typing import Optional

from unity_mcp.execution import run_exec
from unity_mcp.tools._common import run


def register(mcp):
    @mcp.tool(description=(
        '在 Unity Editor 里执行一个 Pipeline 命令（会修改项目，需要谨慎）。command 必须与 unity_commands 返回的命令名完全一致，'
        '例如 animation.animator add_layer；parameters 的键名用 schema 里的短横线写法，例如 blending-mode。'
        '支持 dry-run 的写操作必须先用 dryRun=true 调一次（只校验、不写入），参数完全相同再正式执行。'
        'Eval 类命令默认禁用。一次只执行一个命令。超时时先用 unity_status 检查 Editor 是否卡在对话框上。'))
    def unity_exec(command: str, parameters: Optional[dict] = None, dryRun: bool = False,
                   timeoutMs: Optional[int] = None) -> dict:
        return run(run_exec, command=command, parameters=parameters, dryRun=dryRun, timeoutMs=timeoutMs)
