# -*- coding: utf-8 -*-
"""
院落环境贴图：青砖铺地 / 红墙抹灰 / 树皮 / 叶簇
沿用 gen_textures.py 的线性空间约定：rgb() 返回线性值。

用法：blender --background --factory-startup --python gen_tex_site.py
"""

import bpy
import numpy as np
import os

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "tex")
os.makedirs(OUT, exist_ok=True)


def lin(c):
    c = c / 255.0
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def rgb(r, g, b):
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
    rng = np.random.default_rng(seed)
    acc = np.zeros((S, S), dtype=np.float32)
    for oc, wt in zip(octaves, weights):
        g = rng.random((oc, oc)).astype(np.float32)
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


# ============================ 青砖铺地 ============================
def paving_tex(S=512):
    """1 贴图 = 1.92m。方砖 0.48m（4x4），十字缝墁地，局部沉降与草缝"""
    base = rgb(74, 72, 66)
    arr = np.ones((S, S, 3), dtype=np.float32) * base
    n_cell = 4                               # 1.92 / 0.48 = 4
    cs = S // n_cell
    rng = np.random.default_rng(97)

    for r in range(n_cell):
        for c in range(n_cell):
            shade = 1.0 + rng.uniform(-0.27, 0.27)
            tint = np.array([1.0, rng.uniform(0.94, 1.03), rng.uniform(0.90, 1.06)],
                            dtype=np.float32)
            arr[r * cs:(r + 1) * cs, c * cs:(c + 1) * cs] = base * shade * tint

    # 灰缝（宽约 4cm）
    mortar = rgb(48, 46, 41)
    for k in range(n_cell + 1):
        y = min(S - 1, k * cs)
        arr[max(0, y - 2):min(S, y + 2), :] = mortar
        x = min(S - 1, k * cs)
        arr[:, max(0, x - 2):min(S, x + 2)] = mortar

    # 磨损 + 沉降
    n1 = fbm(S, seed=101)
    n2 = fbm(S, octaves=(24, 64, 160), weights=(0.55, 0.3, 0.15), seed=107)
    arr *= (0.80 + 0.34 * n1)[:, :, None]
    arr *= (0.90 + 0.18 * n2)[:, :, None]

    # 砖面磨光的高光斑（人流踩踏）
    polish = np.clip((n1 - 0.66) * 3.4, 0, 1) * 0.20
    arr = arr * (1 + polish[:, :, None])

    # 缝里草芽 / 苔
    rng2 = np.random.default_rng(113)
    for _ in range(200):
        x, y = int(rng2.integers(2, S - 2)), int(rng2.integers(2, S - 2))
        near_x = min(x % cs, cs - x % cs)
        near_y = min(y % cs, cs - y % cs)
        if min(near_x, near_y) > 5:
            continue
        g = rng2.uniform(0.35, 0.85)
        arr[max(0, y - 2):y + 3, max(0, x - 2):x + 3] = rgb(58 * g + 30, 66 * g + 28, 36 * g + 18)

    arr += rng.normal(0.0, 0.016, (S, S, 1)).astype(np.float32)
    save(arr, "paving")
    return arr


# ============================ 红墙抹灰 ============================
def plaster_tex(S=512):
    """寺庙红墙：朱红抹灰，底部返潮、上部雨痕、局部剥落露砖"""
    base = rgb(134, 58, 44)
    arr = np.ones((S, S, 3), dtype=np.float32) * base

    u = np.linspace(0, 1, S, dtype=np.float32)
    v = np.linspace(0, 1, S, dtype=np.float32)      # v=0 为墙脚
    U, V = np.meshgrid(u, v)

    n1 = fbm(S, seed=131)
    n2 = fbm(S, octaves=(16, 48, 128), weights=(0.55, 0.3, 0.15), seed=137)

    # 整体色斑（抹灰不均）
    arr *= (0.86 + 0.26 * n1)[:, :, None]
    arr *= (0.93 + 0.14 * n2)[:, :, None]

    # 墙脚返潮：下 22% 逐渐发暗发灰
    damp = np.clip((0.22 - V) / 0.22, 0, 1) ** 1.4
    damp *= 0.55 + 0.45 * n1
    arr = arr * (1 - damp[:, :, None] * 0.72) + rgb(58, 44, 36) * (damp[:, :, None] * 0.72)

    # 雨痕：竖向条状暗纹
    streak = np.clip(np.sin(U * 74.0 + n2 * 6.0) * 0.5 + 0.5, 0, 1) ** 6
    streak *= np.clip((0.85 - V) / 0.85, 0, 1) ** 0.6
    arr *= (1 - 0.16 * streak)[:, :, None]

    # 剥落：露出内层灰浆 / 砖
    peel = np.clip((n2 - 0.74) * 7.0, 0, 1)
    peel *= np.clip((0.62 - V) / 0.62, 0, 1)
    arr = arr * (1 - peel[:, :, None]) + rgb(112, 104, 92) * peel[:, :, None]

    arr += np.random.default_rng(139).normal(0.0, 0.020, (S, S, 1)).astype(np.float32)
    save(arr, "plaster")
    return arr


