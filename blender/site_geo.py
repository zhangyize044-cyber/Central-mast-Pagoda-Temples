# -*- coding: utf-8 -*-
"""
天宁寺院落 · 几何与构件库
================================================================
中式古建构件生成器：台基 / 柱网 / 墙体 / 板门 / 直棂窗 /
额枋斗拱 / 举折屋面（庑殿·歇山·硬山）/ 正脊垂脊鸱吻 /
院墙 / 石桥 / 石碑 / 石灯 / 香炉 / 古树 / 民居

坐标：建筑正面朝 +Y，正脊沿 X。
所有函数第一参数是「材质名 -> Part」字典 P。
"""

import bpy
import bmesh
import math
import random

TAU = math.tau


# ============================ 基础 ============================
def srgb(hexstr):
    h = hexstr.lstrip("#")
    out = []
    for i in (0, 2, 4):
        c = int(h[i:i + 2], 16) / 255.0
        out.append(c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4)
    return (*out, 1.0)


MATS = {
    "stone":   ("#6A6354", 0.95, 0.00),
    "brick":   ("#565044", 0.93, 0.00),
    "plaster": ("#8A4436", 0.88, 0.00),
    "wood":    ("#6B3A22", 0.86, 0.00),
    "tile":    ("#33393C", 0.87, 0.02),
    "paving":  ("#5B564B", 0.94, 0.00),
    "dark":    ("#160F0B", 0.92, 0.00),
    "gold":    ("#C9A24A", 0.32, 0.85),
    "leaf":    ("#3C4A26", 0.96, 0.00),
    "bark":    ("#3A2C1E", 0.98, 0.00),
    "caihua":  ("#585F58", 0.82, 0.00),
    "metal":   ("#5C5448", 0.46, 0.50),
}

TEXMAP = {
    "stone":   ("stone",   0.32),
    "brick":   ("brick",   0.50),
    "plaster": ("plaster", 0.30),
    "wood":    ("wood",    0.95),
    "tile":    ("tile",    0.50),
    "paving":  ("paving",  0.52),
    "caihua":  ("caihua",  2.40),
    "leaf":    ("leaf",    0.60),
    "bark":    ("bark",    1.10),
}


def box_uv(me, scale=0.5):
    """三平面盒式投影：按面法线主轴取投影平面，1 米 = scale 个 tile"""
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

    def prism(self, pts, z0, z1, cap_b=True, cap_t=True):
        n = len(pts)
        for i in range(n):
            j = (i + 1) % n
            self.quad((pts[i][0], pts[i][1], z0), (pts[j][0], pts[j][1], z0),
                      (pts[j][0], pts[j][1], z1), (pts[i][0], pts[i][1], z1))
        if cap_t:
            self.ngon([(p[0], p[1], z1) for p in pts])
        if cap_b:
            self.ngon([(p[0], p[1], z0) for p in reversed(pts)])

    def slab(self, pts, z, up=True):
        self.ngon([(p[0], p[1], z) for p in (pts if up else list(reversed(pts)))])

    def tube(self, r0, r1, z0, z1, n=16, cx=0.0, cy=0.0):
        for i in range(n):
            a0 = i * TAU / n
            a1 = (i + 1) * TAU / n
            self.quad((cx + r0 * math.cos(a0), cy + r0 * math.sin(a0), z0),
                      (cx + r0 * math.cos(a1), cy + r0 * math.sin(a1), z0),
                      (cx + r1 * math.cos(a1), cy + r1 * math.sin(a1), z1),
                      (cx + r1 * math.cos(a0), cy + r1 * math.sin(a0), z1))

    def disc(self, r, z, n=16, up=True, cx=0.0, cy=0.0):
        pts = [(cx + r * math.cos(i * TAU / n), cy + r * math.sin(i * TAU / n), z) for i in range(n)]
        self.ngon(pts if up else list(reversed(pts)))

    def sphere(self, cx, cy, cz, r, seg=10, ring=6, ry=1.0, rz=1.0):
        verts = []
        for j in range(ring + 1):
            phi = math.pi * j / ring
            for i in range(seg):
                th = TAU * i / seg
                verts.append((cx + r * math.sin(phi) * math.cos(th),
                              cy + r * math.sin(phi) * math.sin(th) * ry,
                              cz + r * math.cos(phi) * rz))
        for j in range(ring):
            for i in range(seg):
                i2 = (i + 1) % seg
                self.quad(verts[j * seg + i], verts[(j + 1) * seg + i],
                          verts[(j + 1) * seg + i2], verts[j * seg + i2])


# ---------------------------- 向量工具 ----------------------------
def vsub(a, b):
    return (a[0] - b[0], a[1] - b[1], a[2] - b[2])


def vadd(a, b):
    return (a[0] + b[0], a[1] + b[1], a[2] + b[2])


def vmul(a, k):
    return (a[0] * k, a[1] * k, a[2] * k)


def vlen(a):
    return math.sqrt(a[0] ** 2 + a[1] ** 2 + a[2] ** 2)


def vnorm(a):
    l = max(vlen(a), 1e-9)
    return (a[0] / l, a[1] / l, a[2] / l)


def vcross(a, b):
    return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0])


def frame(d):
    """由方向向量构造正交基 (u, v)"""
    d = vnorm(d)
    ref = (0.0, 0.0, 1.0) if abs(d[2]) < 0.92 else (1.0, 0.0, 0.0)
    u = vnorm(vcross(d, ref))
    v = vcross(d, u)
    return u, v


def bar(part, p0, p1, w, h, roll=0.0):
    """矩形截面梁：从 p0 到 p1，截面 w(横) x h(厚)"""
    u, v = frame(vsub(p1, p0))
    if roll:
        ca, sa = math.cos(roll), math.sin(roll)
        u, v = (vadd(vmul(u, ca), vmul(v, sa)), vadd(vmul(u, -sa), vmul(v, ca)))
    hw, hh = w * 0.5, h * 0.5
    ring = [vadd(vmul(u, -hw), vmul(v, -hh)), vadd(vmul(u, hw), vmul(v, -hh)),
            vadd(vmul(u, hw), vmul(v, hh)), vadd(vmul(u, -hw), vmul(v, hh))]
    a = [vadd(p0, r) for r in ring]
    b = [vadd(p1, r) for r in ring]
    for i in range(4):
        j = (i + 1) % 4
        part.quad(a[i], a[j], b[j], b[i])
    part.ngon(list(reversed(a)))
    part.ngon(b)


def rod(part, p0, p1, r0, r1, n=6):
    """圆柱形枝干"""
    u, v = frame(vsub(p1, p0))
    ra, rb = [], []
    for i in range(n):
        a = i * TAU / n
        o = vadd(vmul(u, math.cos(a)), vmul(v, math.sin(a)))
        ra.append(vadd(p0, vmul(o, r0)))
        rb.append(vadd(p1, vmul(o, r1)))
    for i in range(n):
        j = (i + 1) % n
        part.quad(ra[i], ra[j], rb[j], rb[i])
    part.ngon(list(reversed(ra)))
    part.ngon(rb)


