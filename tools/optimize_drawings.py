# -*- coding: utf-8 -*-
"""Пережатие чертежей каталога: серые штриховые сканы → JPEG меньшего объёма.

Чертежи в заводском PDF лежат как RGB-JPEG, хотя это штриховая графика.
Скрипт переводит их в градации серого (если цвет действительно не используется)
и пережимает; имена файлов не меняются, ссылки в data/models/*.js остаются
рабочими.
"""
import argparse, glob, os
from PIL import Image, ImageStat

MAXW = 2100
QUALITY = 78


def is_gray(im, tol=8):
    if im.mode != 'RGB':
        return True
    small = im.convert('RGB').resize((80, 80))
    r, g, b = small.split()
    st = ImageStat.Stat(Image.merge('RGB', (r, g, b)))
    mr, mg, mb = st.mean
    return max(abs(mr - mg), abs(mg - mb), abs(mr - mb)) < tol


def optimize(path):
    before = os.path.getsize(path)
    im = Image.open(path)
    if im.width > MAXW:
        im = im.resize((MAXW, round(im.height * MAXW / im.width)), Image.LANCZOS)
    if is_gray(im):
        im = im.convert('L')
    im.save(path, 'JPEG', quality=QUALITY, optimize=True, progressive=True)
    return before, os.path.getsize(path)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('root', help='каталог с чертежами, например build/drawings')
    a = ap.parse_args()
    files = [f for f in glob.glob(os.path.join(a.root, '**', '*'), recursive=True)
             if os.path.isfile(f)]
    tb = ta = 0
    for f in files:
        b, aa = optimize(f)
        tb += b
        ta += aa
    print(f"чертежей {len(files)}: {tb/2**20:.1f} МБ -> {ta/2**20:.1f} МБ "
          f"({100 - ta * 100 / max(tb, 1):.0f}% экономии)")


if __name__ == '__main__':
    main()
