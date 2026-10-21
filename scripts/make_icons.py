#!/usr/bin/env python3
"""Build site icons from the square source artwork (rounded square on white).
Crops the white margin and applies a transparent, anti-aliased rounded-corner mask
fitted to the artwork (measured: square x 39..984, y 36..982 of 1024, corner radius ~198px)."""
import sys
from PIL import Image, ImageDraw
src = sys.argv[1]; out = sys.argv[2] if len(sys.argv) > 2 else 'static'
L, T, SIZE, R = 39, 36, 946, 198.0   # fitted on the 1024px source
INSET = 1.5                            # px, removes the anti-aliased white fringe
im = Image.open(src).convert('RGB').crop((L, T, L + SIZE, T + SIZE)).convert('RGBA')
S = 8
m = Image.new('L', (SIZE * S, SIZE * S), 0)
ImageDraw.Draw(m).rounded_rectangle([INSET * S, INSET * S, (SIZE - INSET) * S - 1, (SIZE - INSET) * S - 1],
                                    radius=(R - INSET) * S, fill=255)
im.putalpha(m.resize((SIZE, SIZE), Image.LANCZOS))
def save(px, name):
    im.resize((px, px), Image.LANCZOS).save(f'{out}/{name}', optimize=True)
for px, name in [(512, 'icon-512.png'), (192, 'icon-192.png'), (180, 'apple-touch-icon.png'),
                 (32, 'favicon-32.png'), (16, 'favicon-16.png')]:
    save(px, name)
im.resize((256, 256), Image.LANCZOS).save(f'{out}/favicon.ico', sizes=[(16, 16), (32, 32), (48, 48), (64, 64)])
print('ok')