# ============================ 屋面 ============================
def roof(part, cx, cy, w, d, eave, z0, rise, kind="xieshan", seg=7, sh=None, bf=None,
         gb=None):
    """
    生成中式举折屋面。
      w,d     面阔 / 进深（柱中距）
      eave    出檐
      z0      檐口（椽头）标高
      rise    举高（檐口到正脊）
      kind    xieshan / wudian / yingshan
      sh,bf   歇山山花 / 博风板所用部件（缺省并入瓦作，传 plaster+wood 可分离材质）
      gb      硬山山墙墙顶标高；给值才补山墙三角，缺省不补（披檐不适用）
    举折曲线 z = z0 + rise * t^1.55，下缓上陡；歇山收山取进深的 0.34。
    """
    A = w * 0.5 + eave
    B = d * 0.5 + eave
    ztop = z0 + rise

    if kind == "wudian":
        shou = B * 0.70
        xs = max(0.05, A - shou)
        Bt = max(0.05, B - shou)
    else:
        shou = 0.34 * d
        xs = max(0.55, A - shou)
        Bt = max(0.35, B - shou)

    def zf(y):
        t = max(0.0, 1.0 - abs(y) / B)
        return z0 + rise * (t ** 1.55)

    zs = zf(Bt)

    def half_at(y):
        if y <= Bt:
            return xs
        return xs + (A - xs) * (y - Bt) / max(B - Bt, 1e-6)

    def P(x, y, z):
        return (cx + x, cy + y, z)

    if kind == "yingshan":
        for sgn in (1, -1):
            prev = None
            for i in range(seg + 1):
                y = B - B * i / seg
                z = zf(y)
                row = [P(-A, sgn * y, z), P(A, sgn * y, z)]
                if prev:
                    if sgn > 0:
                        part.quad(prev[1], prev[0], row[0], row[1])
                    else:
                        part.quad(prev[0], prev[1], row[1], row[0])
                prev = row
        # ---- 硬山山墙：墙顶至屋面的曲边三角扇 ----
        if gb is not None:
            gp = sh if sh is not None else part
            for sgn in (1, -1):
                xx = cx + sgn * w * 0.5
                p0 = (xx, cy - d * 0.5, gb)
                for i in range(seg):
                    ya = -d * 0.5 + d * i / seg
                    yb = -d * 0.5 + d * (i + 1) / seg
                    pa = (xx, cy + ya, max(gb, zf(ya)))
                    pb = (xx, cy + yb, max(gb, zf(yb)))
                    if sgn > 0:
                        gp.tri(p0, pb, pa)
                    else:
                        gp.tri(p0, pa, pb)
        return {"A": A, "B": B, "xs": A, "Bt": B, "zs": z0, "ztop": ztop}

    # ---- 前后坡：y 由 ±B 收到 ±Bt，x 半宽同步收到 xs ----
    for sgn in (1, -1):
        prev = None
        for i in range(seg + 1):
            y = B - (B - Bt) * i / seg
            a = half_at(y)
            z = zf(y)
            row = [P(-a, sgn * y, z), P(a, sgn * y, z)]
            if prev:
                if sgn > 0:
                    part.quad(prev[1], prev[0], row[0], row[1])
                else:
                    part.quad(prev[0], prev[1], row[1], row[0])
            prev = row

    # ---- 两山撒头 ----
    if A - xs > 0.06:
        for sgn in (1, -1):
            prev = None
            for i in range(seg + 1):
                x = A - (A - xs) * i / seg
                b = B - (B - Bt) * i / seg
                t = (A - x) / max(A - xs, 1e-6)
                z = z0 + (zs - z0) * (t ** 1.55)
                row = [P(sgn * x, -b, z), P(sgn * x, b, z)]
                if prev:
                    if sgn > 0:
                        part.quad(prev[0], prev[1], row[1], row[0])
                    else:
                        part.quad(prev[1], prev[0], row[0], row[1])
                prev = row

    # ---- 悬山段（歇山正脊两侧的两坡）----
    if kind == "xieshan":
        for sgn in (1, -1):
            prev = None
            for i in range(seg + 1):
                y = Bt - Bt * i / seg
                z = zf(y)
                row = [P(-xs, sgn * y, z), P(xs, sgn * y, z)]
                if prev:
                    if sgn > 0:
                        part.quad(prev[1], prev[0], row[0], row[1])
                    else:
                        part.quad(prev[0], prev[1], row[1], row[0])
                prev = row

        # ---- 山花：曲边三角，收山处到正脊 ----
        shp = sh if sh is not None else part
        bfp = bf if bf is not None else part
        for sgn in (1, -1):
            x = cx + sgn * xs
            if sgn > 0:
                shp.tri((x, cy - Bt, zs), (x, cy + Bt, zs), (x, cy, ztop))
            else:
                shp.tri((x, cy + Bt, zs), (x, cy - Bt, zs), (x, cy, ztop))
            # 博风板（沿山花两腰）
            for sy in (1, -1):
                bar(bfp, (x, cy + sy * Bt, zs), (x, cy, ztop), 0.20, 0.34)
            bar(bfp, (x, cy - Bt, zs), (x, cy + Bt, zs), 0.20, 0.26)

    return {"A": A, "B": B, "xs": xs, "Bt": Bt, "zs": zs, "ztop": ztop}


def roof_ridges(tile, gold, cx, cy, w, d, eave, z0, rise, kind="xieshan", curve=0.16):
    """正脊 / 垂脊 / 戗脊 / 鸱吻"""
    A = w * 0.5 + eave
    B = d * 0.5 + eave
    ztop = z0 + rise
    if kind == "wudian":
        shou = B * 0.70
        xs, Bt = max(0.05, A - shou), max(0.05, B - shou)
    elif kind == "yingshan":
        xs, Bt = A, B
    else:
        shou = 0.34 * d
        xs, Bt = max(0.55, A - shou), max(0.35, B - shou)
    zs = z0 + rise * max(0.0, 1.0 - Bt / B) ** 1.55

    # 正脊
    rw, rh = 0.34, 0.44
    tile.box(cx, cy, ztop + rh * 0.5, 2 * xs, rw, rh)
    tile.box(cx, cy, ztop + rh + 0.055, 2 * xs * 0.995, rw * 0.80, 0.10)

    # 鸱吻（正脊两端，吞脊）
    for sgn in (1, -1):
        bx = cx + sgn * (xs - 0.06)
        tile.box(bx, cy, ztop + rh + 0.30, 0.36, 0.30, 0.62, rot=0.0)
        tile.box(bx - sgn * 0.14, cy, ztop + rh + 0.66, 0.20, 0.24, 0.30)
        tile.box(bx - sgn * 0.10, cy, ztop + rh + 0.84, 0.36, 0.20, 0.14)
        gold.box(bx - sgn * 0.20, cy, ztop + rh + 0.50, 0.10, 0.10, 0.10)

    # 垂脊 / 戗脊
    if kind == "yingshan":
        return
    for sx in (1, -1):
        for sy in (1, -1):
            p0 = (cx + sx * A, cy + sy * B, z0 + 0.02)
            p1 = (cx + sx * xs, cy + sy * Bt, zs)
            bar(tile, p0, p1, 0.30, 0.30)
            # 翼角起翘
            bar(tile, p0, (cx + sx * (A - 0.55), cy + sy * (B - 0.55), z0 + 0.02), 0.26, 0.56)


