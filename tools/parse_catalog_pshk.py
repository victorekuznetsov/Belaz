# -*- coding: utf-8 -*-
"""Каталог з-ч ПЩК-7547 → data/models/pshk7547.js + drawings/pshk7547/.

Вёрстка этого каталога отличается от каталогов самосвалов: он русскоязычный,
без колонки «Код ОКП», подпись рисунка стоит под таблицей, а не над ней.
Поэтому разбор отдельный, но на выходе — та же структура данных.
"""
import argparse, hashlib, json, os, re
from collections import defaultdict
import pymupdf

# границы колонок считаются от заголовков таблицы: страницы свёрстаны
# зеркально, поэтому абсолютные координаты на чётных и нечётных не совпадают
HDR = {'pos': 'Номер', 'des': 'Обозначение', 'ru': 'Наименование', 'qty': 'Кол.'}
OFFSETS = {'pos': (-25, None), 'des': (-60, None), 'ru': (-48, None), 'qty': (-30, None)}
RE_CAPTION = re.compile(r'Рисунок\s+(\d+(?:\.\d+)+)\s*[-–—]\s*(.+)')
RE_SECTION = re.compile(r'^(\d+\.\d+)\s+(.+)$', re.S)
ROW_TOL = 9.5


def clean(s):
    return re.sub(r'\s+', ' ', (s or '')).strip(' .')


def lines_of(page):
    buckets = defaultdict(list)
    for x0, y0, _x1, _y1, t, *_ in page.get_text("words"):
        buckets[round(y0 / 2.0)].append((x0, t))
    return [(k * 2.0, sorted(v)) for k, v in sorted(buckets.items())]


def header_bands(page):
    """Границы колонок страницы по заголовкам «Номер · Обозначение · …»."""
    xs = {}
    for _y, ws in lines_of(page):
        for x0, t in ws:
            for key, word in HDR.items():
                if t.rstrip('.') == word.rstrip('.') and key not in xs:
                    xs[key] = x0
        if len(xs) == len(HDR):
            break
    if len(xs) < len(HDR):
        return None
    order = ['pos', 'des', 'ru', 'qty']
    edges = []
    for i, key in enumerate(order):
        lo = xs[key] + OFFSETS[key][0]
        hi = (xs[order[i + 1]] + OFFSETS[order[i + 1]][0]) if i + 1 < len(order) else 10 ** 4
        edges.append((key, lo, hi))
    return edges


def cells_of(words, bands):
    out = {n: [] for n, _lo, _hi in bands}
    for x0, t in words:
        for name, lo, hi in bands:
            if lo <= x0 < hi:
                out[name].append(t)
                break
    return {k: ' '.join(v).strip() for k, v in out.items()}


def page_rows(page, bands=None):
    """Строки таблицы страницы; перенос строк приклеивается к своей позиции."""
    bands = bands or header_bands(page)
    if not bands:
        return []
    parsed = [(y, cells_of(ws, bands)) for y, ws in lines_of(page)]
    anchors = [(y, c) for y, c in parsed if re.fullmatch(r'\d+', c['pos'] or '')]
    if not anchors:
        return []
    rows = [{'y': y, 'pos': c['pos'], 'des': [(y, c['des'])],
             'ru': [(y, c['ru'])], 'qty': c['qty']} for y, c in anchors]
    ays = {r['y'] for r in rows}
    for y, c in parsed:
        if y in ays or not (c['des'] or c['ru']):
            continue
        best = min(rows, key=lambda r: abs(r['y'] - y))
        if abs(best['y'] - y) > ROW_TOL:
            continue
        best['des'].append((y, c['des']))
        best['ru'].append((y, c['ru']))
    out = []
    for r in rows:
        out.append((r['y'], {
            'pos': r['pos'],
            'des': clean(' '.join(t for _y, t in sorted(r['des']) if t)),
            'okp': '',
            'qty': r['qty'].strip(),
            'ru': clean(' '.join(t for _y, t in sorted(r['ru']) if t)),
            'en': '',
            'x': 0,
        }))
    return out


def captions(page):
    """Подписи рисунков страницы: (y, код, название)."""
    out = []
    for y, ws in lines_of(page):
        m = RE_CAPTION.search(' '.join(t for _x, t in ws))
        if m:
            out.append((y, m.group(1), clean(m.group(2))))
    return out


def events(doc):
    """Поток элементов каталога в порядке чтения: чертежи, строки, подписи.

    Вёрстка каталога неоднородна — подпись рисунка стоит то над таблицей,
    то под ней, а таблица может уходить на следующие страницы. Устойчивый
    признак один: новый чертёж начинает новый блок, а подпись внутри блока
    задаёт его номер.
    """
    for pno in range(len(doc)):
        page = doc[pno]
        items = []
        for info in page.get_image_info(xrefs=True):
            b = info['bbox']
            if (b[2] - b[0]) * (b[3] - b[1]) >= 20000 and info.get('xref'):
                items.append((b[1], 'img', info['xref']))
        for y, code, title in captions(page):
            items.append((y, 'cap', (code, title)))
        for y, row in page_rows(page):
            items.append((y, 'row', row))
        items.sort(key=lambda it: it[0])
        for _y, kind, data in items:
            yield pno, kind, data


