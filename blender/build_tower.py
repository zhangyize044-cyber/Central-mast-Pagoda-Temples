# -*- coding: utf-8 -*-
"""
正定天宁寺凌霄塔 · 参数化重建 v2
================================================================
形制依据（公开测绘资料）：
  通高 40.98 m / 九级 / 平面八角 / 楼阁式
  下三层砖构（斗拱砖仿木，宋重修），四层以上斗拱及檐口木构（金重建）
  八角形台基，首层甚高，四正面辟圆拱门，四隅面设窗
  每面三开间，四层起立木质塔心柱 17 m，八根扒梁放射连接塔壁转角

用法：
  blender --background --factory-startup --python build_tower.py
"""

import bpy
import bmesh
import math
import os
import sys

TAU = math.tau
PHASE = math.pi / 8.0
SIDES = 8
SEG = 8

OUT_DIR = os.path.dirname(os.path.abspath(__file__)) if "__file__" in dir() else os.getcwd()

# ============================ 参数 ============================
P = {
    "base_h":       2.00,
    "base_r":       6.10,
    "body_h":      34.00,
    "finial_h":     4.98,
    "r_first":      4.40,
    "taper":        0.942,
    "body_taper":   0.978,
    "brick_tiers":  3,
    "eave_brick":   0.92,
    "eave_wood":    1.18,
    "lift_brick":   0.24,
    "lift_wood":    0.32,
    "col_r":        0.145,
    "dougong_scale": 1.0,
}

TIER_H = [8.20]
_vals = [3.58 - i * 0.055 for i in range(8)]
_k = (P["body_h"] - TIER_H[0]) / sum(_vals)
TIER_H += [v * _k for v in _vals]

R_BOT = [P["r_first"] * (P["taper"] ** i) for i in range(9)]
R_TOP = [r * P["body_taper"] for r in R_BOT]


def srgb(hexstr):
    h = hexstr.lstrip("#")
    out = []
    for i in (0, 2, 4):
        c = int(h[i:i + 2], 16) / 255.0
        out.append(c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4)
    return (*out, 1.0)


MATS = {
    "stone":   ("#5F5849", 0.94, 0.00),
    "brick":   ("#4A4438", 0.92, 0.00),
    "wood":    ("#6E3A20", 0.85, 0.00),
    "tile":    ("#343B3E", 0.88, 0.02),   # v3 哑光青瓦：压住半圆弧瓦垄的镜面高光
    "dougong": ("#5E3C22", 0.82, 0.02),
    "dark":    ("#241A14", 0.90, 0.00),
    "gold":    ("#D2A64E", 0.30, 0.90),
    "metal":   ("#6E6357", 0.44, 0.55),
    "timber":  ("#9A7A4C", 0.86, 0.00),
}


TEX_DIR = os.path.join(OUT_DIR, "tex")
# 材质键 -> (贴图名, UV 缩放)；UV 缩放 = 每米多少个贴图 tile
TEXMAP = {
    "brick":   ("brick",  0.50),
    "tile":    ("tile",   0.55),
    "wood":    ("wood",   1.10),
    "stone":   ("stone",  0.30),
    "dougong": ("caihua", 3.20),
    "gold":    (None,     0.0),
    "dark":    (None,     0.0),
    "metal":   (None,     0.0),
    "timber":  (None,     0.0),
}


def box_uv(me, scale=0.5):
    """三平面盒式投影：按面法线主轴取投影平面，1 米 = scale 个 tile"""
    if me.uv_layers:
        while me.uv_layers:
            me.uv_layers.remove(me.uv_layers[0])
    uvl = me.uv_layers.new(name="UVMap")
    for poly in me.polygons:
        n = poly.normal
        ax, ay, az = abs(n.x), abs(n.y), abs(n.z)
        mode = 0 if (ax >= ay and ax >= az) else (1 if ay >= az else 2)
        for li in poly.loop_indices:
            co = me.vertices[me.loops[li].vertex_index].co
            if mode == 0:
                u, v = co.y, co.z
            elif mode == 1:
                u, v = co.x, co.z
            else:
                u, v = co.x, co.y
            uvl.data[li].uv = (u * scale, v * scale)


# ============================ 几何构建器 ============================
class Part:
    def __init__(self):
        self.v = []
        self.f = []
        self.ox = self.oy = self.oz = 0.0

    def at(self, x=0.0, y=0.0, z=0.0):
        self.ox, self.oy, self.oz = x, y, z
        return self

    def _o(self, v):
        return (v[0] + self.ox, v[1] + self.oy, v[2] + self.oz)

    def quad(self, a, b, c, d):
        i = len(self.v)
        self.v += [self._o(a), self._o(b), self._o(c), self._o(d)]
        self.f.append((i, i + 1, i + 2, i + 3))

    def tri(self, a, b, c):
        i = len(self.v)
        self.v += [self._o(a), self._o(b), self._o(c)]
        self.f.append((i, i + 1, i + 2))

    def ngon(self, pts):
        i = len(self.v)
        self.v += [self._o(x) for x in pts]
        self.f.append(tuple(range(i, i + len(pts))))

    def box(self, cx, cy, cz, sx, sy, sz, rot=0.0):
        hx, hy, hz = sx * 0.5, sy * 0.5, sz * 0.5
        ca, sa = math.cos(rot), math.sin(rot)
        cs = []
        for px, py in ((-hx, -hy), (hx, -hy), (hx, hy), (-hx, hy)):
            cs.append((cx + px * ca - py * sa, cy + px * sa + py * ca))
        b = [(x, y, cz - hz) for x, y in cs]
        t = [(x, y, cz + hz) for x, y in cs]
        self.quad(b[3], b[2], b[1], b[0])
        self.quad(t[0], t[1], t[2], t[3])
        for i in range(4):
            j = (i + 1) % 4
            self.quad(b[i], b[j], t[j], t[i])

    def oct_tube(self, r0, r1, z0, z1, n=SIDES):
        for i in range(n):
            a0 = PHASE + i * TAU / n
            a1 = PHASE + (i + 1) * TAU / n
            self.quad(
                (r0 * math.cos(a0), r0 * math.sin(a0), z0),
                (r0 * math.cos(a1), r0 * math.sin(a1), z0),
                (r1 * math.cos(a1), r1 * math.sin(a1), z1),
                (r1 * math.cos(a0), r1 * math.sin(a0), z1),
            )

    def oct_cap(self, r, z, up=True):
        pts = [(r * math.cos(PHASE + i * TAU / SIDES),
                r * math.sin(PHASE + i * TAU / SIDES), z) for i in range(SIDES)]
        self.ngon(pts if up else list(reversed(pts)))

    def eave_ring(self, r_in, r_out, z_top, drop, lift, thick, seg=SEG):
        n = SIDES * seg
        step = TAU / n
        A, B, C, D = [], [], [], []
        for i in range(n):
            a = PHASE + i * step
            lf = lift_at(a, lift)
            ca, sa = math.cos(a), math.sin(a)
            A.append((r_in * ca, r_in * sa, z_top))
            B.append((r_out * ca, r_out * sa, z_top - drop + lf))
            C.append((r_out * ca, r_out * sa, z_top - drop - thick + lf))
            D.append((r_in * ca, r_in * sa, z_top - thick))
        for i in range(n):
            j = (i + 1) % n
            self.quad(A[i], A[j], B[j], B[i])
            self.quad(B[i], C[i], C[j], B[j])
            self.quad(C[i], D[i], D[j], C[j])

    def disc_ring(self, r_in, r_out, z, n=24):
        for i in range(n):
            a0 = i * TAU / n
            a1 = (i + 1) * TAU / n
            self.quad(
                (r_in * math.cos(a0), r_in * math.sin(a0), z),
                (r_out * math.cos(a0), r_out * math.sin(a0), z),
                (r_out * math.cos(a1), r_out * math.sin(a1), z),
                (r_in * math.cos(a1), r_in * math.sin(a1), z),
            )

    def circle_tube(self, r_at, z0, z1, n=16):
        for i in range(n):
            a0 = i * TAU / n
            a1 = (i + 1) * TAU / n
            r0, r1 = r_at(z0), r_at(z1)
            self.quad(
                (r0 * math.cos(a0), r0 * math.sin(a0), z0),
                (r0 * math.cos(a1), r0 * math.sin(a1), z0),
                (r1 * math.cos(a1), r1 * math.sin(a1), z1),
                (r1 * math.cos(a0), r1 * math.sin(a0), z1),
            )

    def sphere(self, cx, cy, cz, r, seg=16, ring=10):
        verts = []
        for j in range(ring + 1):
            phi = math.pi * j / ring
            for i in range(seg):
                th = TAU * i / seg
                verts.append((cx + r * math.sin(phi) * math.cos(th),
                              cy + r * math.sin(phi) * math.sin(th),
                              cz + r * math.cos(phi)))
        for j in range(ring):
            for i in range(seg):
                i2 = (i + 1) % seg
                self.quad(verts[j * seg + i], verts[j * seg + i2],
                          verts[(j + 1) * seg + i2], verts[(j + 1) * seg + i])