def roof_flutes(part, cx, cy, w, d, eave, z0, rise, kind="xieshan",
                spacing=0.42, seg=5, hw=0.088, hh=0.062):
    """筒瓦垄：沿屋面坡度方向逐垄起脊，前后坡 + 两山撒头
       每垄为三棱带（左坡面 + 右坡面），末端自然收到垂脊/戗脊。"""
    A = w * 0.5 + eave
    B = d * 0.5 + eave
    if kind == "wudian":
        shou = B * 0.70
        xs, Bt = max(0.05, A - shou), max(0.05, B - shou)
    elif kind == "yingshan":
        xs, Bt = A, B
    else:
        shou = 0.34 * d
        xs, Bt = max(0.55, A - shou), max(0.35, B - shou)
    zs = z0 + rise * max(0.0, 1.0 - Bt / B) ** 1.55

    def zf(y):
        return z0 + rise * (max(0.0, 1.0 - abs(y) / B) ** 1.55)

    def rib(pts, axis):
        prev = None
        for (x, y, z) in pts:
            if axis == 0:
                l, a, r0 = (x - hw, y, z), (x, y, z + hh), (x + hw, y, z)
            else:
                l, a, r0 = (x, y - hw, z), (x, y, z + hh), (x, y + hw, z)
            if prev:
                pl, pa, pr = prev
                part.quad(pl, l, a, pa)
                part.quad(pa, a, r0, pr)
            prev = (l, a, r0)

    # ---- 前后坡：沿 y 走向 ----
    n = max(2, int(2 * A / spacing))
    for i in range(n + 1):
        x = -A + 2 * A * i / n
        ax = abs(x)
        if ax <= xs + 1e-6:
            y_end = 0.0
        else:
            y_end = Bt + (B - Bt) * (ax - xs) / max(A - xs, 1e-6)
        for sy in (1, -1):
            pts = []
            for k in range(seg + 1):
                y = B - (B - y_end) * k / seg
                pts.append((cx + x, cy + sy * y, zf(y)))
            rib(pts, 0)

    # ---- 两山撒头：沿 x 走向 ----
    if A - xs > 0.06:
        ny = max(2, int(2 * Bt / spacing))
        for j in range(ny + 1):
            y = -Bt + 2 * Bt * j / ny
            t_end = min(1.0, (B - abs(y)) / max(B - Bt, 1e-6))
            x_end = A - (A - xs) * t_end
            if x_end >= A - 1e-3:
                continue
            for sx in (1, -1):
                pts = []
                for k in range(seg + 1):
                    x = A - (A - x_end) * k / seg
                    t = (A - x) / max(A - xs, 1e-6)
                    pts.append((cx + sx * x, cy + y, z0 + (zs - z0) * (t ** 1.55)))
                rib(pts, 1)


def ridge_beasts(tile, gold, cx, cy, w, d, eave, z0, rise, kind="xieshan", n=5):
    """垂脊走兽：自檐角向正脊方向逐只蹲踞，末端为垂兽"""
    A = w * 0.5 + eave
    B = d * 0.5 + eave
    if kind == "wudian":
        shou = B * 0.70
        xs, Bt = max(0.05, A - shou), max(0.05, B - shou)
    elif kind == "yingshan":
        return
    else:
        shou = 0.34 * d
        xs, Bt = max(0.55, A - shou), max(0.35, B - shou)
    for sx in (1, -1):
        for sy in (1, -1):
            for i in range(n):
                t = 0.14 + i * 0.135
                px = cx + sx * (A + (xs - A) * t)
                py = cy + sy * (B + (Bt - B) * t)
                pz = z0 + (rise * max(0.0, 1.0 - abs(py - cy) / B) ** 1.55) + 0.30
                tile.box(px, py, pz, 0.17, 0.15, 0.22)
                tile.box(px, py, pz + 0.15, 0.11, 0.10, 0.10)
                if i == 0:
                    gold.box(px, py, pz + 0.03, 0.06, 0.11, 0.05)


_GLYPHS = [
    # 字形一：三横一竖
    [(0, 0.17, 0.46, 0.050), (0, 0.04, 0.38, 0.044), (0, -0.17, 0.50, 0.050),
     (0, 0.00, 0.050, 0.36)],
    # 字形二：宝盖 + 中竖 + 底横
    [(0, 0.19, 0.42, 0.048), (-0.13, 0.11, 0.050, 0.10), (0.13, 0.11, 0.050, 0.10),
     (0, -0.02, 0.048, 0.30), (0, -0.19, 0.46, 0.048)],
    # 字形三：口框 + 中横
    [(-0.16, 0.14, 0.050, 0.20), (0.16, 0.14, 0.050, 0.20), (0, 0.22, 0.36, 0.048),
     (0, 0.06, 0.30, 0.044), (0, -0.10, 0.36, 0.048)],
    # 字形四：两点 + 横 + 竖钩
    [(-0.13, 0.15, 0.055, 0.055), (0.13, 0.15, 0.055, 0.055), (0, 0.04, 0.44, 0.046),
     (0, -0.06, 0.046, 0.26), (-0.02, -0.19, 0.36, 0.046)],
]


def plaque(stone, dark, gold, x, y, z, w=2.4, h=0.78, rot=0.0, chars=3, face=1):
    """匾额：石框 + 黑漆匾心 + 金字（按字形笔画块拼合）"""
    ny = face * 1.0
    stone.box(x, y, z, w, 0.12, h, rot=rot)
    dark.box(x, y + ny * 0.062, z, w - 0.18, 0.05, h - 0.18, rot=rot)
    gold.box(x, y + ny * 0.070, z + h * 0.5 - 0.052, w - 0.22, 0.030, 0.048, rot=rot)
    gold.box(x, y + ny * 0.070, z - h * 0.5 + 0.052, w - 0.22, 0.030, 0.048, rot=rot)

    cw = (w - 0.34) / chars
    for c in range(chars):
        cxp = x - (w - 0.34) * 0.5 + cw * (c + 0.5)
        for (dx, dz, sw, sh) in _GLYPHS[c % len(_GLYPHS)]:
            gold.box(cxp + dx, y + ny * 0.074, z + dz * (h / 0.78),
                     sw * (h / 0.78), 0.030, sh * (h / 0.78), rot=rot)


def stone_railing(stone, x0, y0, x1, y1, z, h=0.92, step=1.45):
    """汉白玉式石栏杆：地栿 + 栏板 + 望柱 + 柱头"""
    L = math.hypot(x1 - x0, y1 - y0)
    if L < 0.4:
        return
    ang = math.atan2(y1 - y0, x1 - x0)
    cx, cy = (x0 + x1) * 0.5, (y0 + y1) * 0.5
    stone.box(cx, cy, z + 0.09, L, 0.26, 0.18, rot=ang)
    stone.box(cx, cy, z + h * 0.46, L, 0.14, h * 0.60, rot=ang)
    stone.box(cx, cy, z + h * 0.78, L, 0.20, 0.11, rot=ang)
    n = max(1, int(L / step))
    for i in range(n + 1):
        t = i / n
        px, py = x0 + (x1 - x0) * t, y0 + (y1 - y0) * t
        stone.box(px, py, z + h * 0.5, 0.20, 0.20, h, rot=ang)
        stone.box(px, py, z + h + 0.07, 0.25, 0.25, 0.14, rot=ang)
        stone.sphere(px, py, z + h + 0.19, 0.105, seg=6, ring=4)


