# -*- coding: utf-8 -*-
"""Сборка каталога БЕЛАЗ из заводского PDF в data/models/<id>.js + drawings/<id>/.

Разбирает: разделы («2.N»), рисунки («2.N.M») с растровыми чертежами и таблицы
деталей. Одинаковые чертежи хранятся один раз (дедупликация по содержимому).
"""
import argparse, hashlib, io, json, os, re, sys
import pymupdf

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import belaz_pdf as B

RE_CODE_HEAD = re.compile(r'^(\d+\.\d+)\s+(.+)$', re.S)
RE_FIG = re.compile(r'^(?:Рисунок|Figure)\s+(\d+(?:\.\d+)+)\s+(.*)$', re.S)
RE_TBL = re.compile(r'^(?:Таблица|Table|Продолжение таблицы|To be continued)\s+(\d+(?:\.\d+)+)')
RE_SHEET = re.compile(r'\(\s*(?:Рисунок|Figure)\s+([IVX]+)\s*\)')
RE_DESIG = re.compile(r'\(([^()]{3,60})\)\s*$')
ROW_TOL = 9.5          # отступ, в пределах которого строка относится к той же позиции
CYR = re.compile(r'[А-Яа-яЁё]')


def has_cyr(s):
    return bool(CYR.search(s))


def norm(s):
    """Схлопнуть пробелы; в номерах БЕЛАЗ вида «7513T  -1000003» убрать разрыв."""
    s = re.sub(r'\s+', ' ', (s or '')).strip()
    return re.sub(r'\s+-', '-', s)


def clean_name(s):
    return re.sub(r'\s+', ' ', (s or '')).strip(' .')


def strip_page_no(s):
    """Убрать номер страницы, приклеившийся к названию из оглавления."""
    return re.sub(r'\s+\d{1,4}$', '', s)


def blocks(page):
    return [(b[0], b[1], b[4].strip()) for b in page.get_text("blocks") if b[4].strip()]


def parse_sections(doc):
    """Разделительные страницы «2.N Название» → коды и названия разделов.

    Оглавление пропускаем: там те же коды, но с номерами страниц в конце строки.
    """
    sections = {}
    for pno in range(len(doc)):
        page_blocks = blocks(doc[pno])
        if any(t.startswith(('Содержание', 'Contents')) for _x, _y, t in page_blocks):
            continue
        for _x, _y, t in page_blocks:
            m = RE_CODE_HEAD.match(t)
            if not m:
                continue
            code = m.group(1)
            parts = [p for p in t.split('\n') if p.strip()]
            ru = en = ''
            cur = []
            for line in parts:
                mm = RE_CODE_HEAD.match(line)
                if mm and cur:
                    (ru and 0) or None
                    txt = ' '.join(cur)
                    if has_cyr(txt):
                        ru = ru or txt
                    else:
                        en = en or txt
                    cur = []
                cur.append(re.sub(r'^\d+\.\d+\s+', '', line))
            txt = ' '.join(cur)
            if has_cyr(txt):
                ru = ru or txt
            else:
                en = en or txt
            s = sections.setdefault(code, {'code': code, 'ru': '', 'en': '', 'page': pno})
            s['ru'] = s['ru'] or strip_page_no(clean_name(ru))
            s['en'] = s['en'] or strip_page_no(clean_name(en))
    return sections


def page_markers(page):
    """Подписи рисунков и заголовки таблиц страницы: (y, вид, код, данные)."""
    out = []
    for _x, y, t in blocks(page):
        lines = [l.strip() for l in t.split('\n') if l.strip()]
        for line in lines:
            m = RE_TBL.match(line)
            if m:
                out.append((y, 'table', m.group(1), None))
                break
        else:
            fig = {}
            code = None
            for line in lines:
                m = RE_FIG.match(line)
                if not m:
                    continue
                code = m.group(1)
                rest = m.group(2).strip()
                sheet = RE_SHEET.search(rest)
                if sheet:
                    fig['sheet'] = sheet.group(1)
                    rest = RE_SHEET.sub('', rest).strip()
                if has_cyr(rest):
                    d = RE_DESIG.search(rest)
                    if d:
                        fig['desig'] = norm(d.group(1))
                        rest = rest[:d.start()].strip()
                    fig['ru'] = clean_name(rest)
                else:
                    fig['en'] = clean_name(rest)
            if code:
                out.append((y, 'figure', code, fig))
    return sorted(out)


