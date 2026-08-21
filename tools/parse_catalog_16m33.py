# -*- coding: utf-8 -*-
"""Каталог деталей двигателя 16M33 (ДВС самосвала БЕЛАЗ-7513Т) → data/models/.

Каталог китайско-английский и устроен проще каталогов БЕЛАЗ: плоский список
узлов, у каждого узла страница с чертежом и страница (или несколько) с
перечнем позиций «Pos. · Part Number · Qty. · 中文名称 · Part Name».
Чертежи здесь векторные, поэтому страница рендерится в JPEG, а не извлекается
как готовое изображение.
"""
import argparse, hashlib, json, os, re
import pymupdf
from PIL import Image, ImageChops

RE_GROUP = re.compile(r'^(.*?)\s*[（(]\s*([^（）()]+?)\s*[)）]\s*$')
RE_POS = re.compile(r'^\d+$')
RE_PN = re.compile(r'^[0-9A-Za-z][0-9A-Za-z\-./]*$')
CJK = re.compile(r'[一-鿿]')
TITLE_Y = (80, 105)      # полоса, в которой стоит название узла
CLIP = (55, 112, 542, 792)   # без шапки страницы: название узла есть в данных
MARGIN = 24
ZOOM = 3


def clean(s):
    return re.sub(r'\s+', ' ', (s or '')).strip()


def group_title(page):
    """Название узла со страницы: «机体结合组(Engine Block Group)»."""
    for b in page.get_text("blocks"):
        if TITLE_Y[0] <= b[1] <= TITLE_Y[1]:
            t = clean(b[4])
            m = RE_GROUP.match(t)
            if m:
                return clean(m.group(1)), clean(m.group(2))
            if t:
                return t, ''
    return None


def page_parts(page):
    out = []
    for b in page.get_text("blocks"):
        lines = [l.strip() for l in b[4].split('\n') if l.strip()]
        if len(lines) < 4:
            continue
        pos = lines[0] if RE_POS.match(lines[0]) else ''
        rest = lines[1:] if pos else lines
        if not rest or not RE_PN.match(rest[0]):
            continue
        pn, qty, names = rest[0], (rest[1] if len(rest) > 1 else ''), rest[2:]
        if not re.fullmatch(r'\d+', qty or ''):
            continue
        zh = ' '.join(n for n in names if CJK.search(n))
        en = ' '.join(n for n in names if not CJK.search(n))
        out.append({'pos': pos, 'des': pn, 'okp': '', 'qty': qty,
                    'ru': clean(en) or clean(zh), 'en': clean(zh), 'x': 0})
    return out


def render(page, path):
    """Отрисовать чертёж страницы и обрезать пустые поля вокруг него."""
    clip = pymupdf.Rect(*CLIP)
    pix = page.get_pixmap(matrix=pymupdf.Matrix(ZOOM, ZOOM), clip=clip,
                          colorspace=pymupdf.csGRAY)
    im = Image.frombytes('L', (pix.width, pix.height), pix.samples)
    box = ImageChops.invert(im).getbbox()
    if box:
        im = im.crop((max(0, box[0] - MARGIN), max(0, box[1] - MARGIN),
                      min(im.width, box[2] + MARGIN), min(im.height, box[3] + MARGIN)))
    im.save(path, 'JPEG', quality=80, optimize=True, progressive=True)


def build(pdf, model_id, name, subtitle, group, out_root, start=4):
    doc = pymupdf.open(pdf)
    drawings_dir = os.path.join(out_root, 'drawings', model_id)
    os.makedirs(drawings_dir, exist_ok=True)

    figures, order, cur = {}, [], None
    n = 0
    for pno in range(start, len(doc)):
        page = doc[pno]
        title = group_title(page)
        if not title:
            continue
        zh, en = title
        key = zh + '|' + en
        if key not in figures:
            n += 1
            figures[key] = {'code': str(n), 'section': '1', 'ru': en or zh,
                            'en': zh, 'desig': '', 'sheets': [], 'parts': []}
            order.append(key)
        f = figures[key]
        cur = f

        text = page.get_text()
        if '图序号' in text:
            f['parts'].extend(page_parts(page))
        else:
            tmp = os.path.join(drawings_dir, f'_tmp{pno}.jpg')
            render(page, tmp)
            digest = hashlib.sha1(open(tmp, 'rb').read()).hexdigest()[:16]
            final = os.path.join(drawings_dir, digest + '.jpg')
            os.replace(tmp, final)
            rel = f"drawings/{model_id}/{digest}.jpg"
            if rel not in f['sheets']:
                f['sheets'].append(rel)

    used = [figures[k] for k in order if figures[k]['parts'] or figures[k]['sheets']]
    for i, f in enumerate(used, 1):
        f['code'] = str(i)
    model = {'id': model_id, 'name': name, 'subtitle': subtitle, 'group': group,
             'figureWord': 'Узел', 'source': os.path.basename(pdf),
             'sections': [{'code': '1', 'ru': 'Узлы двигателя 16M33',
                           'en': '16M33 series engine assemblies'}],
             'figures': used}
    out_dir = os.path.join(out_root, 'data', 'models')
    os.makedirs(out_dir, exist_ok=True)
    out = os.path.join(out_dir, f'{model_id}.js')
    with open(out, 'w', encoding='utf-8') as fh:
        fh.write('window.MODELS = window.MODELS || {};\n')
        fh.write(f'window.MODELS[{json.dumps(model_id)}] = ')
        json.dump(model, fh, ensure_ascii=False, separators=(',', ':'))
        fh.write(';\n')
    parts = sum(len(f['parts']) for f in used)
    sheets = sum(len(f['sheets']) for f in used)
    print(f"{model_id}: узлов {len(used)}, чертежей {sheets}, деталей {parts} -> {out}")


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('pdf')
    ap.add_argument('--id', default='engine16m33')
    ap.add_argument('--name', default='16M33')
    ap.add_argument('--subtitle', default='дизельный двигатель серии 16M33 (ДВС БЕЛАЗ-7513Т)')
    ap.add_argument('--group', default='Двигатели и агрегаты')
    ap.add_argument('--out', default='.')
    ap.add_argument('--start', type=int, default=4,
                    help='первая страница тела каталога (до неё — оглавление)')
    a = ap.parse_args()
    build(a.pdf, a.id, a.name, a.subtitle, a.group, a.out, a.start)