def water_vat(stone, x, y, r=0.72, h=0.94):
    """消防用大水缸：石座 + 收口缸身 + 缸沿"""
    stone.box(x, y, 0.05, r * 2.30, r * 2.30, 0.10)
    stone.tube(r * 0.92, r * 1.0, 0.10, h * 0.52, n=14, cx=x, cy=y)
    stone.tube(r * 1.0, r * 0.84, h * 0.52, h, n=14, cx=x, cy=y)
    stone.tube(r * 0.90, r * 0.86, h - 0.05, h + 0.03, n=14, cx=x, cy=y)
    stone.disc(r * 0.83, h + 0.005, n=14, cx=x, cy=y)


def planter(brick, stone, bark, leaf, x, y, w=3.4, d=2.4, seed=1):
    """砖砌花坛：坛壁 + 压顶石 + 坛内灌木"""
    brick.box(x, y, 0.30, w, d, 0.60)
    stone.box(x, y, 0.64, w + 0.16, d + 0.16, 0.10)
    for sx in (-1, 1):
        for sy in (-1, 1):
            stone.box(x + sx * (w * 0.5 - 0.10), y + sy * (d * 0.5 - 0.10), 0.72,
                      0.34, 0.34, 0.16)
    bush(bark, leaf, x, y, min(w, d) * 0.42, seed)


def roof_tiles(tile, wood, cx, cy, w, d, eave, z0, rise, kind="xieshan", n=30):
    """檐口勾头滴水 + 檐下椽头飞子"""
    A = w * 0.5 + eave
    B = d * 0.5 + eave
    for sy in (1, -1):
        for i in range(n):
            x = -A + 2 * A * (i + 0.5) / n
            tile.box(cx + x, cy + sy * (B + 0.02), z0 - 0.10, 0.17, 0.10, 0.20)
        m = n
        for i in range(m):
            x = -A + 2 * A * (i + 0.5) / m
            wood.box(cx + x, cy + sy * (B - 0.13), z0 - 0.26, 0.135, 0.40, 0.15)
            wood.box(cx + x, cy + sy * (B - 0.02), z0 - 0.17, 0.105, 0.20, 0.11)
    ny = max(4, int(n * B / A))
    for sx in (1, -1):
        for i in range(ny):
            y = -B + 2 * B * (i + 0.5) / ny
            tile.box(cx + sx * (A + 0.02), cy + y, z0 - 0.10, 0.10, 0.17, 0.20)
        m = ny
        for i in range(m):
            y = -B + 2 * B * (i + 0.5) / m
            wood.box(cx + sx * (A - 0.13), cy + y, z0 - 0.26, 0.40, 0.135, 0.15)
            wood.box(cx + sx * (A - 0.02), cy + y, z0 - 0.17, 0.20, 0.105, 0.11)


# ============================ 台基 ============================
def platform(stone, brick, cx, cy, w, d, h, steps_front=0, steps_w=3.0, stone_edge=True):
    """台基：青砖台身 + 阶条石压边 + 正面踏跺"""
    brick.box(cx, cy, h * 0.5, w, d, h)
    if stone_edge:
        # 陡板石（台身外皮，青砖）
        brick.box(cx, cy, h * 0.5, w + 0.10, d + 0.10, h * 0.96)
        # 阶条石
        stone.box(cx, cy, h + 0.065, w + 0.24, d + 0.24, 0.13)
    if steps_front:
        n = steps_front
        for k in range(n):
            zc = h * (k + 1) / n
            ww = steps_w * (1.0 - 0.10 * k / n)
            stone.box(cx, cy + d * 0.5 + 0.14 + (n - 1 - k) * 0.34,
                      zc * 0.5, ww, 0.36, zc)
        # 垂带石
        for sx in (-1, 1):
            stone.box(cx + sx * (steps_w * 0.5 + 0.20), cy + d * 0.5 + 0.14 + (n - 1) * 0.18,
                      h * 0.5 + 0.06, 0.34, n * 0.34 + 0.40, h + 0.12)


# ============================ 柱 · 墙 · 门窗 ============================
def column(wood, x, y, z0, h, r=0.24, base=True):
    wood.tube(r, r * 0.94, z0, z0 + h, n=10, cx=x, cy=y)
    if base:
        wood.tube(r * 1.6, r * 1.45, z0, z0 + 0.16, n=10, cx=x, cy=y)


def wall_panel(part, x0, x1, y, z0, z1, thick=0.40):
    """沿 X 方向的直墙段（中心线在 y）"""
    part.box((x0 + x1) * 0.5, y, (z0 + z1) * 0.5, abs(x1 - x0), thick, z1 - z0)


def wall_panel_y(part, y0, y1, x, z0, z1, thick=0.40):
    part.box(x, (y0 + y1) * 0.5, (z0 + z1) * 0.5, thick, abs(y1 - y0), z1 - z0)


def lintel(part, x0, x1, y, z, h=0.32, thick=0.46):
    part.box((x0 + x1) * 0.5, y, z, abs(x1 - x0), thick, h)


def door_leaf(dark, wood, gold, x, y, z0, w, h, gold_nails=4):
    """板门：门扇 + 门钉 + 铺首"""
    dark.box(x, y, z0 + h * 0.5, w, 0.09, h)
    for sx in (-1, 1):
        wood.box(x + sx * w * 0.25, y + 0.055, z0 + h * 0.5, w * 0.47, 0.05, h * 0.99)
    if gold_nails:
        for r in range(gold_nails):
            for c in range(3):
                for sx in (-1, 1):
                    gold.box(x + sx * (w * 0.13 + c * w * 0.11),
                             y + 0.09, z0 + h * (0.30 + r * 0.16),
                             0.075, 0.045, 0.075)
    for sx in (-1, 1):
        gold.box(x + sx * w * 0.055, y + 0.10, z0 + h * 0.52, 0.11, 0.05, 0.11)


def lattice_window(dark, wood, x0, x1, y, z0, h, bars=7):
    """直棂窗：暗底 + 竖棂"""
    w = abs(x1 - x0)
    cx = (x0 + x1) * 0.5
    dark.box(cx, y, z0 + h * 0.5, w, 0.08, h)
    for i in range(bars):
        bx = x0 + w * (i + 0.5) / bars
        wood.box(bx, y + 0.055, z0 + h * 0.5, 0.052, 0.06, h * 0.94)
    wood.box(cx, y + 0.055, z0 + h * 0.5, w, 0.06, 0.055)
    for yy in (z0, z0 + h):
        wood.box(cx, y + 0.055, yy, w + 0.10, 0.09, 0.09)