RE_TOC = re.compile(r'^(\d+(?:\.\d+)+)\s+(\D.*?)(?:\s+\d+)?$')


def toc_names(doc):
    """Названия разделов и рисунков из «Таблицы 2.1» — оглавления каталога.

    Оглавление точнее разделительных страниц: на странице раздела
    «Оборудование поливооросительное» в каталоге опечатка в номере (2.4).
    """
    names = {}
    for pno in range(len(doc)):
        text = doc[pno].get_text()
        if 'Наименование рисунка' not in text:
            continue
        for _y, ws in lines_of(doc[pno]):
            m = RE_TOC.match(' '.join(t for _x, t in ws).strip())
            if m:
                names.setdefault(m.group(1), clean(m.group(2)))
    return names


def build(pdf, model_id, name, subtitle, group, out_root):
    doc = pymupdf.open(pdf)
    sections = toc_names(doc)

    blocks, cur, img_page = [], None, None
    for pno, kind, data in events(doc):
        if kind == 'img':
            # листами одного рисунка считаем только чертежи, идущие подряд
            # на одной странице и без подписи с таблицей между ними
            if cur is None or cur['cap'] or cur['rows'] or img_page != pno:
                cur = {'imgs': [], 'rows': [], 'cap': None}
                blocks.append(cur)
            img_page = pno
            cur['imgs'].append(data)
        elif cur is None:
            continue
        elif kind == 'cap':
            cur['cap'] = data
        else:
            cur['rows'].append(data)

    drawings_dir = os.path.join(out_root, 'drawings', model_id)
    os.makedirs(drawings_dir, exist_ok=True)
    figures, order = {}, []

    def fig(code):
        if code not in figures:
            figures[code] = {'code': code, 'section': '.'.join(code.split('.')[:2]),
                             'ru': '', 'en': '', 'desig': '', 'sheets': [], 'parts': []}
            order.append(code)
        return figures[code]

    for blk in blocks:
        if not blk['cap']:
            continue
        code, title = blk['cap']
        f = fig(code)
        f['ru'] = f['ru'] or sections.get(code) or title
        f['parts'].extend(blk['rows'])
        for xref in blk['imgs']:
            img = doc.extract_image(xref)
            digest = hashlib.sha1(img['image']).hexdigest()[:16]
            fname = f"{digest}.{img['ext']}"
            path = os.path.join(drawings_dir, fname)
            if not os.path.exists(path):
                with open(path, 'wb') as fh:
                    fh.write(img['image'])
            rel = f"drawings/{model_id}/{fname}"
            if rel not in f['sheets']:
                f['sheets'].append(rel)

    key = lambda s: [int(x) if x.isdigit() else 0 for x in s.split('.')]
    used = sorted(order, key=key)
    secs = [{'code': c, 'ru': sections.get(c, ''), 'en': ''}
            for c in sorted({figures[c]['section'] for c in used}, key=key)]
    model = {'id': model_id, 'name': name, 'subtitle': subtitle, 'group': group,
             'source': os.path.basename(pdf), 'sections': secs,
             'figures': [figures[c] for c in used]}
    out_dir = os.path.join(out_root, 'data', 'models')
    os.makedirs(out_dir, exist_ok=True)
    out = os.path.join(out_dir, f'{model_id}.js')
    with open(out, 'w', encoding='utf-8') as fh:
        fh.write('window.MODELS = window.MODELS || {};\n')
        fh.write(f'window.MODELS[{json.dumps(model_id)}] = ')
        json.dump(model, fh, ensure_ascii=False, separators=(',', ':'))
        fh.write(';\n')
    parts = sum(len(f['parts']) for f in model['figures'])
    sheets = sum(len(f['sheets']) for f in model['figures'])
    print(f"{model_id}: разделов {len(secs)}, рисунков {len(model['figures'])}, "
          f"чертежей {sheets}, деталей {parts} -> {out}")


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('pdf')
    ap.add_argument('--id', default='pshk7547')
    ap.add_argument('--name', default='ПЩК-7547')
    ap.add_argument('--subtitle', default='щебнеразбрасыватель на шасси БЕЛАЗ-7547')
    ap.add_argument('--group', default='Спецтехника')
    ap.add_argument('--out', default='.')
    a = ap.parse_args()
    build(a.pdf, a.id, a.name, a.subtitle, a.group, a.out)
