# -*- coding: utf-8 -*-
'''Offline self-test: fake Unity Pipeline server + temp project folder. Needs neither Unity nor the mcp SDK.
Run:  python scripts/test_offline.py'''
import os
import sys
import tempfile
import types

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)
sys.path.insert(0, HERE)


def main():
    import fake_unity
    srv, port = fake_unity.start_server()
    project = tempfile.mkdtemp(prefix='fake_unity_')
    sys.argv = ['x', '--project', project, '--max-chars', '1000']   # must be set before unity_mcp.config is imported
    from unity_mcp import client, commands, config, execution, policy, service
    from unity_mcp.client import UnityMcpError
    client.AUTH_RETRY_DELAY = 0.05
    config.COMMAND_CACHE_TTL = 0.0

    def err(fn, *a, **k):
        try:
            fn(*a, **k)
        except UnityMcpError as exc:
            return exc
        return None

    ctx = types.SimpleNamespace(fake=fake_unity, srv=srv, port=port, project=project, err=err, client=client,
                                commands=commands, config=config, execution=execution, policy=policy, service=service)
    import cases_a
    import cases_b
    import checks
    cases_a.run(ctx)
    cases_b.run(ctx)
    print()
    print('ALL PASSED' if not checks.FAILS else 'FAILED: %s' % checks.FAILS)
    return 1 if checks.FAILS else 0


if __name__ == '__main__':
    sys.exit(main())