def dougong_band(caihua, wood, plaster, cx, cy, w, d, z0, bays, layer=0.34, n_per_bay=3):
    """额枋 + 斗拱 + 挑檐枋，环绕一周"""
    # 额枋（正面 / 背面）
    for sy in (1, -1):
        caihua.box(cx, cy + sy * d * 0.5, z0 + 0.17, w + 0.06, 0.30, 0.34)
        plaster.box(cx, cy + sy * d * 0.5, z0 + 0.50, w + 0.04, 0.26, 0.32)
    # 山面额枋
    for sx in (1, -1):
        caihua.box(cx + sx * w * 0.5, cy, z0 + 0.17, 0.30, d + 0.06, 0.34)
        plaster.box(cx + sx * w * 0.5, cy, z0 + 0.50, 0.26, d + 0.04, 0.32)

    # 斗拱（正面 / 背面）
    for sy in (1, -1):
        for b in range(bays):
            for k in range(n_per_bay):
                x = cx + w * ((b + (k + 0.5) / n_per_bay) / bays - 0.5)
                yy = cy + sy * (d * 0.5 + 0.18)
                caihua.box(x, yy, z0 + 0.62, 0.28, 0.26, 0.19)        # 栌斗（青绿）
                caihua.box(x, yy, z0 + 0.75, 0.48, 0.26, 0.12)        # 华拱
                caihua.box(x, yy, z0 + 0.86, 0.76, 0.20, 0.12)        # 令拱（青绿）
                caihua.box(x, yy + sy * 0.09, z0 + 0.93, 0.15, 0.32, 0.11)  # 耍头
    # 斗拱（山面）
    for sx in (1, -1):
        nb = max(2, int(round(bays * d / max(w, 1e-6))))
        for b in range(nb):
            for k in range(n_per_bay):
                y = cy + d * ((b + (k + 0.5) / n_per_bay) / nb - 0.5)
                xx = cx + sx * (w * 0.5 + 0.18)
                caihua.box(xx, y, z0 + 0.62, 0.26, 0.28, 0.19)
                caihua.box(xx, y, z0 + 0.75, 0.26, 0.48, 0.12)
                caihua.box(xx, y, z0 + 0.86, 0.20, 0.76, 0.12)
                caihua.box(xx + sx * 0.09, y, z0 + 0.93, 0.32, 0.15, 0.11)

    # 挑檐枋
    for sy in (1, -1):
        wood.box(cx, cy + sy * (d * 0.5 + 0.32), z0 + 0.99, w + 0.8, 0.22, 0.14)
    for sx in (1, -1):
        wood.box(cx + sx * (w * 0.5 + 0.32), cy, z0 + 0.99, 0.22, d + 0.8, 0.14)


# ============================ 院墙 ============================
def wall_run(plaster, tile, x0, y0, x1, y1, h=3.3, thick=0.85, seg_len=2.4,
             plinth=None, pilaster=0.0):
    """墙段（含墙帽瓦顶、可选勒脚与壁柱）"""
    L = math.hypot(x1 - x0, y1 - y0)
    if L < 0.06:
        return
    ang = math.atan2(y1 - y0, x1 - x0)
    cx, cy = (x0 + x1) * 0.5, (y0 + y1) * 0.5
    plaster.box(cx, cy, h * 0.5, L, thick, h, rot=ang)
    # 下碱：青砖勒脚（外皮略出，形成一道水平线脚）
    if plinth is not None:
        plinth.box(cx, cy, 0.34, L, thick + 0.12, 0.68, rot=ang)
        plinth.box(cx, cy, 0.72, L, thick + 0.20, 0.10, rot=ang)
    # 壁柱：等距凸出的砖垛，打破长墙的空白
    if pilaster > 0.5:
        nb = max(1, int(round(L / pilaster)))
        for i in range(nb + 1):
            t = i / nb
            px, py = x0 + (x1 - x0) * t, y0 + (y1 - y0) * t
            plaster.box(px, py, h * 0.5, 0.58, thick + 0.16, h, rot=ang)
    # 墙帽：两坡小瓦顶
    n = max(1, int(L / 0.55))
    for i in range(n):
        t = (i + 0.5) / n - 0.5
        px = cx + math.cos(ang) * L * t
        py = cy + math.sin(ang) * L * t
        tile.box(px, py, h + 0.10, L / n + 0.02, thick + 0.34, 0.16, rot=ang)
    tile.box(cx, cy, h + 0.26, L, 0.24, 0.22, rot=ang)
    for i in range(n):
        t = (i + 0.5) / n - 0.5
        px = cx + math.cos(ang) * L * t
        py = cy + math.sin(ang) * L * t
        tile.box(px, py, h + 0.40, L / n + 0.02, 0.15, 0.14, rot=ang)


def plain_wall(plaster, tile, x0, y0, x1, y1, h=2.05, thick=0.38):
    """民居院墙：墙身 + 墙帽，三段盒子，控制面数"""
    L = math.hypot(x1 - x0, y1 - y0)
    if L < 0.05:
        return
    ang = math.atan2(y1 - y0, x1 - x0)
    cx, cy = (x0 + x1) * 0.5, (y0 + y1) * 0.5
    plaster.box(cx, cy, h * 0.5, L, thick, h, rot=ang)
    tile.box(cx, cy, h + 0.10, L, thick + 0.26, 0.20, rot=ang)
    tile.box(cx, cy, h + 0.25, L, 0.16, 0.13, rot=ang)


# ============================ 石作小品 ============================
def stele(stone, dark, gold, x, y, h=2.7, rot=0.0):
    """石碑：方形须弥座 + 碑身 + 碑首"""
    stone.box(x, y, 0.18, 1.10, 0.72, 0.36, rot=rot)
    stone.box(x, y, 0.40, 0.96, 0.60, 0.10, rot=rot)
    stone.box(x, y, 0.44 + h * 0.5, 0.72, 0.26, h, rot=rot)
    stone.box(x, y, 0.44 + h, 0.84, 0.32, 0.20, rot=rot)       # 碑首
    stone.box(x, y, 0.44 + h + 0.20, 0.62, 0.30, 0.14, rot=rot)
    dark.box(x, y + 0.135, 0.44 + h * 0.5, 0.56, 0.02, h * 0.80, rot=rot)
    gold.box(x, y + 0.145, 0.44 + h * 0.86, 0.30, 0.02, 0.16, rot=rot)


def stone_lamp(stone, gold, x, y, h=2.1):
    stone.box(x, y, 0.10, 1.00, 1.00, 0.20)
    stone.box(x, y, 0.40, 0.72, 0.72, 0.42)
    stone.tube(0.20, 0.17, 0.60, h * 0.62, n=8, cx=x, cy=y)
    stone.box(x, y, h * 0.62 + 0.10, 0.60, 0.60, 0.20)
    stone.box(x, y, h * 0.62 + 0.44, 0.52, 0.52, 0.48)
    gold.box(x, y, h * 0.62 + 0.44, 0.30, 0.54, 0.30)
    stone.box(x, y, h * 0.62 + 0.76, 0.86, 0.86, 0.16)
    stone.box(x, y, h * 0.62 + 0.90, 0.56, 0.56, 0.20)
    stone.sphere(x, y, h * 0.62 + 1.06, 0.16, seg=8, ring=5)


