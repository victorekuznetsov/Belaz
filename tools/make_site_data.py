# -*- coding: utf-8 -*-
"""Реестр моделей, парк машин и подключение документов для каталога БЕЛАЗ."""
import argparse, json, os, re, shutil

MODELS = [
    ('belaz7513t', 'БЕЛАЗ-7513Т', 'карьерный самосвал, 130 т · ДВС 16M33', 'Самосвалы карьерные'),
    ('belaz7555b', 'БЕЛАЗ-7555В', 'карьерный самосвал, 55 т · ДВС KTTA19-C700', 'Самосвалы карьерные'),
    ('belaz7513d', 'БЕЛАЗ-7513D', 'карьерный самосвал, 130 т (справочно)', 'Самосвалы карьерные'),
    ('belaz76131', 'БЕЛАЗ-76131', 'поливооросительная машина 76131 / 76135 / 7613D', 'Спецтехника'),
    ('pshk7547', 'ПЩК-7547', 'щебнеразбрасыватель на шасси БЕЛАЗ-7547', 'Спецтехника'),
    ('engine16m33', '16M33', 'дизельный двигатель серии 16M33 (ДВС БЕЛАЗ-7513Т)', 'Двигатели и агрегаты'),
]

# Документы моделей: (подпись, исходный файл в rawdata, путь на сайте).
# Руководства серии 7513 общие для 7513Т и 7513D, поэтому лежат один раз.
OM_7513 = ('Руководство по эксплуатации семейства БЕЛАЗ-7513',
           'BELAZ/7513/Руководство по эксплуатации карьерные самосвалы семейства БЕЛАЗ -7513 (06-09-2024).pdf',
           'docs/7513/om.pdf')
RS_7513 = ('Руководство по ремонту серии БЕЛАЗ-7513',
           'BELAZ/7513/Руководство по ремонту на карьерные самосвалы серии БЕЛАЗ-7513 (06-09-2024).pdf',
           'docs/7513/service.pdf')
DOCS = {
    'belaz7513t': [OM_7513, RS_7513],
    'belaz7513d': [OM_7513, RS_7513],
    'belaz76131': [
        ('Руководство по эксплуатации БЕЛАЗ-76131, 76135, 7613D',
         'BELAZ/76131/Руководство по эксплуатации поливооросительная машина БЕЛАЗ-76131, 76135, 7613D (23-05-2024) _compressed.pdf',
         'docs/76131/om.pdf'),
    ],
    'pshk7547': [
        ('Руководство по эксплуатации ПЩК-7547',
         'BELAZ/ПЩК-7547/РЭ ПЩК-7547 (1).doc',
         'docs/pshk7547/om.doc'),
    ],
}

# документы, не привязанные к каталогу конкретной машины
COMMON_DOCS = [
    ('Руководство по эксплуатации серии БЕЛАЗ-7531',
     'BELAZ/7531/Руководство по эксплуатации на карьерные самосвалы серии БЕЛАЗ-7531 (10-04-2026).pdf',
     'docs/belaz/7531_om.pdf'),
    ('Руководство по эксплуатации тягачей БЕЛАЗ-74131 / 7413D',
     'BELAZ/74131/Руководство по эксплуатации на тягачи-буксировщики БЕЛАЗ-74131; БЕЛАЗ-7413D (25-06-2024)-2.pdf',
     'docs/belaz/74131_om.pdf'),
]


def js(path, var, obj, comment=''):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'w', encoding='utf-8') as fh:
        if comment:
            fh.write(f'/* {comment} */\n')
        fh.write(f'{var} = ')
        json.dump(obj, fh, ensure_ascii=False, separators=(',', ':'))
        fh.write(';\n')


def place(src_root, out_root, label, rel, dest):
    src = os.path.join(src_root, rel)
    if not os.path.exists(src):
        print(f"   ! нет файла {rel}")
        return None
    dst = os.path.join(out_root, dest)
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    if not os.path.exists(dst):
        shutil.copy2(src, dst)
    return {'label': label, 'file': dest,
            'kind': 'pdf' if dest.lower().endswith('.pdf') else 'file'}


def copy_docs(src_root, out_root, present):
    docs = {}
    for mid, items in DOCS.items():
        if mid not in present:
            continue
        for label, rel, dest in items:
            d = place(src_root, out_root, label, rel, dest)
            if d:
                docs.setdefault(mid, []).append(d)
    common = [d for d in (place(src_root, out_root, *item) for item in COMMON_DOCS) if d]
    return docs, common


def fleet(src_root):
    data = json.load(open(os.path.join(src_root, 'Эксплуатация/Парк/fleet.json'),
                          encoding='utf-8'))
    out = []
    for m in data['machines']:
        out.append({
            'owner': m['owner'], 'park': m.get('park', ''),
            'brand': m['brand'], 'model': m['model'], 'type': m.get('type', ''),
            'gar': m['gar'], 'vin': m.get('vin', ''), 'year': m.get('year', ''),
            'engines': [{'model': e['model'], 'sn': e['sn']} for e in m.get('engines', [])],
        })
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--src', default='.')
    ap.add_argument('--out', default='.')
    a = ap.parse_args()

    present = {m[0] for m in MODELS
               if os.path.exists(os.path.join(a.out, 'data', 'models', m[0] + '.js'))}
    models = [{'id': i, 'name': n, 'subtitle': s, 'group': g}
              for i, n, s, g in MODELS if i in present]

    docs, common = copy_docs(a.src, a.out, present)
    js(os.path.join(a.out, 'data', 'models.js'), 'window.MODEL_LIST', models,
       'Реестр машин каталога. Порядок = порядок в переключателе.')
    with open(os.path.join(a.out, 'data', 'models.js'), 'a', encoding='utf-8') as fh:
        fh.write('window.MODEL_DOCS = ')
        json.dump(docs, fh, ensure_ascii=False, separators=(',', ':'))
        fh.write(';\n')
        fh.write('window.COMMON_DOCS = ')
        json.dump(common, fh, ensure_ascii=False, separators=(',', ':'))
        fh.write(';\n')

    fl = fleet(a.src)
    js(os.path.join(a.out, 'data', 'fleet.js'), 'window.FLEET', fl,
       'Парк машин из выгрузки SAP (Эксплуатация/Парк/Belaz Fleet with engine.xlsx).')
    print(f"моделей в каталоге: {len(models)}; документов: "
          f"{sum(len(v) for v in docs.values())} по машинам + {len(common)} общих; "
          f"машин в парке: {len(fl)}")


if __name__ == '__main__':
    main()
