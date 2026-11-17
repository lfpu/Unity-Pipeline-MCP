# -*- coding: utf-8 -*-
'''Status, command search and the dry-run rule.'''
import json
import os

from checks import check

P = {'controller': 'Assets/A.controller', 'name': 'L2'}


def run(c):
    err, svc, ex, fake = c.err, c.service, c.execution, c.fake
    s = svc.status()
    check('status without port file -> running False', s.get('running') is False, s)
    e = err(ex.run_exec, 'editor status')
    check('exec without port file -> port_file_missing', e is not None and e.code == 'port_file_missing', e and e.code)

    fake.write_descriptor(c.project, c.port, os.getpid())
    s = svc.status()
    check('status running with 3 commands', s.get('running') is True and s.get('commandCount') == 3, s)
    check('status never contains the token', fake.TOKEN not in json.dumps(s) and 'evalToken' not in json.dumps(s))
    check('status carries the info warning', any('not automated' in w for w in s.get('warnings', [])), s)

    r = svc.list_commands()
    check('list groups', r['total'] == 3 and {g['group'] for g in r['groups']} == {'animation.animator', 'editor', 'eval'}, r)
    r = svc.list_commands(group='animation')
    check('list by parent group prefix', r['total'] == 1, r)
    r = svc.list_commands(keyword='layer animator')
    check('list by keyword (all words must match)', r['total'] == 1, r)
    r = svc.list_commands(command='animation.animator add_layer')
    check('command detail has schema and dry-run flag', r['detail']['schema']['required'] == ['controller', 'name'] and r['detail']['supportsDryRun'], r)
    e = err(svc.list_commands, command='animation.animator add_layr')
    check('typo -> command_not_found with suggestions', e is not None and e.code == 'command_not_found' and e.extra.get('suggestions'), e and e.extra)

    e = err(ex.run_exec, 'animation.animator add_layer', dict(P))
    check('write without dry-run -> dry_run_required', e is not None and e.code == 'dry_run_required', e and e.code)
    e = err(ex.run_exec, 'animation.animator add_layer', {'controller': 'x'})
    check('missing required -> invalid_parameters', e is not None and e.code == 'invalid_parameters' and e.extra.get('missing') == ['name'], e and e.extra)
    e = err(ex.run_exec, 'animation.animator add_layer', dict(P, bogus=1))
    check('unknown param -> invalid_parameters', e is not None and e.code == 'invalid_parameters' and e.extra.get('unknown') == ['bogus'], e and e.extra)

    r = ex.run_exec('animation.animator add_layer', dict(P), dryRun=True)
    sent = fake.STATE['exec_log'][-1]['parameters']
    check('dry-run ok and sends dry-run=true', r['ok'] and r['dryRun'] and sent.get('dry-run') is True, r)
    r = ex.run_exec('animation.animator add_layer', dict(P))
    sent = fake.STATE['exec_log'][-1]['parameters']
    check('real call after matching dry-run ok', r['ok'] and not r['dryRun'] and 'dry-run' not in sent, r)
    check('request body is command / parameters / timeout', set(fake.STATE['exec_log'][-1]) == {'command', 'parameters', 'timeout'}, fake.STATE['exec_log'][-1])
    e = err(ex.run_exec, 'animation.animator add_layer', dict(P))
    check('dry-run authorization is single use', e is not None and e.code == 'dry_run_required', e and e.code)
    e = err(ex.run_exec, 'editor status', dryRun=True)
    check('dryRun on a command without dry-run -> dry_run_unsupported', e is not None and e.code == 'dry_run_unsupported', e and e.code)
    r = ex.run_exec('editor status', {'path': 'a'})
    check('command without dry-run param runs directly', r['ok'] and r['result']['success'] is True, r)
