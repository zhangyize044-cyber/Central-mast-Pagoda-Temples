# -*- coding: utf-8 -*-
"""
程序化贴图生成：砖 / 瓦 / 木 / 石 / 彩画
全部用 numpy 现场生成，不依赖任何外部素材。
输出到 model/tex/*.png

用法：blender --background --factory-startup --python gen_textures.py
"""

import bpy
import numpy as np
import os
import math

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "tex")
os.makedirs(OUT, exist_ok=True)


def lin(c):
    """sRGB 0-255 -> linear"""
    c = c / 255.0
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def rgb(r, g, b):
    # 存 linear：Blender 的 image.pixels 是线性缓冲，保存 PNG 时会编码为 sRGB
    return np.array([lin(r), lin(g), lin(b)], dtype=np.float32)


def save(arr, name):
    h, w, _ = arr.shape
    img = bpy.data.images.new(name, width=w, height=h, alpha=False)
    img.colorspace_settings.name = "sRGB"
    rgba = np.ones((h, w, 4), dtype=np.float32)
    rgba[:, :, :3] = np.clip(arr, 0.0, 1.0)
    img.pixels.foreach_set(rgba[::-1].ravel())
    img.filepath_raw = os.path.join(OUT, name + ".png")
    img.file_format = "PNG"
    img.save()
    print("saved:", name, arr.shape)


def fbm(S, octaves=(4, 8, 16, 48), weights=(0.5, 0.3, 0.15, 0.05), seed=0):
    """简化分形噪声：多个尺度的随机网格插值叠加"""
    rng = np.random.default_rng(seed)
    acc = np.zeros((S, S), dtype=np.float32)
    for oc, wt in zip(octaves, weights):
        g = rng.random((oc, oc)).astype(np.float32)
        # 双线性放大到 S x S
        idx = np.linspace(0, oc - 1, S, dtype=np.float32)
        i0 = np.floor(idx).astype(int)
        i1 = np.minimum(i0 + 1, oc - 1)
        f = (idx - i0)[:, None]
        a = g[i0][:, i0]
        b = g[i0][:, i1]
        c = g[i1][:, i0]
        d = g[i1][:, i1]
        top = a * (1 - f) + b * f
        bot = c * (1 - f) + d * f
        acc += wt * (top * (1 - f.T) + bot * f.T)
    acc -= acc.min()
    acc /= max(acc.max(), 1e-6)
    return acc