# ============================ 工具 ============================
def lift_at(angle, lift):
    """翼角起翘：八角处最大，面中为零（连续函数，保证瓦垄与檐口对齐）"""
    p = ((angle - PHASE) % (TAU / SIDES)) / (TAU / SIDES)
    f = abs(2.0 * p - 1.0)
    return lift * f * f


def edge_pt(r, i, t):
    a0 = PHASE + i * TAU / SIDES
    a1 = PHASE + (i + 1) * TAU / SIDES
    return (r * ((1 - t) * math.cos(a0) + t * math.cos(a1)),
            r * ((1 - t) * math.sin(a0) + t * math.sin(a1)))


def edge_angle(i):
    return PHASE + (i + 0.5) * TAU / SIDES


def edge_tangent(i):
    return edge_angle(i) + math.pi * 0.5


def edge_len(r, i):
    a = edge_pt(r, i, 0.0)
    b = edge_pt(r, i, 1.0)
    return math.hypot(b[0] - a[0], b[1] - a[1])


# ============================ 斗拱 ============================
def add_dougong(part, cx, cy, z, rot, s, is_brick):
    if is_brick:
        # 砖仿木：扁而宽，几乎贴墙面
        part.box(cx, cy, z, 0.44 * s, 0.16 * s, 0.22 * s, rot)
        part.box(cx, cy, z + 0.15 * s, 0.62 * s, 0.20 * s, 0.13 * s, rot)
        part.box(cx, cy, z + 0.26 * s, 0.46 * s, 0.17 * s, 0.11 * s, rot)
        return
    # 木构：栌斗 -> 华拱 -> 散斗 -> 令拱 -> 耍头
    part.box(cx, cy, z, 0.38 * s, 0.24 * s, 0.20 * s, rot)              # 栌斗
    part.box(cx, cy, z + 0.165 * s, 0.60 * s, 0.21 * s, 0.13 * s, rot)  # 华拱（第一跳）
    ca, sa = math.cos(rot), math.sin(rot)
    for sx in (-1, 1):
        part.box(cx + ca * (0.235 * s * sx), cy + sa * (0.235 * s * sx),
                 z + 0.245 * s, 0.13 * s, 0.15 * s, 0.10 * s, rot)      # 散斗
    part.box(cx, cy, z + 0.325 * s, 0.46 * s, 0.27 * s, 0.11 * s, rot)  # 令拱（第二跳）
    part.box(cx, cy, z + 0.255 * s, 0.20 * s, 0.40 * s, 0.12 * s, rot)  # 耍头 / 昂尖


# ============================ 瓦垄与滴水 ============================
def add_tile_detail(part, r_in, r_out, z_top, drop, lift, thick, n_ridge=56):
    for k in range(n_ridge):
        a = PHASE + (k + 0.5) * TAU / n_ridge
        lf = lift_at(a, lift)
        wa = 0.020 / max(r_in, 0.8)
        z_in = z_top
        z_out = z_top - drop + lf
        h = 0.068
        A0 = (r_in * math.cos(a - wa), r_in * math.sin(a - wa), z_in)
        A1 = (r_in * math.cos(a + wa), r_in * math.sin(a + wa), z_in)
        B0 = (r_out * math.cos(a - wa), r_out * math.sin(a - wa), z_out)
        B1 = (r_out * math.cos(a + wa), r_out * math.sin(a + wa), z_out)
        part.quad((A0[0], A0[1], z_in + h), (A1[0], A1[1], z_in + h),
                  (B1[0], B1[1], z_out + h), (B0[0], B0[1], z_out + h))
        part.quad(A0, A1, (A1[0], A1[1], z_in + h), (A0[0], A0[1], z_in + h))
        part.quad(A0, (A0[0], A0[1], z_in + h), (B0[0], B0[1], z_out + h), B0)
        part.quad(A1, B1, (B1[0], B1[1], z_out + h), (A1[0], A1[1], z_in + h))

        # 滴水
        wa2 = 0.022 / max(r_out, 0.8)
        z0 = z_top - drop - thick + lf
        r = r_out + 0.015
        part.quad((r * math.cos(a - wa2), r * math.sin(a - wa2), z0),
                  (r * math.cos(a + wa2), r * math.sin(a + wa2), z0),
                  (r * math.cos(a + wa2), r * math.sin(a + wa2), z0 - 0.14),
                  (r * math.cos(a - wa2), r * math.sin(a - wa2), z0 - 0.14))


