# -*- coding: utf-8 -*-
'''Policy, error mapping, token rotation, dead pid and server down.'''
import os

from checks import check


def run(c):
    err, ex, fake, cfg, cl = c.err, c.execution, c.fake, c.config, c.client

    e = err(ex.run_exec, 'eval run', {})
    check('eval blocked by default', e is not None and e.code == 'blocked_by_policy', e and e.code)
    cfg.ALLOW_EVAL = True
    r = ex.run_exec('eval run', {})
    check('eval allowed with --allow-eval', r['ok'], r)
    cfg.ALLOW_EVAL = False

    cfg.DENY = ['editor *']
    e = err(ex.run_exec, 'editor status', {})
    check('deny list blocks', e is not None and e.code == 'blocked_by_policy', e and e.code)
    cfg.DENY = []

    e = err(ex.run_exec, 'editor status', {'path': 'boom'})
    check('success:false payload -> command_failed', e is not None and e.code == 'command_failed', e and e.code)
    r = ex.run_exec('editor status', {'path': 'big'})
    check('big result is truncated to max-chars', r['truncated'] is True and len(r['result']) <= 1000, len(str(r['result'])))

    old = fake.STATE['token']
    fake.STATE['token'] = 'NEW-TOKEN-xyz'
    fake.write_descriptor(c.project, c.port, os.getpid())
    r = ex.run_exec('editor status', {'path': 'a'})
    check('rotated token is picked up from the port file', r['ok'], r)
    fake.STATE['always_401'] = True
    e = err(ex.run_exec, 'editor status', {'path': 'a'})
    check('persistent 401 -> auth_failed', e is not None and e.code == 'auth_failed', e and e.code)
    fake.STATE['always_401'] = False
    check('redact removes every known token', cl.redact('t=' + old + ' u=' + fake.STATE['token']) == 't=*** u=***')

    fake.write_descriptor(c.project, c.port, 99999999)
    e = err(ex.run_exec, 'editor status', {'path': 'a'})
    check('dead pid -> editor_not_running', e is not None and e.code == 'editor_not_running', e and e.code)
    s = c.service.status()
    check('status with dead pid -> running False', s['running'] is False and s['pidAlive'] is False, s)

    c.srv.shutdown()
    c.srv.server_close()
    fake.write_descriptor(c.project, c.port, os.getpid())
    e = err(ex.run_exec, 'editor status', {'path': 'a'})
    check('server down -> server_unreachable', e is not None and e.code == 'server_unreachable', e and e.code)