# ============================ 树皮 ============================
def bark_tex(S=512):
    """老槐树皮：深灰褐，纵向深裂，沟底近黑"""
    base = rgb(74, 62, 50)
    u = np.linspace(0, 1, S, dtype=np.float32)
    v = np.linspace(0, 1, S, dtype=np.float32)
    U, V = np.meshgrid(u, v)

    n1 = fbm(S, octaves=(6, 12, 32), weights=(0.5, 0.3, 0.2), seed=151)
    n2 = fbm(S, octaves=(24, 96, 192), weights=(0.5, 0.3, 0.2), seed=157)

    # 纵向裂纹：低频横向调制 + 竖向拉伸
    crack = np.abs(np.sin(U * 26.0 + n1 * 5.2 + np.sin(V * 7.0) * 0.9))
    crack = np.clip(crack, 0, 1) ** 0.34
    shade = 0.30 + 0.92 * crack

    arr = np.ones((S, S, 3), dtype=np.float32) * base
    arr *= shade[:, :, None]
    arr *= (0.86 + 0.30 * n2)[:, :, None]

    # 苔痕（背阴处）
    moss = np.clip((n1 - 0.70) * 4.6, 0, 1) * 0.30
    arr = arr * (1 - moss[:, :, None]) + rgb(52, 60, 40) * moss[:, :, None]

    arr += np.random.default_rng(163).normal(0.0, 0.024, (S, S, 1)).astype(np.float32)
    save(arr, "bark")
    return arr


# ============================ 叶簇 ============================
def leaf_tex(S=512):
    """叶簇：深浅不一的团簇，中心厚、边缘薄（边缘压暗，做出体积）"""
    base = rgb(88, 104, 56)
    u = np.linspace(-1, 1, S, dtype=np.float32)
    v = np.linspace(-1, 1, S, dtype=np.float32)
    U, V = np.meshgrid(u, v)
    R = np.sqrt(U * U + V * V)

    n1 = fbm(S, octaves=(8, 20, 56), weights=(0.45, 0.32, 0.23), seed=173)
    n2 = fbm(S, octaves=(40, 120, 256), weights=(0.5, 0.3, 0.2), seed=179)

    # 小叶片：高频斑块
    blade = np.clip(np.sin(U * 96.0 + n1 * 12.0) * np.sin(V * 84.0 - n1 * 9.0), 0, 1) ** 0.5

    arr = np.ones((S, S, 3), dtype=np.float32) * base
    arr *= (0.62 + 0.80 * n1)[:, :, None]
    arr *= (0.84 + 0.42 * n2)[:, :, None]
    arr *= (0.86 + 0.30 * blade)[:, :, None]

    # 边缘压暗，团簇有体积
    edge = np.clip(R / 0.92, 0, 1) ** 2.2
    arr *= (1 - 0.42 * edge)[:, :, None]

    # 少量枯黄叶
    dry = np.clip((n2 - 0.80) * 6.0, 0, 1) * 0.55
    arr = arr * (1 - dry[:, :, None]) + rgb(96, 82, 40) * dry[:, :, None]

    save(arr, "leaf")
    return arr


paving_tex()
plaster_tex()
bark_tex()
leaf_tex()
print("SITE_TEXTURES_DONE ->", OUT)