def add_ridge_beasts(tile, wood, r_out, z_top, lift):
    for i in range(SIDES):
        a = PHASE + i * TAU / SIDES
        ca, sa = math.cos(a), math.sin(a)
        lf = lift_at(a, lift)
        z = z_top - 0.28 + lf
        tile.box(r_out * 0.62 * ca, r_out * 0.62 * sa, z,
                 r_out * 1.04, 0.13, 0.12, rot=a)
        tile.box((r_out + 0.03) * ca, (r_out + 0.03) * sa, z + 0.11,
                 0.15, 0.15, 0.15, rot=a)


def add_bells(part, r, z, lift, n=8):
    for i in range(n):
        a = PHASE + i * TAU / n
        ca, sa = math.cos(a), math.sin(a)
        lf = lift_at(a, lift)
        zz = z + lf
        part.box((r + 0.09) * ca, (r + 0.09) * sa, zz - 0.26, 0.072, 0.072, 0.125, rot=a)
        part.box((r + 0.09) * ca, (r + 0.09) * sa, zz - 0.37, 0.028, 0.028, 0.065, rot=a)


# ============================ 台基 ============================
def build_base(stone):
    """月台 + 石栏杆 + 八角须弥座塔基，共同把塔身托住"""
    r0 = P["base_r"]
    hb = P["base_h"]
    plat_h = hb * 0.46                       # 月台高
    plat_r = r0 * 1.78                       # 月台外接圆半径

    # ---- 月台（两级，下大上小）----
    stone.oct_tube(plat_r, plat_r, 0.0, plat_h * 0.58)
    stone.oct_tube(plat_r, plat_r * 0.982, plat_h * 0.58, plat_h)
    stone.oct_cap(plat_r * 0.982, plat_h, up=True)
    stone.oct_cap(plat_r, 0.0, up=False)

    # ---- 月台石栏杆（正面 +Y 留出入口）----
    rp = plat_r * 0.972
    n_post = 6
    for i in range(SIDES):
        if i == 1:
            continue                          # 正面开口，接踏跺
        tan_a = edge_tangent(i)
        L = edge_len(rp, i)
        mx, my = edge_pt(rp, i, 0.5)
        stone.box(mx, my, plat_h + 0.46, L, 0.17, 0.60, rot=tan_a)      # 栏板
        stone.box(mx, my, plat_h + 1.04, L, 0.16, 0.16, rot=tan_a)      # 寻杖
        for m in range(n_post):
            t = m / (n_post - 1.0)
            px, py = edge_pt(rp, i, t)
            stone.box(px, py, plat_h + 0.56, 0.24, 0.24, 1.12, rot=tan_a)
            stone.box(px, py, plat_h + 1.18, 0.29, 0.29, 0.15, rot=tan_a)

    # ---- 八角须弥座（嵌在月台之上）----
    z_a, z_b = plat_h, hb
    span = z_b - z_a
    profile = [
        (r0,        0.00),
        (r0,        0.15),
        (r0 * 0.958, 0.25),
        (r0 * 1.034, 0.44),     # 束腰外凸
        (r0 * 0.964, 0.66),
        (r0 * 0.956, 0.77),
        (r0 * 1.014, 0.88),
        (r0,        0.95),
        (r0,        1.00),
    ]
    for i in range(len(profile) - 1):
        r_a, t_a = profile[i]
        r_b, t_b = profile[i + 1]
        stone.oct_tube(r_a, r_b, z_a + t_a * span, z_a + t_b * span)
    stone.oct_cap(r0, hb, up=True)

    # 束腰壶门
    for i in range(SIDES):
        tan_a = edge_tangent(i)
        for t in (0.32, 0.68):
            px, py = edge_pt(r0 * 1.012, i, t)
            stone.box(px, py, z_a + span * 0.55, 0.34, 0.055, span * 0.26, rot=tan_a)

    # ---- 正面踏跺：自月台外缘上至塔基顶 ----
    steps = 7
    for k in range(steps):
        w = 5.8 - k * 0.30
        zc = hb * (k + 1) / steps
        stone.box(0.0, plat_r + 0.18 + (steps - 1 - k) * 0.44,
                  zc * 0.5, w, 0.46, zc)


# ============================ 塔心柱 ============================
def build_heart_column(timber):
    """四层起立的木质塔心柱 + 八根抱柱 + 逐层八根扒梁（放射连接塔壁转角）"""
    z_start = P["base_h"] + sum(TIER_H[:3])     # 第四层底
    z_end = P["base_h"] + P["body_h"]           # 塔身顶
    col_r = 0.32

    timber.circle_tube(lambda z: col_r, z_start, z_end, n=20)
    timber.disc_ring(0.0, col_r, z_end, n=20)                 # 柱顶收头
    timber.circle_tube(lambda z: col_r * 1.48, z_start - 0.30, z_start, n=20)  # 柱础
    timber.disc_ring(0.0, col_r * 1.48, z_start - 0.30, n=20)

    # 八根抱柱
    for i in range(SIDES):
        a = PHASE + i * TAU / SIDES
        px, py = math.cos(a) * (col_r + 0.105), math.sin(a) * (col_r + 0.105)
        timber.at(px, py, 0.0)
        timber.circle_tube(lambda z: 0.105, z_start + 0.25, z_end - 0.25, n=10)
        timber.at()

    # 逐层八根扒梁：自抱柱放射至塔壁转角
    for idx in range(3, 9):
        z_top = P["base_h"] + sum(TIER_H[:idx + 1])
        r_in = col_r + 0.22
        r_out = R_TOP[idx] - 0.30
        if r_out <= r_in:
            continue
        L = r_out - r_in
        rm = (r_in + r_out) * 0.5
        for i in range(SIDES):
            a = PHASE + i * TAU / SIDES
            timber.box(math.cos(a) * rm, math.sin(a) * rm, z_top - 0.36,
                       L, 0.23, 0.27, rot=a)
            timber.box(math.cos(a) * r_in, math.sin(a) * r_in, z_top - 0.36,
                       0.30, 0.34, 0.34, rot=a)


# ============================ 配属设施 ============================
def build_props(stone):
    """塔前石狮与香炉已划归场地环境（build_site.py）统一定位，此处不再生成"""
    return


