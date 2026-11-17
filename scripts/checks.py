# -*- coding: utf-8 -*-
FAILS = []


def check(name, cond, extra=''):
    print(('PASS ' if cond else 'FAIL ') + name)
    if not cond:
        print('     detail: ' + str(extra))
        FAILS.append(name)
