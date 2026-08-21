# -*- coding: utf-8 -*-
"""Разбор заводских каталогов деталей БЕЛАЗ (двуязычный PDF с текстовым слоем).

Структура каталога одинакова для всех машин: раздел «2.N Наименование» →
рисунки «2.N.M» (растровый чертёж) → таблица деталей с колонками
«Номер позиции · Обозначение · Код ОКП · Кол-во · Наименование (рус/англ)».
Таблица может продолжаться на следующих страницах («Продолжение таблицы 2.N.M»).

Модуль даёт низкоуровневые примитивы; сборка каталога — в parse_catalog.py.
"""
import re
import pymupdf

# Заголовок колонки «Обозначение» задаёт горизонтальную привязку всей таблицы:
# страницы свёрстаны зеркально (чётные/нечётные сдвинуты на ~28 пт), поэтому
# границы колонок считаются от него, а не от абсолютных координат.
BANDS = {
    'pos': (-49, -17),
    'des': (-17, +71),
    'okp': (+71, +129),
    'ru':  (+129, +275),
    'en':  (+275, +431),
    'qty': (+431, +500),
}

RE_FIG_RU = re.compile(r'^Рисунок\s+(\d+(?:\.\d+)+)\s*(.*)$')
RE_FIG_EN = re.compile(r'^Figure\s+(\d+(?:\.\d+)+)\s*(.*)$')
RE_TBL_RU = re.compile(r'^(?:Продолжение таблицы|Таблица)\s+(\d+(?:\.\d+)+)')
RE_TBL_EN = re.compile(r'^(?:To be continued|Table)\s+(\d+(?:\.\d+)+)')
RE_SECT = re.compile(r'^(\d+\.\d+)\s+(.+?)\s*$')
# «Установка двигателя (7555B  -1000003)» → название и обозначение узла
RE_FIG_DESIG = re.compile(r'^(.*?)\s*\(([^()]*?[-\d][^()]*)\)\s*(?:\(Рисунок\s+([IVX]+)\))?\s*$')


def page_words(page):
    """Слова страницы, сгруппированные в строки по вертикали."""
    words = page.get_text("words")
    lines = {}
    for x0, y0, x1, y1, t, *_ in words:
        key = round(y0 / 2.0)          # допуск ~2 пт на строку
        lines.setdefault(key, []).append((x0, x1, y0, t))
    out = []
    for key in sorted(lines):
        ws = sorted(lines[key])
        out.append((min(w[2] for w in ws), ws))
    return out


def anchor_x(lines):
    """x0 заголовка «Обозначение» / «Designation» — привязка колонок."""
    for _y, ws in lines:
        for x0, _x1, _y0, t in ws:
            if t in ('Обозначение', 'Designation'):
                return x0
    return None


def split_columns(ws, ax):
    """Разложить слова строки по колонкам таблицы."""
    cells = {k: [] for k in BANDS}
    for x0, _x1, _y0, t in ws:
        for name, (lo, hi) in BANDS.items():
            if ax + lo <= x0 < ax + hi:
                cells[name].append(t)
                break
    return {k: ' '.join(v).strip() for k, v in cells.items()}


def text_lines(page):
    """Плоский список строк текста страницы (для заголовков и подписей)."""
    out = []
    for block in page.get_text("blocks"):
        for line in block[4].splitlines():
            line = line.strip()
            if line:
                out.append(line)
    return out


def page_label(page):
    """Напечатанный номер страницы (по центру внизу)."""
    r = page.rect
    clip = pymupdf.Rect(r.x0, r.y1 - 60, r.x1, r.y1)
    for w in page.get_text("words", clip=clip):
        if w[4].isdigit():
            return int(w[4])
    return None


def drawings(page, min_area=8000):
    """Растровые чертежи страницы: (xref, bbox). Мелкие логотипы отсеиваются."""
    out = []
    for info in page.get_image_info(xrefs=True):
        b = info['bbox']
        if (b[2] - b[0]) * (b[3] - b[1]) >= min_area and info.get('xref'):
            out.append((info['xref'], b))
    return out