# ============================ 一层 ============================
def build_tier(body, dg, tile, dark, woodp, metal, idx, gold):
    is_brick = idx < P["brick_tiers"]
    rb, rt = R_BOT[idx], R_TOP[idx]
    z0 = P["base_h"] + sum(TIER_H[:idx])
    z1 = z0 + TIER_H[idx]
    h = TIER_H[idx]
    s = P["dougong_scale"]

    # 塔身（卷杀曲线收分）
    steps = 4
    for k in range(steps):
        t0 = k / steps
        t1 = (k + 1) / steps
        ra = rb + (rt - rb) * (t0 ** 1.18)
        rbz = rb + (rt - rb) * (t1 ** 1.18)
        body.oct_tube(ra, rbz, z0 + h * t0, z0 + h * t1)

    if idx >= 1:
        body.oct_tube(rb * 1.052, rb * 1.052, z0 - 0.05, z0 + 0.17)
        body.oct_tube(rb * 1.052, rb, z0 + 0.17, z0 + 0.23)

    for i in range(SIDES):
        th = edge_angle(i)
        tan_a = edge_tangent(i)
        ux, uy = math.cos(tan_a), math.sin(tan_a)
        nx, ny = math.cos(th), math.sin(th)
        face_w = edge_len(rb, i)

        # 檐柱 + 柱础 + 柱头
        for t in (0.0, 1.0 / 3.0, 2.0 / 3.0, 1.0):
            px, py = edge_pt(rb, i, t)
            px *= (1.0 - 0.055 / rb)
            py *= (1.0 - 0.055 / rb)
            cw = P["col_r"] * 2
            body.box(px, py, z0 + h * 0.5, cw, cw, h * 0.994, rot=tan_a)
            body.box(px, py, z0 + 0.10, cw * 1.34, cw * 1.34, 0.20, rot=tan_a)
            body.box(px, py, z1 - 0.18, cw * 1.30, cw * 1.30, 0.18, rot=tan_a)

        # 门窗
        cx, cy = edge_pt(rb, i, 0.5)
        cx *= (1.0 + 0.002 / rb)
        cy *= (1.0 + 0.002 / rb)

        def place(su, sv, out=0.06):
            return (cx + ux * su + nx * out, cy + uy * su + ny * out, z0 + sv)

        if i % 2 == 1:
            dw = min(face_w * 0.33, 1.30)
            dh = h * (0.60 if idx == 0 else 0.50)
            rr = dw * 0.5
            prof = [(-dw / 2, 0.0), (dw / 2, 0.0)]
            for k in range(9):
                ang = math.pi * k / 8.0
                prof.append((rr * math.cos(ang), dh - rr + rr * math.sin(ang)))
            dark.ngon([place(su, sv, -0.26) for su, sv in prof])
            # 门洞侧壁：v3 纵深由 10 cm 加深到 30 cm
            for k in range(len(prof) - 1):
                p0, p1 = prof[k], prof[k + 1]
                body.ngon([place(p0[0], p0[1], 0.045), place(p1[0], p1[1], 0.045),
                           place(p1[0], p1[1], -0.26), place(p0[0], p0[1], -0.26)])
            # 门框立柱
            for sx in (-1, 1):
                x0 = sx * dw / 2
                body.ngon([place(x0, 0.0, 0.075), place(x0 + sx * 0.11, 0.0, 0.075),
                           place(x0 + sx * 0.11, dh * 0.72, 0.075),
                           place(x0, dh * 0.72, 0.075)])
            # 拱券石圈
            for k in range(8):
                a0 = math.pi * k / 8.0
                a1 = math.pi * (k + 1) / 8.0
                p0 = (rr * math.cos(a0), dh - rr + rr * math.sin(a0))
                p1 = (rr * math.cos(a1), dh - rr + rr * math.sin(a1))
                if abs(p1[0] - p0[0]) < 1e-6:
                    continue
                body.ngon([place(p0[0], p0[1], 0.075), place(p1[0], p1[1], 0.075),
                           place(p1[0] * 1.26, p1[1] + 0.05, 0.075),
                           place(p0[0] * 1.26, p0[1] + 0.05, 0.075)])
            add_door_leaf(dark, body, gold, place, dw, dh, rr, idx)
            add_plaque(body, gold, place, face_w, dh, idx)
        else:
            ww = face_w * 0.40
            wh = h * 0.30
            wz = h * 0.32
            dark.ngon([place(-ww / 2, wz, -0.26), place(ww / 2, wz, -0.26),
                       place(ww / 2, wz + wh, -0.26), place(-ww / 2, wz + wh, -0.26)])
            # 窗侧壁：v3 同步加深到 30 cm
            for (a0, a1, b0, b1) in ((-ww/2, ww/2, wz, wz), (-ww/2, ww/2, wz+wh, wz+wh),
                                     (-ww/2, -ww/2, wz, wz+wh), (ww/2, ww/2, wz, wz+wh)):
                body.ngon([place(a0, b0 - 0.075, 0.045), place(a1, b1 - 0.075, 0.045),
                           place(a1, b1 - 0.075, -0.26), place(a0, b0 - 0.075, -0.26)])
            fw = 0.075
            body.ngon([place(-ww / 2 - fw, wz - fw, 0.07), place(ww / 2 + fw, wz - fw, 0.07),
                       place(ww / 2 + fw, wz, 0.07), place(-ww / 2 - fw, wz, 0.07)])
            body.ngon([place(-ww / 2 - fw, wz + wh, 0.07), place(ww / 2 + fw, wz + wh, 0.07),
                       place(ww / 2 + fw, wz + wh + fw, 0.07), place(-ww / 2 - fw, wz + wh + fw, 0.07)])
            for m in range(1, 5):
                sx = -ww / 2 + ww * m / 5.0
                db = 0.030
                body.ngon([place(sx - db, wz, 0.09), place(sx + db, wz, 0.09),
                           place(sx + db, wz + wh, 0.09), place(sx - db, wz + wh, 0.09)])
            add_lattice(body, place, ww, wh, wz)

        # 斗拱
        for t in (1.0 / 6.0, 0.5, 5.0 / 6.0):
            px, py = edge_pt(rb, i, t)
            px *= (1.0 + 0.042 / rb)
            py *= (1.0 + 0.042 / rb)
            add_dougong(dg, px, py, z1 - 0.13 * s, tan_a, s, is_brick)

    # 檐口
    eave = P["eave_brick"] if is_brick else P["eave_wood"]
    lift = P["lift_brick"] if is_brick else P["lift_wood"]
    # v3：上部三层逐级收檐，解决 8–9 层被下层檐口挤压遮挡
    shrink = 1.0 - 0.075 * max(0, idx - 5)
    eave *= shrink
    lift *= 1.0 - 0.06 * max(0, idx - 5)
    drop = 0.48 if is_brick else 0.62
    thick = 0.26
    tile.eave_ring(rt, rt + eave, z1, drop, lift, thick)
    add_tile_detail(tile, rt, rt + eave, z1, drop, lift, thick)
    add_ridge_beasts(tile, woodp, rt + eave, z1, lift)
    add_bells(metal, rt + eave, z1 - drop - thick, lift)

    # 平座
    if idx >= 1:
        rp = rb + 0.40
        tile.disc_ring(rb - 0.04, rp + 0.10, z0 + 0.015, n=48)
        n_post = 5
        for i in range(SIDES):
            tan_a = edge_tangent(i)
            L = edge_len(rp, i)
            mx, my = edge_pt(rp, i, 0.5)
            woodp.box(mx, my, z0 + 0.20, L, 0.055, 0.30, rot=tan_a)   # 华板
            woodp.box(mx, my, z0 + 0.68, L, 0.055, 0.055, rot=tan_a)  # 寻杖
            for m in range(n_post):
                t = m / (n_post - 1.0)
                px, py = edge_pt(rp, i, t)
                woodp.box(px, py, z0 + 0.38, 0.085, 0.085, 0.76, rot=tan_a)
                woodp.box(px, py, z0 + 0.80, 0.115, 0.115, 0.09, rot=tan_a)

    return z1