def incense_burner(stone, gold, x, y, s=1.0):
    """大香炉：三足 + 炉身 + 双耳 + 攒尖盖"""
    stone.box(x, y, 0.10 * s, 2.2 * s, 2.2 * s, 0.20 * s)
    stone.box(x, y, 0.26 * s, 1.7 * s, 1.7 * s, 0.16 * s)
    for k in range(3):
        a = math.pi * 0.5 + k * TAU / 3
        stone.box(x + math.cos(a) * 0.52 * s, y + math.sin(a) * 0.52 * s,
                  0.52 * s, 0.22 * s, 0.22 * s, 0.52 * s)
    stone.tube(0.44 * s, 0.80 * s, 0.74 * s, 1.20 * s, n=14, cx=x, cy=y)
    stone.tube(0.80 * s, 0.72 * s, 1.20 * s, 1.34 * s, n=14, cx=x, cy=y)
    stone.disc(0.72 * s, 1.34 * s, n=14, cx=x, cy=y)
    for sx in (-1, 1):
        stone.box(x + sx * 0.80 * s, y, 1.30 * s, 0.14 * s, 0.34 * s, 0.44 * s)
    stone.tube(0.62 * s, 0.12 * s, 1.36 * s, 1.86 * s, n=14, cx=x, cy=y)
    gold.sphere(x, y, 1.94 * s, 0.14 * s, seg=8, ring=5)


def bridge(stone, x, y, span=7.4, width=4.6, camber=0.76, rise=1.22):
    """单孔石拱桥：拱腹 + 券脸石 + 拱肩墙 + 桥面 + 栏板望柱 + 抱鼓石

    拱洞必须透空（前版把拱洞砌死，形同实心路堤，属硬伤）。
    桥面起拱 0.36→1.12，拱腹自 -0.80 起拱，券顶在桥面之下留 0.2 m 结构厚度。
    """
    n = 18
    hw = width * 0.5
    y0 = y - span * 0.5
    z_d0, t_dk = 0.36, 0.24          # 桥面端部标高 / 桥面板厚
    z_sp, ring = -0.80, 0.26         # 拱腹起拱标高 / 券脸石厚

    def zd(t):
        return z_d0 + camber * math.sin(math.pi * t) ** 0.85

    def zs(t):
        return z_sp + rise * math.sin(math.pi * t) ** 0.62

    def yy(t):
        return y0 + span * t

    def face(sx, xx, t0, t1, lo0, lo1, hi0, hi1):
        """x 恒定竖面；sx>0 时法线朝 +x，sx<0 朝 -x"""
        if sx > 0:
            pts = [(xx, yy(t0), lo0), (xx, yy(t1), lo1),
                   (xx, yy(t1), hi1), (xx, yy(t0), hi0)]
        else:
            pts = [(xx, yy(t0), hi0), (xx, yy(t1), hi1),
                   (xx, yy(t1), lo1), (xx, yy(t0), lo0)]
        stone.quad(*pts)

    # 桥面（顶面）
    prev = None
    for i in range(n + 1):
        t = i / n
        row = [(x - hw, yy(t), zd(t)), (x + hw, yy(t), zd(t))]
        if prev:
            stone.quad(prev[0], prev[1], row[1], row[0])
        prev = row
    # 桥面两侧立面
    for sx in (-1, 1):
        for i in range(n):
            t0, t1 = i / n, (i + 1) / n
            face(sx, x + sx * hw, t0, t1,
                 zd(t0) - t_dk, zd(t1) - t_dk, zd(t0), zd(t1))
    # 拱腹（下弧面，法线朝下）
    for i in range(n):
        t0, t1 = i / n, (i + 1) / n
        stone.quad((x - hw, yy(t0), zs(t0)), (x - hw, yy(t1), zs(t1)),
                   (x + hw, yy(t1), zs(t1)), (x + hw, yy(t0), zs(t0)))
    # 券脸石：两侧向外微凸的拱圈带
    for sx in (-1, 1):
        for i in range(n):
            t0, t1 = i / n, (i + 1) / n
            face(sx, x + sx * (hw + 0.02), t0, t1,
                 zs(t0), zs(t1), zs(t0) + ring, zs(t1) + ring)
    # 拱肩墙：券顶到桥面底
    for sx in (-1, 1):
        for i in range(n):
            t0, t1 = i / n, (i + 1) / n
            a0, a1 = zs(t0) + ring, zs(t1) + ring
            b0, b1 = zd(t0) - t_dk, zd(t1) - t_dk
            if b0 - a0 < 0.015 and b1 - a1 < 0.015:
                continue
            face(sx, x + sx * hw, t0, t1, a0, a1, max(a0, b0), max(a1, b1))
    # 桥台：两端坐入渠岸
    for ty in (y0, y0 + span):
        stone.box(x, ty + (-0.42 if ty == y0 else 0.42), -0.40,
                  width + 1.20, 0.84, 1.58)
    # 两端踏步（各三级）
    for ed in (0, 1):
        base_y = y0 - 0.42 if ed == 0 else y0 + span + 0.42
        sgn = -1 if ed == 0 else 1
        for k in range(3):
            stone.box(x, base_y + sgn * (0.18 + k * 0.36), 0.30 - k * 0.14,
                      width, 0.36, 0.10)
    # 栏板（实心板带）+ 压顶
    for sx in (-1, 1):
        xi, xo = x + sx * (hw - 0.18), x + sx * (hw - 0.02)
        for i in range(n):
            t0, t1 = i / n, (i + 1) / n
            face(sx, xo, t0, t1, zd(t0), zd(t1), zd(t0) + 0.32, zd(t1) + 0.32)
            face(-sx, xi, t0, t1, zd(t0), zd(t1), zd(t0) + 0.32, zd(t1) + 0.32)
            stone.quad((xo, yy(t0), zd(t0) + 0.32), (xo, yy(t1), zd(t1) + 0.32),
                       (xi, yy(t1), zd(t1) + 0.32), (xi, yy(t0), zd(t0) + 0.32))
            stone.quad((xi, yy(t0), zd(t0) + 0.44), (xi, yy(t1), zd(t1) + 0.44),
                       (xo, yy(t1), zd(t1) + 0.44), (xo, yy(t0), zd(t0) + 0.44))
            stone.quad((xo, yy(t0), zd(t0) + 0.32), (xo, yy(t1), zd(t1) + 0.32),
                       (xo, yy(t1), zd(t1) + 0.44), (xo, yy(t0), zd(t0) + 0.44))
            stone.quad((xi, yy(t0), zd(t0) + 0.44), (xi, yy(t1), zd(t1) + 0.44),
                       (xi, yy(t1), zd(t1) + 0.32), (xi, yy(t0), zd(t0) + 0.32))
    # 望柱（四等分）+ 抱鼓石
    for sx in (-1, 1):
        px = x + sx * (hw - 0.10)
        for k in range(5):
            t = k / 4.0
            stone.box(px, yy(t), zd(t) + 0.62, 0.21, 0.21, 1.24)
            stone.box(px, yy(t), zd(t) + 1.30, 0.27, 0.27, 0.13)
            stone.sphere(px, yy(t), zd(t) + 1.42, 0.09, seg=8, ring=5)
        for ed in (0, 1):
            t = 0.0 if ed == 0 else 1.0
            by = yy(t) + (-0.30 if ed == 0 else 0.30)
            stone.box(px, by, zd(t) + 0.30, 0.30, 0.68, 0.60)
            stone.sphere(px, by, zd(t) + 0.62, 0.20, seg=10, ring=6, ry=1.0, rz=0.86)


