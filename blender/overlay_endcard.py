# -*- coding: utf-8 -*-
"""第 08 拍落版：对 19.5–22.0s 的帧压暗并淡入标题组。

原序列保留在 anim_frames*/，成品序列写到 anim_frames_final*/。
可反复重放，不需要重渲；帧率无关（12fps 预览 / 24fps 终版共用一套版式）。

环境变量
  ANIM_SRC_DIR       原始序列目录，默认 anim_frames
  ANIM_DST_DIR       成品序列目录，默认 anim_frames_final
  ANIM_FRAME_END     总帧数，默认 264（12fps）；24fps 终版设 528
  ANIM_ENDCARD_START 落版起始帧，默认 235；24fps 终版设 469
  ANIM_FADE          淡入帧数，默认 12；24fps 终版设 24
"""
import os, shutil
from PIL import Image, ImageDraw, ImageFont

BASE = os.path.dirname(os.path.abspath(__file__))
SRC = os.environ.get("ANIM_SRC_DIR", os.path.join(BASE, "anim_frames"))
DST = os.environ.get("ANIM_DST_DIR", os.path.join(BASE, "anim_frames_final"))
os.makedirs(DST, exist_ok=True)

FRAME_END = int(os.environ.get("ANIM_FRAME_END", "264"))
ENDCARD_START = int(os.environ.get("ANIM_ENDCARD_START", "235"))
FADE = int(os.environ.get("ANIM_FADE", "12"))


def font(px, bold=False):
    for p in (("C:/Windows/Fonts/msyhbd.ttc" if bold else "C:/Windows/Fonts/msyh.ttc"),
              "C:/Windows/Fonts/simhei.ttf"):
        if os.path.exists(p):
            try:
                return ImageFont.truetype(p, px)
            except Exception:
                pass
    return ImageFont.load_default()


def spaced(draw, xy, text, fnt, fill, gap=0):
    x, y = xy
    for ch in text:
        draw.text((x, y), ch, font=fnt, fill=fill)
        box = draw.textbbox((0, 0), ch, font=fnt)
        x += box[2] - box[0] + gap


def width_of(draw, text, fnt, gap=0):
    return sum(draw.textbbox((0, 0), ch, font=fnt)[2] for ch in text) + gap * max(0, len(text) - 1)


def center(draw, y, text, fnt, fill, gap=0, W=800):
    w = width_of(draw, text, fnt, gap)
    spaced(draw, ((W - w) / 2, y), text, fnt, fill, gap)


GOLD = (232, 217, 184)
PALE = (224, 214, 194)
FAINT = (203, 210, 222)
DIM = (174, 182, 198)
LINE = (201, 162, 74)


def draw_text(W, H):
    """透明底的标题层，另与压暗层合成，便于分别控制淡入。

    版式以 800×500 预览为基准；终版按高度等比缩放字号与纵坐标，
    横向居中始终用实际 W，保证 16:10 → 16:9 变化时文字不变形。
    """
    layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer, "RGBA")
    A = lambda c: (c[0], c[1], c[2], 255)
    S = H / 500.0
    P = lambda v: int(round(v * S))

    f_title = font(P(34), True)
    f_sub = font(P(12))
    f_data = font(P(15))
    f_claim = font(P(18), True)
    f_note = font(P(11))
    f_tech = font(P(10))

    center(d, P(148), "正定 · 天宁寺凌霄塔", f_title, A(GOLD), P(3), W)
    center(d, P(198), "LINGXIAO PAGODA  /  TIAN'NING TEMPLE  /  ZHENGDING",
           f_sub, A((198, 206, 221)), P(2), W)
    d.line((W / 2 - P(96), P(224), W / 2 + P(96), P(224)),
           fill=(*LINE, 150), width=max(1, P(1)))
    center(d, P(236), "九级八角  ·  楼阁式  ·  砖木混合  ·  通高 40.98 m",
           f_data, A(PALE), P(1), W)
    center(d, P(292), "国内现存唯一保存塔心柱结构的古塔", f_claim, A(GOLD), P(1), W)
    center(d, P(330),
           "示意性重建 · 非测绘模型；牌坊、石渠、石桥、前殿遗址为复原推定，不作修缮依据",
           f_note, A(FAINT), 0, W)
    center(d, P(364), "BLENDER 4.4   ·   PARAMETRIC RECONSTRUCTION   ·   2026",
           f_tech, A(DIM), P(1), W)
    return layer


TEXT_LAYER = None
copied, titled = 0, 0
for f in range(1, FRAME_END + 1):
    name = "frame_%04d.png" % f
    src, dst = os.path.join(SRC, name), os.path.join(DST, name)
    if not os.path.exists(src):
        print("MISSING", name)
        continue
    if f < ENDCARD_START:
        if not os.path.exists(dst) or os.path.getsize(dst) != os.path.getsize(src):
            shutil.copy2(src, dst)
        copied += 1
        continue

    im = Image.open(src).convert("RGBA")
    W, H = im.size
    if TEXT_LAYER is None or TEXT_LAYER.size != (W, H):
        TEXT_LAYER = draw_text(W, H)
    t = f - ENDCARD_START
    fade = min(1.0, t / float(FADE))
    text_alpha = max(0.0, min(1.0, (t - 2) / float(FADE - 2)))
    dark = Image.new("RGBA", (W, H), (9, 12, 21, int(195 * fade)))
    # 落款区叠一条更实的带，浅色小字压在亮院落上才读得清
    S = H / 500.0
    P = lambda v: int(round(v * S))
    band = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    ImageDraw.Draw(band, "RGBA").rectangle(
        (0, P(272), W, P(392)), fill=(9, 12, 21, int(72 * fade)))
    dark = Image.alpha_composite(dark, band)
    txt = TEXT_LAYER
    if text_alpha < 1.0:
        txt = TEXT_LAYER.copy()
        txt.putalpha(TEXT_LAYER.getchannel("A").point(
            lambda a: int(a * text_alpha)))
    layer = Image.alpha_composite(dark, txt)
    out = Image.alpha_composite(im, layer).convert("RGB")
    out.save(dst, "PNG")
    titled += 1

print("ENDCARD_DONE copied=%d titled=%d dir=%s" % (copied, titled, DST))