# ============================ 顶层与塔刹 ============================
def build_roof_and_finial(tile, gold, woodp, metal, z9_top):
    rt = R_TOP[8]
    r_out = rt + P["eave_wood"]
    lift = P["lift_wood"]
    roof_h = 2.10
    z_apex = z9_top + roof_h
    drop = 0.62
    thick = 0.26
    n = SIDES * SEG
    step = TAU / n

    tile.eave_ring(rt, r_out, z9_top, drop, lift, thick)
    add_tile_detail(tile, rt, r_out, z9_top, drop, lift, thick)
    add_bells(metal, r_out, z9_top - drop - thick, lift)

    r_apex = 0.62
    z_eave = z9_top - drop
    outer, mid, inner = [], [], []
    for i in range(n):
        a = PHASE + i * step
        ca, sa = math.cos(a), math.sin(a)
        lf = lift_at(a, lift)
        outer.append((r_out * ca, r_out * sa, z_eave + lf))
        rm = r_out * 0.44
        zm = z_eave + lf * 0.5 + (z_apex - z_eave) * 0.30
        mid.append((rm * ca, rm * sa, zm))
        inner.append((r_apex * ca, r_apex * sa, z_apex))
    for i in range(n):
        j = (i + 1) % n
        tile.quad(outer[i], outer[j], mid[j], mid[i])
        tile.quad(mid[i], mid[j], inner[j], inner[i])

    for i in range(SIDES):
        a = PHASE + i * TAU / SIDES
        ca, sa = math.cos(a), math.sin(a)
        tile.box(r_out * 0.56 * ca, r_out * 0.56 * sa,
                 z_eave + lift_at(a, lift) * 0.85 + roof_h * 0.36,
                 r_out * 1.0, 0.16, 0.14, rot=a)
    tile.oct_cap(r_apex + 0.05, z_apex, up=True)

    z = z_apex
    gold.oct_tube(0.70, 0.62, z, z + 0.16)
    gold.oct_cap(0.70, z, up=False)
    gold.oct_tube(0.62, 0.55, z + 0.16, z + 0.30)
    z += 0.30
    gold.circle_tube(lambda zz: 0.55 - (zz - z) * 0.42, z, z + 0.34, n=18)
    gold.oct_cap(0.55 - 0.34 * 0.42, z + 0.34, up=True)
    z += 0.34
    for k in range(8):
        rr = 0.60 - k * 0.008
        zz = z + k * 0.195
        gold.disc_ring(max(0.02, rr - 0.105), rr, zz, n=22)
        gold.circle_tube(lambda t, r_=rr: r_, zz, zz + 0.048, n=22)
    z += 8 * 0.195
    gold.oct_cap(0.12, z + 0.16, up=True)
    gold.oct_tube(0.60, 0.12, z + 0.02, z + 0.16)
    z += 0.16
    gold.disc_ring(0.06, 0.19, z + 0.03, n=16)
    gold.sphere(0.0, 0.0, z + 0.26, 0.21, seg=18, ring=12)
    gold.sphere(0.0, 0.0, z + 0.58, 0.13, seg=14, ring=9)
    gold.circle_tube(lambda t: 0.05, z_apex, z + 0.72, n=10)
    add_finial_detail(gold, metal, z, z_apex, r_out, z_eave, lift)


# ============================ 组装 ============================
def clear_scene():
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(use_global=False)
    for blk in (bpy.data.meshes, bpy.data.materials, bpy.data.objects):
        for item in list(blk):
            if item.users == 0:
                blk.remove(item)


def to_object(name, part, mat_key):
    if not part.f:
        return None
    me = bpy.data.meshes.new(name)
    me.from_pydata(part.v, [], part.f)
    me.validate(verbose=False)
    me.update()

    bm = bmesh.new()
    bm.from_mesh(me)
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-5)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bm.to_mesh(me)
    bm.free()

    hexcol, rough, metal_v = MATS[mat_key]
    mat = bpy.data.materials.new(name + "_mat")
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes.get("Principled BSDF")
    bsdf.inputs["Base Color"].default_value = srgb(hexcol)
    bsdf.inputs["Roughness"].default_value = rough
    bsdf.inputs["Metallic"].default_value = metal_v

    tex_name, uv_scale = TEXMAP.get(mat_key, (None, 0.0))
    if tex_name:
        p_tex = os.path.join(TEX_DIR, tex_name + ".png")
        if os.path.exists(p_tex):
            box_uv(me, uv_scale)
            img = bpy.data.images.load(p_tex, check_existing=True)
            img.colorspace_settings.name = "sRGB"
            node = mat.node_tree.nodes.new("ShaderNodeTexImage")
            node.image = img
            node.extension = "REPEAT"
            node.interpolation = "Smart"
            node.location = (-420, 220)
            mat.node_tree.links.new(node.outputs["Color"], bsdf.inputs["Base Color"])
            # glTF 会把 baseColorFactor 与贴图相乘，接了贴图必须置白，否则双重变暗
            bsdf.inputs["Base Color"].default_value = (1.0, 1.0, 1.0, 1.0)
            print("  tex ->", name, tex_name, "uvscale", uv_scale)

    me.materials.append(mat)

    ob = bpy.data.objects.new(name, me)
    bpy.context.collection.objects.link(ob)
    ob.data.shade_flat()
    return ob