def paifang(stone, plaster, tile, wood, gold, caihua, x, y, w=13.0, h=8.4):
    """四柱三门三楼牌坊：明间高、次间低，各覆小庑殿顶

    明间自下而上：下额枋—匾额—上额枋—平板枋—斗拱—屋顶。
    """
    cols = [-w * 0.5, -w * 0.165, w * 0.165, w * 0.5]
    for i, cxx in enumerate(cols):
        side = 0.34 if i in (0, 3) else 0.40
        stone.box(x + cxx, y, 0.30, side * 2.1, side * 2.1, 0.60)     # 柱础
        stone.box(x + cxx, y, 0.66, side * 1.5, side * 1.5, 0.18)
        plaster.box(x + cxx, y, h * 0.5 + 0.72, side, side, h - 0.72)  # 柱身
        stone.box(x + cxx, y, h * 0.5 + 0.72, side * 1.18, side * 1.18, 0.22)

    mid_w = w * 0.33
    # 明间：下额枋 / 匾额 / 上额枋
    caihua.box(x, y, h - 2.06, mid_w + 0.9, 0.46, 0.46)
    caihua.box(x, y, h - 0.62, mid_w + 0.9, 0.44, 0.46)
    stone.box(x, y + 0.20, h - 1.34, mid_w * 0.62, 0.10, 0.96)
    stone.box(x, y + 0.27, h - 1.34, mid_w * 0.58, 0.06, 0.84)
    gold.box(x, y + 0.30, h - 1.34, mid_w * 0.50, 0.04, 0.70)
    caihua.box(x, y, h - 0.14, mid_w + 1.2, 0.42, 0.30)               # 平板枋
    # 明间斗拱
    for k in range(5):
        cxx = -mid_w * 0.44 + k * (mid_w * 0.22)
        wood.box(x + cxx, y, h + 0.14, 0.30, 0.62, 0.24)
        wood.box(x + cxx, y, h + 0.28, 0.52, 0.70, 0.16)
    # 次间额枋
    for sx in (-1, 1):
        cxs = x + sx * (mid_w * 0.5 + (w * 0.335) * 0.5)
        caihua.box(cxs, y, h * 0.50, w * 0.335, 0.42, 0.40)
        caihua.box(cxs, y, h * 0.63, w * 0.335, 0.42, 0.36)
        for k in range(3):
            cxx = cxs - w * 0.10 + k * (w * 0.10)
            wood.box(cxx, y, h * 0.63 + 0.26, 0.28, 0.56, 0.22)
            wood.box(cxx, y, h * 0.63 + 0.38, 0.46, 0.64, 0.14)

    # 三间小屋顶
    roof(tile, x, y, mid_w + 1.5, 2.6, 0.85, h + 0.36, 1.32, kind="wudian", seg=5)
    roof_ridges(tile, gold, x, y, mid_w + 1.5, 2.6, 0.85, h + 0.36, 1.32, kind="wudian")
    for sx in (-1, 1):
        rx = x + sx * (mid_w * 0.5 + w * 0.1675)
        roof(tile, rx, y, w * 0.335 + 1.2, 2.3, 0.72, h * 0.63 + 0.50, 1.00,
             kind="wudian", seg=5)
        roof_ridges(tile, gold, rx, y, w * 0.335 + 1.2, 2.3, 0.72, h * 0.63 + 0.50, 1.00,
                    kind="wudian")

    # 夹杆石 + 抱鼓
    for cxx in cols:
        stone.box(x + cxx, y, 0.62, 0.90, 0.90, 1.24)
        stone.box(x + cxx, y, 1.28, 0.76, 0.76, 0.14)
        for sy in (-1, 1):
            stone.sphere(x + cxx, y + sy * 0.48, 0.42, 0.26, seg=10, ring=6, rz=0.64)


def house(plaster, tile, dark, wood, cx, cy, w, d, h, seed=0):
    """周边民居正房：硬山小房，檐下带门窗"""
    plaster.box(cx, cy, h * 0.5, w, d, h)
    dark.box(cx, cy + d * 0.5 + 0.01, h * 0.34, 1.05, 0.10, h * 0.62)
    for sx in (-1, 1):
        dark.box(cx + sx * w * 0.26, cy + d * 0.5 + 0.01, h * 0.56, 0.95, 0.10, 0.85)
    wood.box(cx, cy + d * 0.5 + 0.06, h * 0.84, w * 0.9, 0.12, 0.16)
    rise = (d * 0.5 + 0.52) * 0.44
    roof(tile, cx, cy, w, d, 0.52, h, rise, kind="yingshan", seg=4,
         sh=plaster, gb=h)
    # 檐口勾头：仅补一排瓦当，给远景屋脊下一条暗边
    for sy in (1, -1):
        for i in range(9):
            x = -w * 0.5 - 0.4 + (w + 0.8) * (i + 0.5) / 9
            tile.box(cx + x, cy + sy * (d * 0.5 + 0.52), h - 0.09, 0.16, 0.09, 0.17)
    tile.box(cx, cy, h + rise + 0.09, w + 1.0, 0.24, 0.18)


