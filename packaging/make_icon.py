"""Draws the app icon (packaging/icon.png). Run once: python packaging/make_icon.py"""

from pathlib import Path

from PIL import Image, ImageDraw

S = 1024
img = Image.new("RGBA", (S, S), (0, 0, 0, 0))
d = ImageDraw.Draw(img)

# Background: rounded square with a vertical blue gradient.
grad = Image.new("RGBA", (S, S))
gd = ImageDraw.Draw(grad)
for y in range(S):
    t = y / S
    gd.line([(0, y), (S, y)], fill=(int(37 + 20 * t), int(99 - 30 * t), int(235 - 60 * t), 255))
mask = Image.new("L", (S, S), 0)
ImageDraw.Draw(mask).rounded_rectangle([40, 40, S - 40, S - 40], radius=200, fill=255)
img.paste(grad, (0, 0), mask)

# Two overlapping pages.
def page(x, y, w, h, fill, fold=90):
    d.polygon([(x, y), (x + w - fold, y), (x + w, y + fold), (x + w, y + h), (x, y + h)], fill=fill)
    d.polygon([(x + w - fold, y), (x + w - fold, y + fold), (x + w, y + fold)], fill=(203, 213, 225, 255))

page(200, 190, 380, 480, (226, 232, 240, 255))
page(440, 350, 380, 480, (255, 255, 255, 255))
for i in range(4):
    d.rounded_rectangle([500, 500 + i * 70, 760 - (i % 2) * 70, 530 + i * 70], radius=12, fill=(37, 99, 235, 255))

# Curved arrow from back page to front page.
d.arc([250, 520, 560, 830], start=90, end=200, fill=(250, 204, 21, 255), width=46)
d.polygon([(390, 790), (470, 830), (390, 880)], fill=(250, 204, 21, 255))

out = Path(__file__).with_name("icon.png")
img.save(out)
print(out)