def main():
    clear_scene()

    parts = {k: Part() for k in ("base", "body_low", "body_up", "dg", "dg_wood",
                                  "tile_low", "tile_up", "dark", "gold", "rail", "metal", "timber")}
    M = {
        "base":  ("stone",   "Base_Stone"),
        "body_low": ("brick", "Body_Lower"),
        "body_up":  ("brick", "Body_Upper"),
        "dg":    ("brick",   "Dougong_Brick"),
        "dg_wood": ("dougong", "Dougong_Wood"),
        "tile_low": ("tile", "Eave_Lower"),
        "tile_up":  ("tile", "Eave_Upper"),
        "dark":  ("dark",    "Openings"),
        "gold":  ("gold",    "Finial_Gold"),
        "rail":  ("wood",    "Body_Wood_Railing"),
        "metal": ("metal",   "Bells_Metal"),
        "timber": ("timber", "Heart_Column_Braces"),
    }

    build_base(parts["base"])
    build_props(parts["base"])
    build_heart_column(parts["timber"])

    z = P["base_h"]
    for idx in range(9):
        # 塔身通体砖砌；下三层与四层以上拆成两组，便于网页端只对上部做剖视
        lo = idx < P["brick_tiers"]
        body_part = parts["body_low"] if lo else parts["body_up"]
        tile_part = parts["tile_low"] if lo else parts["tile_up"]
        dg_part = parts["dg"] if lo else parts["dg_wood"]
        z = build_tier(body_part, dg_part, tile_part, parts["dark"],
                       parts["rail"], parts["metal"], idx, parts["gold"])

    build_roof_and_finial(parts["tile_up"], parts["gold"], parts["rail"], parts["metal"], z)

    objs = []
    for key, part in parts.items():
        mat_key, name = M[key]
        ob = to_object(name, part, mat_key)
        if ob:
            objs.append(ob)

    tri_total = sum(len(o.data.polygons) for o in objs)
    print("PARTS:", [(o.name, len(o.data.polygons)) for o in objs])

    target = P["base_h"] + P["body_h"] + P["finial_h"]
    zs = [v.co.z for o in objs for v in o.data.vertices]
    cur = max(zs) - min(zs)
    if abs(cur - target) > 1e-3:
        sc = target / cur
        for o in objs:
            o.scale = (sc, sc, sc)
            bpy.context.view_layer.objects.active = o
            o.select_set(True)
        bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
        for o in objs:
            o.select_set(False)
        print("normalized_scale:", round(sc, 5))

    zs = [v.co.z for o in objs for v in o.data.vertices]
    print("bbox_height:", round(max(zs) - min(zs), 2))

    glb = os.path.join(OUT_DIR, "lingxiao_tower.glb")
    bpy.ops.export_scene.gltf(filepath=glb, export_format="GLB", export_apply=True,
                              export_yup=True, use_selection=False,
                              export_cameras=False, export_lights=False,
                              export_image_format="AUTO", export_texcoords=True,
                              export_normals=True)
    bpy.ops.wm.save_as_mainfile(filepath=os.path.join(OUT_DIR, "lingxiao_tower.blend"))

    print("=== DONE ===")
    print("faces:", tri_total)
    print("glb_mb:", round(os.path.getsize(glb) / 1024.0 / 1024.0, 2))


# ============================ v3 细部覆盖层 ============================
# 同名重定义：main() 在最后调用，运行时这些实现会覆盖上面的 v2 版本。
# 所有构件仍挂回原有 part，因此 object 名、材质与网页剖视分组完全不变。

def _pt(cx, cy, z, rot, u, out, w):
    """局部 -> 世界：u 沿面切向，out 沿外法线，w 竖直"""
    ca, sa = math.cos(rot), math.sin(rot)
    return (cx + ca * u + sa * out, cy + sa * u - ca * out, z + w)


def extrude_axis(part, cx, cy, z, rot, f0, f1, poly, axis="u"):
    """闭合轮廓 (a,w) 沿主轴成型、沿副轴挤出（拱/昂/月牙/耍头通用）"""
    def P(a, w, f):
        if axis == "out":
            return _pt(cx, cy, z, rot, f, a, w)
        return _pt(cx, cy, z, rot, a, f, w)

    front = [P(a, w, f0) for a, w in poly]
    back = [P(a, w, f1) for a, w in poly]
    part.ngon(front)
    part.ngon(list(reversed(back)))
    for k in range(len(poly)):
        j = (k + 1) % len(poly)
        part.quad(front[k], front[j], back[j], back[k])


def gong_outline(L, t, center=0.0, petals=4, n=12):
    """拱瓣卷杀：端部下缘逐瓣内收、上缘起翘"""
    top, bot = [], []
    for k in range(n + 1):
        a = -L * 0.5 + L * k / n
        q = abs(a) / (L * 0.5)
        c = max(0.0, (q - 0.58) / 0.42)
        pet = abs(math.sin(c * petals * math.pi)) * 0.024 if c > 0 else 0.0
        top.append((a + center, t * 0.5 + t * 0.18 * c * c + pet * 0.35))
        bot.append((a + center, -t * 0.5 + t * 0.60 * c + pet))
    return top + list(reversed(bot))


def add_gong(part, cx, cy, z, rot, L, t, depth, out0, center=0.0):
    extrude_axis(part, cx, cy, z, rot, out0, out0 + depth, gong_outline(L, t, center))


def ribbon(part, p0, p1, w):
    """两点之间的薄带（刹链）"""
    dx, dy = p1[0] - p0[0], p1[1] - p0[1]
    L = math.hypot(dx, dy) or 1.0
    px, py = -dy / L * w, dx / L * w
    part.quad((p0[0] + px, p0[1] + py, p0[2]), (p0[0] - px, p0[1] - py, p0[2]),
              (p1[0] - px, p1[1] - py, p1[2]), (p1[0] + px, p1[1] + py, p1[2]))