def page_rows(page):
    """Строки таблицы страницы: (y, поля). Перенос строк приклеивается к позиции."""
    lines = B.page_words(page)
    ax = B.anchor_x(lines)
    if ax is None:
        return []
    parsed = [(y, B.split_columns(ws, ax)) for y, ws in lines]
    anchors = [(y, c) for y, c in parsed
               if re.fullmatch(r'\d+[а-яА-Яa-zA-Z]?', c['pos'] or '')]
    if not anchors:
        return []
    rows = [{'y': y, 'pos': c['pos'], 'des': [c['des']], 'okp': [c['okp']],
             'qty': c['qty'], 'ru': [(y, c['ru'])], 'en': [(y, c['en'])]} for y, c in anchors]
    ays = [r['y'] for r in rows]
    for y, c in parsed:
        if any(abs(y - a) < 0.01 for a in ays):
            continue
        if not (c['ru'] or c['en'] or c['des'] or c['okp']):
            continue
        best = min(rows, key=lambda r: abs(r['y'] - y))
        if abs(best['y'] - y) > ROW_TOL:
            continue
        best['ru'].append((y, c['ru']))
        best['en'].append((y, c['en']))
        if c['des']:
            best['des'].append(c['des'])
        if c['okp']:
            best['okp'].append(c['okp'])
    out = []
    for r in rows:
        ru = ' '.join(t for _y, t in sorted(r['ru']) if t)
        en = ' '.join(t for _y, t in sorted(r['en']) if t)
        okp = ' '.join(x for x in r['okp'] if x)
        interch = '*' in okp
        out.append((r['y'], {
            'pos': r['pos'],
            'des': norm(' '.join(x for x in r['des'] if x)),
            'okp': re.sub(r'[^0-9]', '', okp),
            'qty': r['qty'].strip(),
            'ru': clean_name(ru),
            'en': clean_name(en),
            'x': 1 if interch else 0,
        }))
    return out


def page_images(page, min_area=8000):
    out = []
    for info in page.get_image_info(xrefs=True):
        b = info['bbox']
        if (b[2] - b[0]) * (b[3] - b[1]) >= min_area and info.get('xref'):
            out.append((info['xref'], b))
    return out


def build(pdf, model_id, name, subtitle, group, out_root, chapter='2'):
    doc = pymupdf.open(pdf)
    sections = parse_sections(doc)
    figures = {}        # code -> {ru,en,desig,section,sheets:[],parts:[]}
    order = []
    drawings_dir = os.path.join(out_root, 'drawings', model_id)
    os.makedirs(drawings_dir, exist_ok=True)
    seen_img = {}
    current = None      # код таблицы, продолжающейся со страницы на страницу

    def fig(code):
        if code not in figures:
            sec = code.rsplit('.', 1)[0]
            figures[code] = {'code': code, 'section': sec, 'ru': '', 'en': '',
                             'desig': '', 'sheets': [], 'parts': []}
            order.append(code)
        return figures[code]

    for pno in range(len(doc)):
        page = doc[pno]
        marks = page_markers(page)
        rows = page_rows(page)
        imgs = page_images(page)

        for _y, kind, code, data in marks:
            f = fig(code)
            if kind == 'figure' and data:
                f['ru'] = f['ru'] or data.get('ru', '')
                f['en'] = f['en'] or data.get('en', '')
                f['desig'] = f['desig'] or data.get('desig', '')

        # чертёж относится к подписи, стоящей под ним
        caps = [(y, code) for y, kind, code, _d in marks if kind == 'figure']
        for xref, bbox in imgs:
            cand = [(y - bbox[3], c) for y, c in caps if -4 <= y - bbox[3] <= 80]
            if not cand:
                continue
            _dy, code = min(cand)
            if xref not in seen_img:
                img = doc.extract_image(xref)
                digest = hashlib.sha1(img['image']).hexdigest()[:16]
                fname = f"{digest}.{img['ext']}"
                path = os.path.join(drawings_dir, fname)
                if not os.path.exists(path):
                    with open(path, 'wb') as fh:
                        fh.write(img['image'])
                seen_img[xref] = f"drawings/{model_id}/{fname}"
            rel = seen_img[xref]
            if rel not in fig(code)['sheets']:
                fig(code)['sheets'].append(rel)

        if marks:
            tbl_marks = [(y, code) for y, kind, code, _d in marks if kind == 'table']
        else:
            tbl_marks = []
        for y, row in rows:
            before = [c for my, c in tbl_marks if my < y]
            code = before[-1] if before else current
            if not code:
                continue
            fig(code)['parts'].append(row)
        if tbl_marks:
            current = tbl_marks[-1][1]

    used = [c for c in order
            if (figures[c]['parts'] or figures[c]['sheets'])
            and c.startswith(chapter + '.')]
    secs = []
    for code in sorted({figures[c]['section'] for c in used},
                       key=lambda s: [int(x) for x in s.split('.')]):
        s = sections.get(code, {'code': code, 'ru': '', 'en': ''})
        secs.append({'code': code, 'ru': s['ru'], 'en': s['en']})
    model = {
        'id': model_id, 'name': name, 'subtitle': subtitle, 'group': group,
        'source': os.path.basename(pdf),
        'sections': secs,
        'figures': [figures[c] for c in sorted(used, key=lambda s: [int(x) for x in s.split('.')])],
    }
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
    return model


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('pdf')
    ap.add_argument('--id', required=True)
    ap.add_argument('--name', required=True)
    ap.add_argument('--subtitle', default='')
    ap.add_argument('--group', default='Машины БЕЛАЗ')
    ap.add_argument('--out', default='.')
    ap.add_argument('--chapter', default='2',
                    help='номер главы с иллюстрациями и деталировкой')
    a = ap.parse_args()
    build(a.pdf, a.id, a.name, a.subtitle, a.group, a.out, a.chapter)
