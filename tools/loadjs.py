# -*- coding: utf-8 -*-
"""Чтение JSON из сгенерированных window.*.js файлов каталога."""
import json


def load(path, marker='window.MODELS['):
    s = open(path, encoding='utf-8').read()
    i = s.index(marker)
    j = s.index('=', i) + 1
    return json.loads(s[j:].strip().rstrip().rstrip(';'))