def add_dougong(part, cx, cy, z, rot, s, is_brick):
    """v3 真斗拱：栌斗/泥道拱/华拱/昂/散斗/令拱/耍头/替木，带拱瓣卷杀"""
    Q = 0.62                       # 竖向压缩，保证斗拱仍藏在檐下
    if is_brick:
        part.box(cx, cy, z + 0.06 * Q * s, 0.42 * s, 0.22 * s, 0.14 * Q * s, rot)
        add_gong(part, cx, cy, z + 0.19 * Q * s, rot, 0.66 * s, 0.12 * s, 0.16 * s, -0.02 * s)
        add_gong(part, cx, cy, z + 0.33 * Q * s, rot, 0.84 * s, 0.10 * s, 0.13 * s, -0.02 * s)
        return
    part.box(cx, cy, z + 0.06 * Q * s, 0.40 * s, 0.26 * s, 0.13 * Q * s, rot)   # 栌斗
    part.box(cx, cy, z + 0.13 * Q * s, 0.47 * s, 0.30 * s, 0.055 * Q * s, rot)  # 斗耳 / 斗口
    add_gong(part, cx, cy, z + 0.20 * Q * s, rot, 0.74 * s, 0.11 * s, 0.20 * s, -0.10 * s)
    hp = [(a + 0.34 * s, w * Q) for a, w in gong_outline(0.70 * s, 0.12 * s)]
    extrude_axis(part, cx, cy, z + 0.27 * Q * s, rot, -0.10 * s, 0.10 * s, hp, axis="out")
    ang = [(0.04 * s, 0.26 * Q * s), (0.92 * s, -0.16 * Q * s),
           (0.92 * s, -0.27 * Q * s), (0.04 * s, 0.14 * Q * s)]
    extrude_axis(part, cx, cy, z + 0.31 * Q * s, rot, -0.075 * s, 0.075 * s, ang, axis="out")
    for du in (-0.30, 0.0, 0.30):
        px, py, pz = _pt(cx, cy, z + 0.40 * Q * s, rot, du * s, 0.01 * s, 0)
        part.box(px, py, pz, 0.14 * s, 0.16 * s, 0.10 * Q * s, rot)             # 散斗 / 齐心斗
    add_gong(part, cx, cy, z + 0.47 * Q * s, rot, 0.96 * s, 0.10 * s, 0.18 * s, 0.0)
    head = [(0.08 * s, 0.56 * Q * s), (0.50 * s, 0.56 * Q * s),
            (0.50 * s, 0.40 * Q * s), (0.36 * s, 0.40 * Q * s),
            (0.36 * s, 0.47 * Q * s), (0.08 * s, 0.47 * Q * s)]
    extrude_axis(part, cx, cy, z + 0.40 * Q * s, rot, -0.085 * s, 0.085 * s, head, axis="out")
    px, py, pz = _pt(cx, cy, z + 0.56 * Q * s, rot, 0.0, 0.02 * s, 0)
    part.box(px, py, pz, 0.92 * s, 0.16 * s, 0.07 * Q * s, rot)                 # 替木


def add_tile_detail(part, r_in, r_out, z_top, drop, lift, thick, n_ridge=56):
    """v3 筒瓦：半圆弧瓦垄 + 勾头瓦当 + 如意滴水"""
    ARC = 6
    for k in range(n_ridge):
        a = PHASE + (k + 0.5) * TAU / n_ridge
        lf = lift_at(a, lift)
        wa = 0.021 / max(r_in, 0.8)
        h = 0.075
        z_in, z_out = z_top, z_top - drop + lf
        prev = None
        for m in range(ARC + 1):
            q = -1.0 + 2.0 * m / ARC
            ang = a + wa * q
            hh = h * math.sqrt(max(0.0, 1.0 - q * q))
            p0 = (r_in * math.cos(ang), r_in * math.sin(ang), z_in + hh)
            p1 = (r_out * math.cos(ang), r_out * math.sin(ang), z_out + hh)
            if prev is not None:
                part.quad(prev[0], prev[1], p1, p0)
            prev = (p0, p1)
        # 勾头瓦当：只留一枚小圆片。v3 初版给每垄加了侧壁与双圆片，
        # 在翼角起翘区会多层自叠加、被多光源烧成白块，这里全部撤掉。
        r = r_out + 0.012
        w2 = 0.024 / max(r_out, 0.8)
        ring = []
        for t in range(8):
            th = t * TAU / 8
            aa = a + w2 * math.cos(th)
            ring.append((r * math.cos(aa), r * math.sin(aa),
                         z_out + 0.030 + 0.028 * math.sin(th)))
        part.ngon(ring)
        z1 = z_top - drop - thick + lf
        rr = r_out + 0.018
        w3 = 0.026 / max(r_out, 0.8)
        part.ngon([(rr * math.cos(a - w3), rr * math.sin(a - w3), z1),
                   (rr * math.cos(a + w3), rr * math.sin(a + w3), z1),
                   (rr * math.cos(a + w3), rr * math.sin(a + w3), z1 - 0.10),
                   (rr * math.cos(a), rr * math.sin(a), z1 - 0.19),
                   (rr * math.cos(a - w3), rr * math.sin(a - w3), z1 - 0.10)])


def add_ridge_beasts(tile, wood, r_out, z_top, lift):
    """v3 垂脊走兽：每角三只蹲兽 + 垂兽"""
    for i in range(SIDES):
        a = PHASE + i * TAU / SIDES
        ca, sa = math.cos(a), math.sin(a)
        lf = lift_at(a, lift)
        tile.box(r_out * 0.86 * ca, r_out * 0.86 * sa, z_top - 0.22 + lf,
                 r_out * 0.32, 0.15, 0.13, rot=a)
        # v3.1：每角只留一只小蹲兽。三只兽 + 垂脊在翼角叠了 13 个 box，
        # 多光源下会聚成整片过曝白块；收敛后器物细节仍在，翼角恢复干净。
        r = r_out * 0.96
        z = z_top - 0.26 + lf
        cx, cy = r * ca, r * sa
        tile.box(cx, cy, z + 0.07, 0.11, 0.09, 0.13, rot=a)
        tile.box(cx + 0.065 * ca, cy + 0.065 * sa, z + 0.16, 0.07, 0.07, 0.07, rot=a)


def add_bells(part, r, z, lift, n=8):
    """v3 钟形风铎：吊绳 + 钟身 + 悬舌"""
    for i in range(n):
        a = PHASE + i * TAU / n
        ca, sa = math.cos(a), math.sin(a)
        zz = z + lift_at(a, lift)
        cx, cy = (r + 0.09) * ca, (r + 0.09) * sa
        part.box(cx, cy, zz - 0.09, 0.026, 0.026, 0.18, rot=a)
        r0, r1, h, seg = 0.050, 0.082, 0.19, 8
        for k in range(seg):
            a0, a1 = k * TAU / seg, (k + 1) * TAU / seg
            part.quad((cx + r0 * math.cos(a0), cy + r0 * math.sin(a0), zz - 0.19),
                      (cx + r0 * math.cos(a1), cy + r0 * math.sin(a1), zz - 0.19),
                      (cx + r1 * math.cos(a1), cy + r1 * math.sin(a1), zz - 0.19 - h),
                      (cx + r1 * math.cos(a0), cy + r1 * math.sin(a0), zz - 0.19 - h))
        part.box(cx, cy, zz - 0.42, 0.030, 0.030, 0.07, rot=a)


