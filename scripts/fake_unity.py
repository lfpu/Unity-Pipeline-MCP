# -*- coding: utf-8 -*-
'''Fake Unity Pipeline server for offline tests (127.0.0.1, random port).'''
import json
import os
import threading
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, HTTPServer

TOKEN = 'SECRET-TOKEN-abc123=='
STATE = {'token': TOKEN, 'exec_log': [], 'always_401': False}

SCHEMA = {
    'type': 'object',
    'properties': {'controller': {'type': 'string'}, 'name': {'type': 'string'}, 'dry-run': {'type': 'boolean'}},
    'required': ['controller', 'name'],
    'additionalProperties': False,
}
RO_SCHEMA = {'type': 'object', 'properties': {'path': {'type': 'string'}}, 'required': [], 'additionalProperties': False}
EVAL_SCHEMA = {'type': 'object', 'properties': {}}


def _cmd(command, group, name, desc, schema):
    return {'command': command, 'name': name, 'group': group, 'description': desc, 'tags': [],
            'mainThreadRequired': True, 'parameters': [], 'schema': json.dumps(schema)}


COMMANDS = [
    _cmd('animation.animator add_layer', 'animation.animator', 'add_layer', 'Add a layer to an AnimatorController.', SCHEMA),
    _cmd('editor status', 'editor', 'status', 'Editor status.', RO_SCHEMA),
    _cmd('eval run', 'eval', 'run', 'Run C# code.', EVAL_SCHEMA),
]


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def _send(self, code, obj):
        raw = json.dumps(obj).encode('utf-8')
        self.send_response(code)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def _authed(self):
        if STATE['always_401']:
            return False
        return self.headers.get('Authorization') == 'Bearer ' + STATE['token']

    def do_GET(self):
        if not self._authed():
            return self._send(401, {'error': 'unauthorized'})
        if self.path.startswith('/api/commands'):
            return self._send(200, {'commands': COMMANDS, 'count': len(COMMANDS), 'total': len(COMMANDS), 'offset': 0})
        self._send(404, {'error': 'not found'})

    def do_POST(self):
        if not self._authed():
            return self._send(401, {'error': 'unauthorized'})
        size = int(self.headers.get('Content-Length', '0'))
        body = json.loads(self.rfile.read(size) or b'{}')
        if self.path != '/api/exec':
            return self._send(404, {'error': 'not found'})
        STATE['exec_log'].append(body)
        path = (body.get('parameters') or {}).get('path')
        if body.get('command') == 'editor status' and path == 'boom':
            return self._send(200, {'success': False, 'error': 'boom failed'})
        if body.get('command') == 'editor status' and path == 'big':
            return self._send(200, {'data': 'x' * 50000})
        self._send(200, {'success': True, 'result': 'done', 'echo': body.get('parameters')})


def start_server():
    srv = HTTPServer(('127.0.0.1', 0), Handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv, srv.server_address[1]


def write_descriptor(project, port, pid):
    d = os.path.join(project, 'Library', 'Pipeline')
    os.makedirs(d, exist_ok=True)
    now = datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%S.0000000Z')
    data = {'pid': pid, 'port': port, 'projectPath': project, 'projectName': 'Fake', 'unityVersion': '6000.0.0f1',
            'mode': 'editor', 'startedAt': '2026-01-01T00:00:00.0000000Z', 'lastHeartbeat': now,
            'evalToken': STATE['token'], 'info': 'not automated.', 'endpoints': [{'type': 'http', 'port': port}]}
    with open(os.path.join(d, '.unity-pipeline-port'), 'w', encoding='utf-8') as f:
        json.dump(data, f)