# ============================ 砖墙 ============================
def brick_tex(S=512):
    base = rgb(102, 96, 84)
    arr = np.ones((S, S, 3), dtype=np.float32) * base

    rows, cols = 26, 6            # 2m 贴图：砖约 0.077 x 0.33 m
    rh = S // rows
    cw = S // cols
    rng = np.random.default_rng(7)

    for r in range(rows):
        off = (cw // 2) if (r % 2) else 0
        for c in range(-1, cols + 1):
            x0 = c * cw + off
            x1 = x0 + cw
            y0 = r * rh
            y1 = y0 + rh
            shade = 1.0 + rng.uniform(-0.11, 0.11)
            tint = np.array([1.0, rng.uniform(0.96, 1.03), rng.uniform(0.93, 1.04)], dtype=np.float32)
            xs = slice(max(0, x0), min(S, x1))
            ys = slice(max(0, y0), min(S, y1))
            arr[ys, xs] = base * shade * tint

    # 砖缝
    mortar = rgb(80, 75, 66)
    for r in range(rows + 1):
        y = min(S - 1, r * rh)
        arr[max(0, y - 1):min(S, y + 2), :] = mortar
    for r in range(rows):
        off = (cw // 2) if (r % 2) else 0
        for c in range(-1, cols + 1):
            x = c * cw + off
            if 0 <= x < S:
                y0 = r * rh
                y1 = min(S, (r + 1) * rh)
                arr[y0:y1, max(0, x - 1):min(S, x + 2)] = mortar

    # 斑驳 / 水渍 / 风化
    n1 = fbm(S, seed=11)
    n2 = fbm(S, octaves=(16, 48, 96), weights=(0.6, 0.3, 0.1), seed=23)
    wear = 1.0 - 0.22 * n1 - 0.14 * n2
    arr *= wear[:, :, None]

    # 细颗粒
    grain = rng.normal(0.0, 0.018, (S, S, 1)).astype(np.float32)
    arr += grain

    # 少量苔痕（偏绿的暗斑）
    moss = np.clip((n1 - 0.62) * 3.0, 0, 1) * 0.22
    arr = arr * (1 - moss[:, :, None]) + rgb(60, 62, 44) * moss[:, :, None]

    save(arr, "brick")
    return arr


# ============================ 瓦面 ============================
def tile_tex(S=512):
    base = rgb(100, 108, 114)
    u = np.linspace(0, 1, S, dtype=np.float32)
    v = np.linspace(0, 1, S, dtype=np.float32)
    U, V = np.meshgrid(u, v)

    # 筒瓦：沿 U 方向 8 垄（2m / 0.25m）
    # 场地屋面已用几何生成瓦垄，贴图此处只留极轻的明暗，避免与几何叠出摩尔纹
    ridge = 0.5 + 0.5 * np.cos(2 * np.pi * U * 8)
    shade = 0.92 + 0.16 * ridge

    # 板瓦竖向分割（每垄中间一道暗缝）
    seam = 1.0 - 0.14 * np.exp(-((((U * 8) % 1.0) - 0.5) ** 2) / 0.0006)

    # 横向瓦片搭接（每 0.33m 一道）
    row = (V * 6.0) % 1.0
    lap = 1.0 - 0.20 * np.exp(-((row - 0.02) ** 2) / 0.0004)

    arr = np.ones((S, S, 3), dtype=np.float32) * base
    arr *= (shade * seam * lap)[:, :, None]

    # 风化斑驳
    n1 = fbm(S, seed=31)
    arr *= (0.86 + 0.26 * n1)[:, :, None]

    rng = np.random.default_rng(5)
    arr += rng.normal(0.0, 0.014, (S, S, 1)).astype(np.float32)

    save(arr, "tile")
    return arr


# ============================ 木纹 ============================
def wood_tex(S=512):
    base = rgb(120, 64, 38)
    u = np.linspace(0, 1, S, dtype=np.float32)
    v = np.linspace(0, 1, S, dtype=np.float32)
    U, V = np.meshgrid(u, v)

    # 竖向年轮：低频正弦 + 扰动
    warp = 0.10 * np.sin(2 * np.pi * V * 1.3) + 0.05 * np.sin(2 * np.pi * V * 3.7)
    rings = 0.5 + 0.5 * np.sin(2 * np.pi * (U * 5.5 + warp + 0.6 * np.sin(2 * np.pi * V * 0.7)))
    shade = 0.74 + 0.40 * rings

    arr = np.ones((S, S, 3), dtype=np.float32) * base
    arr *= shade[:, :, None]

    # 细长纤维
    n1 = fbm(S, octaves=(32, 96, 192), weights=(0.5, 0.3, 0.2), seed=41)
    arr *= (0.86 + 0.28 * n1)[:, :, None]

    # 节疤
    rng = np.random.default_rng(3)
    for _ in range(6):
        cx, cy = rng.uniform(0.1, 0.9), rng.uniform(0.1, 0.9)
        r = rng.uniform(0.012, 0.028)
        d = np.sqrt((U - cx) ** 2 + (V - cy) ** 2)
        knot = np.exp(-(d ** 2) / (2 * r ** 2)) * 0.45
        arr *= (1 - knot)[:, :, None]

    # 竖向拉丝
    arr *= (1 - 0.10 * (0.5 + 0.5 * np.sin(2 * np.pi * U * 90)))[:, :, None]

    save(arr, "wood")
    return arr


# ============================ 石材 ============================
def stone_tex(S=512):
    base = rgb(118, 110, 94)
    arr = np.ones((S, S, 3), dtype=np.float32) * base

    n1 = fbm(S, seed=53)
    n2 = fbm(S, octaves=(24, 64, 128), weights=(0.6, 0.3, 0.1), seed=59)
    arr *= (0.78 + 0.38 * n1)[:, :, None]
    arr *= (0.90 + 0.20 * n2)[:, :, None]

    rng = np.random.default_rng(13)
    arr += rng.normal(0.0, 0.022, (S, S, 1)).astype(np.float32)

    # 石缝：2m 内 4x4 块，每块 0.5m
    seam = rgb(84, 78, 66)
    step = S // 4
    for i in range(5):
        p = min(S - 1, i * step)
        arr[max(0, p - 1):min(S, p + 2), :] = seam
        arr[:, max(0, p - 1):min(S, p + 2)] = seam

    save(arr, "stone")
    return arr


# ============================ 彩画（斗拱用） ============================
def caihua_tex(S=256):
    """旋子彩画意象：青绿底 + 金色线条 + 局部朱红"""
    base = rgb(78, 112, 102)
    arr = np.ones((S, S, 3), dtype=np.float32) * base
    v = np.linspace(0, 1, S, dtype=np.float32)
    V = np.tile(v[:, None], (1, S))

    # 上下青绿带：石绿压深、下缘朱红
    arr[V > 0.72] = rgb(48, 96, 88)
    arr[V < 0.22] = rgb(112, 56, 42)

    # 金色箍线
    for y in (0.20, 0.24, 0.70, 0.74):
        y0 = int(y * S)
        arr[y0:y0 + max(2, S // 220), :] = rgb(196, 156, 70)

    # 旋子花心（3 朵）
    u = np.linspace(0, 1, S, dtype=np.float32)
    U = np.tile(u[None, :], (S, 1))
    for cx in (0.18, 0.5, 0.82):
        d = np.sqrt(((U - cx) * 2.2) ** 2 + ((V - 0.47) * 1.0) ** 2)
        ring1 = (np.abs(d - 0.16) < 0.012)
        ring2 = (np.abs(d - 0.095) < 0.010)
        arr[ring1] = rgb(196, 156, 70)
        arr[ring2] = rgb(166, 126, 56)
        arr[d < 0.045] = rgb(52, 104, 96)

    # 风化
    n1 = fbm(S, octaves=(8, 32, 96), weights=(0.5, 0.3, 0.2), seed=71)
    arr *= (0.78 + 0.34 * n1)[:, :, None]
    rng = np.random.default_rng(17)
    arr += rng.normal(0.0, 0.016, (S, S, 1)).astype(np.float32)

    save(arr, "caihua")
    return arr


brick_tex()
tile_tex()
wood_tex()
stone_tex()
caihua_tex()
print("ALL_TEXTURES_DONE ->", OUT)