def add_door_leaf(dark, body, gold, place, dw, dh, rr, idx):
    """v3 门扇纵深：双扇实榻门 + 门钉 + 铺首 + 三重内收券石"""
    d0 = -0.235
    for sx in (-1, 1):
        x0, x1 = (0.0, dw / 2) if sx > 0 else (-dw / 2, 0.0)
        dark.ngon([place(x0, 0.0, d0), place(x1, 0.0, d0),
                   place(x1, dh - rr, d0), place(x0, dh - rr, d0)])
    rows = 6 if idx == 0 else 3
    cols = 5 if idx == 0 else 3
    for sx in (-1, 1):
        for m in range(1, cols + 1):
            for n in range(1, rows + 1):
                u = sx * (dw * 0.5) * m / (cols + 1)
                w = (dh - rr) * n / (rows + 1)
                gold.ngon([place(u - 0.018, w - 0.018, d0 + 0.012),
                           place(u + 0.018, w - 0.018, d0 + 0.012),
                           place(u + 0.018, w + 0.018, d0 + 0.012),
                           place(u - 0.018, w + 0.018, d0 + 0.012)])
        u, w = sx * dw * 0.30, dh * 0.42
        gold.ngon([place(u - 0.055, w - 0.055, d0 + 0.02),
                   place(u + 0.055, w - 0.055, d0 + 0.02),
                   place(u + 0.055, w + 0.055, d0 + 0.02),
                   place(u - 0.055, w + 0.055, d0 + 0.02)])
    for layer in (1, 2, 3):
        off = -0.055 - layer * 0.055
        for k in range(8):
            a0 = math.pi * k / 8.0
            a1 = math.pi * (k + 1) / 8.0
            p0 = (rr * math.cos(a0), dh - rr + rr * math.sin(a0))
            p1 = (rr * math.cos(a1), dh - rr + rr * math.sin(a1))
            body.ngon([place(p0[0], p0[1], off), place(p1[0], p1[1], off),
                       place(p1[0] * 1.06, p1[1] - 0.03, off),
                       place(p0[0] * 1.06, p0[1] - 0.03, off)])


def add_plaque(body, gold, place, face_w, dh, idx):
    """首层四正面匾额：石框 + 黑漆匾心 + 贴金字形"""
    if idx != 0:
        return
    w, h, y0 = min(face_w * 0.52, 1.55), 0.46, dh + 0.18
    gold.ngon([place(-w / 2, y0, 0.085), place(w / 2, y0, 0.085),
               place(w / 2, y0 + h, 0.085), place(-w / 2, y0 + h, 0.085)])
    body.ngon([place(-w / 2 + 0.045, y0 + 0.05, 0.095), place(w / 2 - 0.045, y0 + 0.05, 0.095),
               place(w / 2 - 0.045, y0 + h - 0.05, 0.095), place(-w / 2 + 0.045, y0 + h - 0.05, 0.095)])
    for j in range(3):
        u = -w * 0.30 + j * w * 0.30
        gold.ngon([place(u - 0.075, y0 + 0.14, 0.105), place(u + 0.075, y0 + 0.14, 0.105),
                   place(u + 0.075, y0 + h - 0.14, 0.105), place(u - 0.075, y0 + h - 0.14, 0.105)])


def add_lattice(body, place, ww, wh, wz):
    """v3 窗棂：横竖格 + 窗台"""
    d = 0.10
    for m in range(1, 4):
        v = wz + wh * m / 4.0
        body.ngon([place(-ww / 2, v - 0.014, d), place(ww / 2, v - 0.014, d),
                   place(ww / 2, v + 0.014, d), place(-ww / 2, v + 0.014, d)])
    for m in range(1, 5):
        u = -ww / 2 + ww * m / 5.0
        body.ngon([place(u - 0.014, wz, d), place(u + 0.014, wz, d),
                   place(u + 0.014, wz + wh, d), place(u - 0.014, wz + wh, d)])
    body.ngon([place(-ww / 2 - 0.10, wz - 0.10, 0.13), place(ww / 2 + 0.10, wz - 0.10, 0.13),
               place(ww / 2 + 0.10, wz - 0.03, 0.13), place(-ww / 2 - 0.10, wz - 0.03, 0.13)])


def add_finial_detail(gold, metal, z, z_apex, r_out, z_eave, lift):
    """v3 塔刹：覆莲座 / 仰月 / 宝盖 / 火焰宝珠 / 八道刹链"""
    zl = z_apex + 0.30
    for i in range(8):
        a = i * TAU / 8
        gold.tri((0.28 * math.cos(a), 0.28 * math.sin(a), zl + 0.32),
                 (0.80 * math.cos(a - 0.30), 0.80 * math.sin(a - 0.30), zl),
                 (0.80 * math.cos(a + 0.30), 0.80 * math.sin(a + 0.30), zl))

    def crescent(R=0.52, r=0.40, off=0.22, n=14):
        pts = []
        for k in range(n + 1):
            t = -math.pi * 0.60 + 1.20 * math.pi * k / n
            pts.append((R * math.cos(t), R * math.sin(t) + 0.08))
        for k in range(n + 1):
            t = math.pi * 0.60 - 1.20 * math.pi * k / n
            pts.append((r * math.cos(t), r * math.sin(t) + off))
        return pts

    for rot in (0.0, math.pi * 0.5):
        extrude_axis(gold, 0.0, 0.0, z + 0.08, rot, -0.028, 0.028, crescent())
    zc = z + 0.12
    gold.disc_ring(0.10, 0.62, zc, n=24)
    gold.circle_tube(lambda t: 0.62, zc, zc + 0.055, n=24)
    for i in range(8):
        a = PHASE + i * TAU / 8
        cx, cy = 0.58 * math.cos(a), 0.58 * math.sin(a)
        gold.box(cx, cy, zc - 0.09, 0.022, 0.022, 0.18, rot=a)
        gold.box(cx, cy, zc - 0.21, 0.060, 0.060, 0.075, rot=a)
    for i in range(8):
        a = i * TAU / 8
        gold.tri((0.16 * math.cos(a - 0.14), 0.16 * math.sin(a - 0.14), z + 0.28),
                 (0.16 * math.cos(a + 0.14), 0.16 * math.sin(a + 0.14), z + 0.28),
                 (0.27 * math.cos(a), 0.27 * math.sin(a), z + 0.68))
    for i in range(SIDES):
        a = PHASE + i * TAU / SIDES
        lf = lift_at(a, lift)
        p0 = (0.20 * math.cos(a), 0.20 * math.sin(a), z_apex + 1.05)
        p1 = ((r_out - 0.10) * math.cos(a), (r_out - 0.10) * math.sin(a), z_eave + lf + 0.12)
        ribbon(metal, p0, p1, 0.018)


main()
