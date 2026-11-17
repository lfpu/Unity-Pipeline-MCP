# -*- coding: utf-8 -*-
'''HTTP client for the Unity Pipeline editor server (com.unity.pipeline).
Port and token are read from Library/Pipeline/.unity-pipeline-port on every call and never returned to callers.
NOTE: stdout is the MCP protocol channel, never print() here.'''
import json
import os
import socket
import threading
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone

from unity_mcp import config

AUTH_RETRY_DELAY = 1.0


class UnityMcpError(Exception):
    def __init__(self, code, message, hint='', extra=None):
        super().__init__(message)
        self.code = code
        self.hint = hint
        self.extra = extra or {}


_tokens = set()
_exec_lock = threading.Lock()
_opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))


def redact(obj):
    '''Remove every token seen so far from any string / dict / list before it leaves this process.'''
    if isinstance(obj, str):
        for t in _tokens:
            if t and t in obj:
                obj = obj.replace(t, '***')
        return obj
    if isinstance(obj, dict):
        return {k: ('***' if k == 'evalToken' else redact(v)) for k, v in obj.items()}
    if isinstance(obj, list):
        return [redact(x) for x in obj]
    return obj


def brief(payload, limit=1500):
    text = payload if isinstance(payload, str) else json.dumps(payload, ensure_ascii=False, default=str)
    text = redact(text)
    return text if len(text) <= limit else text[:limit] + '...'


def parse_time(s):
    if not s:
        return None
    s = str(s).strip()
    if s.endswith('Z'):
        s = s[:-1] + '+00:00'
    if '.' in s:
        head, rest = s.split('.', 1)
        i = 0
        while i < len(rest) and rest[i].isdigit():
            i += 1
        frac, tail = rest[:i][:6].ljust(6, '0'), rest[i:]
        s = head + '.' + frac + tail
    try:
        dt = datetime.fromisoformat(s)
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def _pid_alive_windows(pid):
    try:
        import ctypes
        k32 = ctypes.WinDLL('kernel32', use_last_error=True)
        h = k32.OpenProcess(0x1000, False, pid)
        if not h:
            return False if ctypes.get_last_error() == 87 else None
        try:
            code = ctypes.c_ulong(0)
            if not k32.GetExitCodeProcess(h, ctypes.byref(code)):
                return None
            return code.value == 259
        finally:
            k32.CloseHandle(h)
    except Exception:
        return None


def pid_alive(pid):
    '''True / False, or None when it cannot be determined. Never os.kill on Windows (signal 0 is CTRL_C there).'''
    try:
        pid = int(pid)
    except (TypeError, ValueError):
        return None
    if pid <= 0:
        return None
    if os.name == 'nt':
        return _pid_alive_windows(pid)
    try:
        os.kill(pid, 0)
        return True
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    except OSError:
        return None


def descriptor_path():
    if not config.PROJECT:
        raise UnityMcpError('project_not_set', '没有设置 Unity 项目路径', '在 MCP 配置的 args 里加上 --project <Unity 项目根目录>')
    return os.path.join(config.PROJECT, 'Library', 'Pipeline', '.unity-pipeline-port')


def read_descriptor(check_pid=True):
    path = descriptor_path()
    if not os.path.isfile(path):
        raise UnityMcpError('port_file_missing', '找不到端口文件: ' + path,
                            'Unity Editor 可能没有打开该项目，或项目里没有安装 com.unity.pipeline 包')
    try:
        with open(path, 'r', encoding='utf-8-sig') as f:
            d = json.load(f)
    except (OSError, ValueError) as exc:
        raise UnityMcpError('port_file_unreadable', '读取端口文件失败: ' + type(exc).__name__, 'Editor 可能正在写入该文件，稍后重试')
    if not isinstance(d, dict):
        raise UnityMcpError('port_file_unreadable', '端口文件格式不是 JSON 对象', '')
    tok = d.get('evalToken')
    if tok:
        _tokens.add(str(tok))
    if check_pid and pid_alive(d.get('pid')) is False:
        raise UnityMcpError('editor_not_running', 'Editor 进程已退出 (pid %s)，端口文件是旧的' % d.get('pid'), '请重新打开该 Unity 项目')
    return d


def http_port(d):
    for ep in d.get('endpoints') or []:
        if isinstance(ep, dict) and ep.get('type') == 'http' and ep.get('port'):
            return int(ep['port'])
    if d.get('port'):
        return int(d['port'])
    raise UnityMcpError('port_file_unreadable', '端口文件里没有 http 端口', '')


def _timeout_error():
    return UnityMcpError('timeout', '等待 Unity 响应超时',
                         '请到 Editor 里看有没有模态对话框卡住了它，或者加大 timeoutMs；Editor 正在编译时也会变慢')


def _request(method, path, d, body=None, timeout=10.0):
    port = http_port(d)
    url = 'http://127.0.0.1:%d%s' % (port, path)
    headers = {'Authorization': 'Bearer ' + str(d.get('evalToken') or ''), 'Accept': 'application/json'}
    data = None
    if body is not None:
        data = json.dumps(body, ensure_ascii=False).encode('utf-8')
        headers['Content-Type'] = 'application/json; charset=utf-8'
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with _opener.open(req, timeout=timeout) as resp:
            status, raw = resp.status, resp.read()
    except urllib.error.HTTPError as exc:
        status, raw = exc.code, exc.read()
    except urllib.error.URLError as exc:
        if isinstance(exc.reason, (socket.timeout, TimeoutError)):
            raise _timeout_error()
        raise UnityMcpError('server_unreachable', '连接不上 Unity Pipeline 服务 (127.0.0.1:%d)' % port,
                            '确认 Editor 已打开，并在 Window > Pipeline > Start Server 里启动服务')
    except (socket.timeout, TimeoutError):
        raise _timeout_error()
    except OSError:
        raise UnityMcpError('server_unreachable', '连接 Unity Pipeline 服务出错 (127.0.0.1:%d)' % port, '确认 Editor 已打开且服务在运行')
    text = raw.decode('utf-8', errors='replace')
    try:
        payload = json.loads(text) if text.strip() else None
    except ValueError:
        payload = text
    return status, payload


def api(method, path, body=None, timeout=10.0):
    '''Returns (http_status, payload). On 401 re-reads the port file once (token rotated / Editor restarted).'''
    d = read_descriptor()
    status, payload = _request(method, path, d, body, timeout)
    if status == 401:
        time.sleep(AUTH_RETRY_DELAY)
        d = read_descriptor()
        status, payload = _request(method, path, d, body, timeout)
        if status == 401:
            raise UnityMcpError('auth_failed', '认证失败 (401)，重读端口文件后仍然无效',
                                '重启 Unity Editor 后再试；token 只在 Editor 进程存活期间有效')
    return status, payload


def exec_command(command, parameters, timeout_ms):
    '''Only one command runs at a time (the Unity server executes them one by one anyway).'''
    body = {'command': command, 'parameters': parameters or {}, 'timeout': timeout_ms}
    with _exec_lock:
        return api('POST', '/api/exec', body, timeout=timeout_ms / 1000.0 + 15.0)