def village_yard(P, cx, cy, w, d, h, seed):
    """一座民居院落：三面院墙 + 门楼 + 正房

    按 seed 出四种变体，避免院院雷同（正定老城街坊，一进四合式）：
      0 单进正房 · 1 正房带东西厢房 · 2 二层小楼 · 3 临街铺面（无院墙）
    """
    rng = random.Random(seed * 7919 + 17)
    hw, hd = w * 0.5, d * 0.5
    wh, th = rng.uniform(1.78, 2.10), 0.38
    var = seed % 4

    if var != 3:
        plain_wall(P["brick"], P["tile"], cx - hw, cy - hd, cx + hw, cy - hd, h=wh, thick=th)
        plain_wall(P["brick"], P["tile"], cx - hw, cy - hd, cx - hw, cy + hd, h=wh, thick=th)
        plain_wall(P["brick"], P["tile"], cx + hw, cy - hd, cx + hw, cy + hd, h=wh, thick=th)
        gw = 1.7
        plain_wall(P["brick"], P["tile"], cx - hw, cy + hd, cx - gw * 0.5, cy + hd, h=wh, thick=th)
        plain_wall(P["brick"], P["tile"], cx + gw * 0.5, cy + hd, cx + hw, cy + hd, h=wh, thick=th)
        # 门楼
        P["brick"].box(cx, cy + hd, 1.55, 2.5, 0.55, 3.15)
        P["dark"].box(cx, cy + hd + 0.28, 0.95, 1.15, 0.10, 1.9)
        roof(P["tile"], cx, cy + hd, 2.3, 0.9, 0.36, 3.18, 0.72, kind="yingshan", seg=3,
         sh=P["brick"], gb=3.15)

    if var == 2:
        # 二层小楼：上下两段，腰檐挑出
        bw = min(w * 0.72, 8.6)
        bd = min(d * 0.40, 5.8)
        by = cy - hd * 0.34
        h1 = h + 0.35
        hs = h * 0.80
        P["brick"].box(cx, by, h1 + hs * 0.5, bw, bd, hs)
        P["dark"].box(cx, by + bd * 0.5 + 0.01, h1 + hs * 0.46, 1.15, 0.10, hs * 0.52)
        for sx in (-1, 1):
            P["dark"].box(cx + sx * bw * 0.28, by + bd * 0.5 + 0.01,
                          h1 + hs * 0.52, 0.80, 0.10, hs * 0.40)
        roof(P["tile"], cx, by, bw + 2.4, bd + 2.2, 0.55, h1, 0.52, kind="yingshan", seg=4)
        roof(P["tile"], cx, by, bw, bd, 0.54, h1 + hs, (bd * 0.5 + 0.54) * 0.42,
             kind="yingshan", seg=4)
        P["tile"].box(cx, by, h1 + hs + (bd * 0.5 + 0.54) * 0.42 + 0.09, bw + 1.0, 0.24, 0.18)
    else:
        house(P["brick"], P["tile"], P["dark"], P["wood"],
              cx, cy - hd * 0.36, min(w * 0.76, 9.2), min(d * 0.44, 6.2), h, seed=seed)
        if var == 1:
            for sx in (-1, 1):
                house(P["brick"], P["tile"], P["dark"], P["wood"],
                      cx + sx * (hw - 2.4), cy + hd * 0.10, 3.6, min(d * 0.34, 4.4),
                      h * 0.80, seed=seed + sx)
    if var == 3:
        # 临街铺面：门脸开敞 + 木雨棚
        P["wood"].box(cx, cy + hd - 1.3, h + 0.42, w * 0.80, 2.4, 0.14)
        for sx in (-1, 1):
            P["wood"].box(cx + sx * w * 0.36, cy + hd - 1.3, h + 0.10, 0.14, 2.2, 0.70)


def tree(bark, leaf, cx, cy, h=14.0, seed=1, spread=1.0, style="huai"):
    """古树：主干 + 三级分枝 + 叶团"""
    rng = random.Random(seed)
    r0 = h * (0.045 if style == "huai" else 0.036)
    trunk_h = h * (0.36 if style == "huai" else 0.44)

    # 主干（带弯曲）
    pts = [(cx, cy, 0.0)]
    for i in range(1, 5):
        t = i / 4.0
        pts.append((cx + rng.uniform(-0.20, 0.20) * h * 0.03 * t * spread,
                    cy + rng.uniform(-0.20, 0.20) * h * 0.03 * t * spread,
                    trunk_h * t))
    for i in range(4):
        rod(bark, pts[i], pts[i + 1], r0 * (1 - i * 0.16), r0 * (0.84 - i * 0.16), n=8)
    # 根部起鼓
    for k in range(5):
        a = k * TAU / 5 + 0.3
        bark.box(cx + math.cos(a) * r0 * 1.25, cy + math.sin(a) * r0 * 1.25, r0 * 0.9,
                 r0 * 0.9, r0 * 0.9, r0 * 1.8)

    top = pts[-1]
    nbr = 3

    def grow(p, d, length, rad, depth):
        p1 = vadd(p, vmul(d, length))
        rod(bark, p, p1, rad, rad * 0.70, n=5)
        if depth <= 0 or length < h * 0.060:
            for _ in range(3):
                c = vadd(p1, (rng.uniform(-1, 1) * length * 0.30,
                              rng.uniform(-1, 1) * length * 0.30,
                              rng.uniform(-0.45, 0.85) * length * 0.30))
                rr = length * rng.uniform(0.34, 0.58) * spread
                leaf.sphere(c[0], c[1], c[2], rr, seg=6, ring=3, ry=1.10, rz=0.86)
            return
        for i in range(nbr):
            a = (i / float(nbr)) * TAU + rng.uniform(-0.6, 0.6)
            tilt = rng.uniform(0.55, 1.15)
            nd = vnorm(vadd(d, (math.cos(a) * tilt, math.sin(a) * tilt, rng.uniform(0.12, 0.55))))
            grow(p1, nd, length * rng.uniform(0.58, 0.76), rad * 0.62, depth - 1)

    for i in range(nbr):
        a = i * TAU / nbr + rng.uniform(-0.35, 0.35)
        tilt = rng.uniform(0.42, 0.95) * spread
        d = vnorm((math.cos(a) * tilt, math.sin(a) * tilt, rng.uniform(0.85, 1.45)))
        grow(top, d, h * rng.uniform(0.21, 0.28), r0 * 0.70, 2)


def bush(bark, leaf, cx, cy, r=1.6, seed=3):
    rng = random.Random(seed)
    for _ in range(5):
        leaf.sphere(cx + rng.uniform(-r, r) * 0.6,
                    cy + rng.uniform(-r, r) * 0.6,
                    r * rng.uniform(0.34, 0.56),
                    r * rng.uniform(0.38, 0.62), seg=6, ring=4, rz=0.70)


def tree_pit(stone, dark, x, y, s=1.9):
    """树池：石砌边框 + 池内培土"""
    h = s * 0.5
    for (dx, dy, sx, sy) in ((0, h, s + 0.22, 0.18), (0, -h, s + 0.22, 0.18),
                             (h, 0, 0.18, s + 0.22), (-h, 0, 0.18, s + 0.22)):
        stone.box(x + dx, y + dy, 0.075, sx, sy, 0.15)
    dark.box(x, y, 0.02, s - 0.06, s - 0.06, 0.05)


def banner_pole(wood, gold, stone, x, y, h=13.0, cloth=None):
    """幡杆：石座 + 木杆 + 顶部宝珠 + 横木 + 幡旗"""
    stone.box(x, y, 0.22, 1.20, 1.20, 0.44)
    stone.box(x, y, 0.50, 0.90, 0.90, 0.16)
    wood.tube(0.16, 0.11, 0.58, h, n=10, cx=x, cy=y)
    gold.sphere(x, y, h + 0.14, 0.17, seg=8, ring=5)
    wood.box(x, y, h - 0.70, 1.60, 0.12, 0.12)
    wood.box(x, y, h - 1.55, 1.86, 0.10, 0.10)
    if cloth is None:
        return
    # 幡旗：自横木垂下，分段错位做出垂坠波浪
    top, hp, n = h - 1.62, 2.75, 5
    for i in range(n):
        za = top - hp * i / n
        zb = top - hp * (i + 1) / n
        d0 = 0.11 * math.sin(i * 1.35)
        d1 = 0.11 * math.sin((i + 1) * 1.35)
        cloth.quad((x - 0.48, y + d0, za), (x + 0.48, y + d0, za),
                   (x + 0.48, y + d1, zb), (x - 0.48, y + d1, zb))
        # 幡面横带
        if i % 2 == 0:
            gold.box(x, y + d0 + 0.012, za - 0.06, 0.92, 0.018, 0.07)
    # 幡首横杆与坠饰
    wood.box(x, y, top + 0.04, 1.06, 0.10, 0.10)
    for sx in (-1, 1):
        gold.box(x + sx * 0.46, y, top - hp - 0.10, 0.09, 0.09, 0.24)
