# -*- coding: utf-8 -*-
"""Оглавления руководств и связка «раздел каталога → глава руководства».

Руководства БЕЛАЗ идут без закладок PDF, зато на каждой странице есть колонтитул
с названием главы и меткой «глава-страница» (например «5-11»). По метке со
страницей 1 находится первая страница каждой главы — этого достаточно и для
оглавления во встроенном просмотрщике, и для перехода из раздела каталога.
"""
import argparse, json, os, re
import pymupdf

RE_LABEL = re.compile(r'^(\d{1,2})-(\d{1,3})$')

# Раздел каталога → ключевые слова главы руководства. Названия разделов во всех
# каталогах БЕЛАЗ одинаковы, поэтому таблица общая для всех машин.
SECTION_HINTS = [
    ('дизель-генератор', 'системы двигателя'),
    ('система питания', 'системы двигателя'),
    ('система выпуска', 'системы двигателя'),
    ('система охлаждения', 'системы двигателя'),
    ('электропривод', 'тяговый электропривод'),
    ('мост ведущий', 'задний мост'),
    ('электромотор', 'электромотор-колесо'),
    ('рама', 'ходовая часть'),
    ('подвеска', 'ходовая часть'),
    ('передняя ось', 'ходовая часть'),
    ('колеса и шины', 'ходовая часть'),
    ('рулевое', 'рулевое управление'),
    ('тормоз', 'тормозные системы'),
    ('пневмат', 'пневматическая система'),
    ('электрооборудование', 'электрооборудование'),
    ('дополнительные системы', 'система пожаротушения'),
    ('кабина', 'кабина'),
    ('оперение', 'кабина'),
    ('платформа', 'платформа'),
    ('опрокидывающий', 'опрокидывающий механизм'),
]


def chapters(path, start=5):
    """Главы документа: [{n, title, page}] — page это номер страницы PDF."""
    doc = pymupdf.open(path)
    out = {}
    for i in range(start, len(doc)):
        lines = [l.strip() for l in doc[i].get_text().splitlines() if l.strip()][:4]
        label = next((l for l in lines if RE_LABEL.fullmatch(l)), None)
        if not label:
            continue
        n, m = label.split('-')
        if int(m) == 1 and n not in out and lines and not RE_LABEL.fullmatch(lines[0]):
            out[n] = {'n': n, 'title': lines[0], 'page': i + 1}
    doc.close()
    return [out[k] for k in sorted(out, key=int)]


def match_chapter(section_name, chs):
    """Подобрать главу руководства по названию раздела каталога."""
    s = (section_name or '').lower()
    for needle, chapter_key in SECTION_HINTS:
        if needle in s:
            for c in chs:
                if chapter_key in c['title'].lower():
                    return c
    return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--out', default='.', help='корень каталога')
    a = ap.parse_args()

    models_js = os.path.join(a.out, 'data', 'models.js')
    src = open(models_js, encoding='utf-8').read()
    docs = json.loads(src[src.index('window.MODEL_DOCS =') + len('window.MODEL_DOCS ='):]
                      .split(';\n')[0])

    doctoc, xref = {}, {}
    for mid, items in docs.items():
        model_path = os.path.join(a.out, 'data', 'models', mid + '.js')
        if not os.path.exists(model_path):
            continue
        ms = open(model_path, encoding='utf-8').read()
        model = json.loads(ms[ms.index('=', ms.index('window.MODELS[')) + 1:].strip().rstrip(';\n').rstrip(';'))
        for d in items:
            if d['kind'] != 'pdf':
                continue
            path = os.path.join(a.out, d['file'])
            chs = chapters(path)
            if not chs:
                print(f"   ! глав не найдено: {d['file']}")
                continue
            doctoc[d['file']] = chs
            for sec in model['sections']:
                c = match_chapter(sec['ru'], chs)
                if not c:
                    continue
                xref.setdefault(mid, {}).setdefault(sec['code'], []).append(
                    {'doc': d['file'], 'label': d['label'],
                     'chapter': c['n'], 'title': c['title'], 'page': c['page']})
            print(f"   {d['file']}: глав {len(chs)}")

    with open(os.path.join(a.out, 'data', 'doctoc.js'), 'w', encoding='utf-8') as fh:
        fh.write('/* Оглавления руководств: файл -> главы с номерами страниц PDF. */\n')
        fh.write('window.DOCTOC = ')
        json.dump(doctoc, fh, ensure_ascii=False, separators=(',', ':'))
        fh.write(';\n')
    with open(os.path.join(a.out, 'data', 'xref.js'), 'w', encoding='utf-8') as fh:
        fh.write('/* Связка «раздел каталога -> глава руководства». */\n')
        fh.write('window.XREF = ')
        json.dump(xref, fh, ensure_ascii=False, separators=(',', ':'))
        fh.write(';\n')
    linked = sum(len(v) for v in xref.values())
    print(f"оглавлений: {len(doctoc)}, разделов со ссылкой на руководство: {linked}")


if __name__ == '__main__':
    main()
