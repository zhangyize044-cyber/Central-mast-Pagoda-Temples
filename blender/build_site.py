# -*- coding: utf-8 -*-
"""
正定天宁寺 · 院落环境（原生态配套）
================================================================
依据现存格局与清光绪《正定县志》记载，沿中轴自南向北布置：
  牌坊 → 石桥 → 山门 → 一进院（东西厢房）→ 重门（元代石狮）
  → 前殿遗址（柱础阵列、残墙、散石）→ 凌霄塔 → 后殿 → 后院

另配：院墙、明清古碑八通、宋槐、清榆、石灯、幡杆、香炉、
      寺前广场、石渠，以及院墙外正定古城低矮民居群。

用法：
  blender --background --factory-startup --python build_site.py
"""

import bpy
import bmesh
import math
import os
import sys
import random

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

import site_geo as G
from site_geo import Part, MATS, TEXMAP, srgb, box_uv  # noqa


# ============================ 布局常量 ============================
Y_PAIFANG = 84.0
Y_CANAL = 70.0
Y_GATE = 60.0          # 山门
Y_WING = 48.4          # 东西厢房
Y_CHONGMEN = 37.0      # 重门
Y_FRONT = 22.5         # 前殿遗址
Y_REAR = -30.0         # 后殿
Y_NWALL = -44.0        # 北院墙
X_WALL = 26.5          # 东西院墙


# ============================ 合并与输出 ============================
def merge_xf(dst, src, rot=0.0, tx=0.0, ty=0.0):
    ca, sa = math.cos(rot), math.sin(rot)
    base = len(dst.v)
    for v in src.v:
        x, y, z = v[0], v[1], v[2]
        dst.v.append((x * ca - y * sa + tx, x * sa + y * ca + ty, z))
    for f in src.f:
        dst.f.append(tuple(i + base for i in f))


def merge_all(dst, src, rot=0.0, tx=0.0, ty=0.0):
    for k, s in src.items():
        if s.f:
            merge_xf(dst[k], s, rot, tx, ty)


def new_parts():
    return {k: Part() for k in MATS}


def clear_scene():
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(use_global=False)
    for blk in (bpy.data.meshes, bpy.data.materials, bpy.data.objects):
        for item in list(blk):
            if item.users == 0:
                blk.remove(item)


def to_object(name, part, mat_key, tex_dir):
    if not part.f:
        return None
    me = bpy.data.meshes.new(name)
    me.from_pydata(part.v, [], part.f)
    me.validate(verbose=False)
    me.update()

    bm = bmesh.new()
    bm.from_mesh(me)
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-4)
    # 屋面与铺地都是开放面片，recalc 会把它们整体翻面，故不做法线重算，
    # 生成时已保证顶点绕序；渲染端材质一律双面。
    bm.to_mesh(me)
    bm.free()

    hexcol, rough, metal_v = MATS[mat_key]
    mat = bpy.data.materials.new(name + "_mat")
    mat.use_nodes = True
    mat.use_backface_culling = False
    bsdf = mat.node_tree.nodes.get("Principled BSDF")
    bsdf.inputs["Base Color"].default_value = srgb(hexcol)
    bsdf.inputs["Roughness"].default_value = rough
    bsdf.inputs["Metallic"].default_value = metal_v

    tex_name, uv_scale = TEXMAP.get(mat_key, (None, 0.0))
    if tex_name:
        p = os.path.join(tex_dir, tex_name + ".png")
        if os.path.exists(p):
            box_uv(me, uv_scale)
            img = bpy.data.images.load(p, check_existing=True)
            img.colorspace_settings.name = "sRGB"
            node = mat.node_tree.nodes.new("ShaderNodeTexImage")
            node.image = img
            node.extension = "REPEAT"
            node.interpolation = "Smart"
            node.location = (-420, 220)
            mat.node_tree.links.new(node.outputs["Color"], bsdf.inputs["Base Color"])
            bsdf.inputs["Base Color"].default_value = (1.0, 1.0, 1.0, 1.0)

    me.materials.append(mat)
    ob = bpy.data.objects.new(name, me)
    bpy.context.collection.objects.link(ob)
    ob.data.shade_flat()
    return ob


# ============================ 殿宇 ============================
def hall(w, d, hcol, bays=5, kind="xieshan", eave=1.9, plat_h=0.9,
         steps=3, door_bays=None, back_door=False, plat_extra=1.7,
         rail=False, dg=True, plinth=True, plaque_w=0.0, flutes=True):
    """通用殿宇（局部坐标，中心在原点，正面朝 +Y）"""
    P = new_parts()
    pw = w + plat_extra * 2
    pd = d + plat_extra * 2

    G.platform(P["stone"], P["brick"], 0, 0, pw, pd, plat_h,
               steps_front=steps, steps_w=min(w * 0.44, 5.0))

    z0 = plat_h
    z1 = z0 + hcol

    # ---- 柱网 ----
    cols_x = [w * (i / float(bays) - 0.5) for i in range(bays + 1)]
    for x in cols_x:
        G.column(P["wood"], x, d * 0.5, z0, hcol)
        G.column(P["wood"], x, -d * 0.5, z0, hcol)
    G.column(P["wood"], w * 0.5, 0, z0, hcol)
    G.column(P["wood"], -w * 0.5, 0, z0, hcol)

    # ---- 室内暗面 ----
    P["dark"].box(0, 0, z0 + hcol * 0.5, w - 0.75, d - 0.75, hcol)

    if door_bays is None:
        door_bays = [bays // 2]

    # ---- 正面：门 / 槛墙直棂窗 ----
    for b in range(bays):
        x0, x1 = cols_x[b], cols_x[b + 1]
        bw = x1 - x0
        cxb = (x0 + x1) * 0.5
        if b in door_bays:
            dw = min(bw * 0.66, 2.4)
            dh = hcol * 0.80
            G.door_leaf(P["dark"], P["wood"], P["gold"], cxb, d * 0.5 - 0.16, z0, dw, dh)
            P["plaster"].box(cxb - dw * 0.5 - (bw - dw) * 0.25, d * 0.5 - 0.14,
                             z0 + dh * 0.5, max(0.2, bw - dw) * 0.5, 0.42, dh)
            P["plaster"].box(cxb + dw * 0.5 + (bw - dw) * 0.25, d * 0.5 - 0.14,
                             z0 + dh * 0.5, max(0.2, bw - dw) * 0.5, 0.42, dh)
            P["plaster"].box(cxb, d * 0.5 - 0.14, z0 + dh + (hcol - dh) * 0.5,
                             bw - 0.1, 0.42, max(0.05, hcol - dh))
        else:
            kq = 0.95                                   # 槛墙（青砖）
            P["brick"].box(cxb, d * 0.5 - 0.14, z0 + kq * 0.5, bw - 0.08, 0.46, kq)
            P["stone"].box(cxb, d * 0.5 - 0.14, z0 + kq + 0.03, bw - 0.02, 0.52, 0.07)
            wh = hcol * 0.38
            wz = z0 + kq + wh * 0.5 + 0.14
            wwin = min(bw * 0.52, 2.1)
            G.lattice_window(P["dark"], P["wood"], cxb - wwin * 0.5, cxb + wwin * 0.5,
                             d * 0.5 - 0.16, wz - wh * 0.5, wh, bars=max(5, int(wwin / 0.28)))
            P["plaster"].box(cxb, d * 0.5 - 0.14, z0 + kq + wh + (hcol - kq - wh) * 0.5,
                             bw - 0.08, 0.42, max(0.05, hcol - kq - wh))

    # ---- 背面山墙 ----
    if back_door:
        dw = min(w * 0.16, 1.9)
        G.door_leaf(P["dark"], P["wood"], P["gold"], 0, -d * 0.5 + 0.16, z0, dw, hcol * 0.72)
        for sx in (-1, 1):
            P["plaster"].box(sx * (w * 0.25 + dw * 0.25), -d * 0.5 + 0.14,
                             z0 + hcol * 0.5, w * 0.5 - dw * 0.5 - 0.05, 0.42, hcol)
    else:
        P["plaster"].box(0, -d * 0.5 + 0.14, z0 + hcol * 0.5, w - 0.1, 0.42, hcol)

    for sx in (-1, 1):
        P["plaster"].box(sx * (w * 0.5 - 0.14), 0, z0 + hcol * 0.5, 0.42, d - 0.1, hcol)

    # ---- 墙身下碱：青砖墙裙 + 压面石，打破大面积红墙的空白 ----
    zb = z0 + 1.35
    for sx in (-1, 1):
        P["brick"].box(sx * (w * 0.5 - 0.13), 0, (z0 + zb) * 0.5, 0.50, d - 0.12, 1.35)
        P["stone"].box(sx * (w * 0.5 - 0.13), 0, zb + 0.045, 0.56, d - 0.06, 0.09)
    if back_door:
        dgb = min(w * 0.16, 1.9)
        for sx in (-1, 1):
            P["brick"].box(sx * (w * 0.25 + dgb * 0.25), -(d * 0.5 - 0.13),
                           (z0 + zb) * 0.5, w * 0.5 - dgb * 0.5, 0.50, 1.35)
            P["stone"].box(sx * (w * 0.25 + dgb * 0.25), -(d * 0.5 - 0.13),
                           zb + 0.045, w * 0.5 - dgb * 0.5 + 0.04, 0.56, 0.09)
    else:
        P["brick"].box(0, -(d * 0.5 - 0.13), (z0 + zb) * 0.5, w - 0.12, 0.50, 1.35)
        P["stone"].box(0, -(d * 0.5 - 0.13), zb + 0.045, w - 0.06, 0.56, 0.09)

    # ---- 斗拱带 + 屋顶 ----
    if dg:
        G.dougong_band(P["caihua"], P["wood"], P["plaster"], 0, 0, w, d, z1,
                       bays, n_per_bay=3 if bays >= 3 else 2)
        z_eave = z1 + 1.05
    else:
        G.lintel(P["caihua"], -w * 0.5, w * 0.5, d * 0.5, z1 + 0.24, 0.48, 0.44)
        G.lintel(P["caihua"], -w * 0.5, w * 0.5, -d * 0.5, z1 + 0.24, 0.48, 0.44)
        z_eave = z1 + 0.52

    rise = (d * 0.5 + eave) * (0.48 if kind == "xieshan" else 0.44)
    G.roof(P["tile"], 0, 0, w, d, eave, z_eave, rise, kind=kind, seg=8,
           sh=P["plaster"], bf=P["wood"], gb=z1)
    if flutes:
        G.roof_flutes(P["tile"], 0, 0, w, d, eave, z_eave, rise, kind=kind,
                      spacing=0.44, seg=4)
    G.roof_tiles(P["tile"], P["wood"], 0, 0, w, d, eave, z_eave, rise, kind=kind,
                 n=max(16, int(w * 2.4)))
    G.roof_ridges(P["tile"], P["gold"], 0, 0, w, d, eave, z_eave, rise, kind=kind)
    G.ridge_beasts(P["tile"], P["gold"], 0, 0, w, d, eave, z_eave, rise, kind=kind,
                   n=5 if w > 14 else 4)

    # ---- 匾额（悬于额枋下、门楣上）----
    if plaque_w > 0:
        G.plaque(P["stone"], P["dark"], P["gold"], 0, d * 0.5 + 0.20,
                 z1 - 0.56, w=plaque_w, h=0.80, chars=3)

    # ---- 台基石栏杆 ----
    if rail:
        zw = plat_h + 0.06
        hx = pw * 0.5 - 0.34
        hy = pd * 0.5 - 0.34
        gap = (min(w * 0.44, 5.0) * 0.5 + 0.55)
        if steps:
            G.stone_railing(P["stone"], -hx, hy, -gap, hy, zw)
            G.stone_railing(P["stone"], gap, hy, hx, hy, zw)
        else:
            G.stone_railing(P["stone"], -hx, hy, hx, hy, zw)
        for sx in (-1, 1):
            G.stone_railing(P["stone"], sx * hx, -hy, sx * hx, hy, zw)
        G.stone_railing(P["stone"], -hx, -hy, hx, -hy, zw)

    return P


def hall_ruins():
    """前殿遗址：台基 + 柱础阵列 + 残柱 + 残墙基 + 散落构件"""
    P = new_parts()
    W, D, H = 24.0, 11.2, 1.10
    G.platform(P["stone"], P["brick"], 0, 0, W, D, H)
    # 阶条石（外圈压边，残破感靠高低错落）
    rng = random.Random(7)
    n = 26
    for i in range(n):
        x = -W * 0.5 + W * (i + 0.5) / n
        for sy in (1, -1):
            if rng.random() < 0.14:
                continue
            P["stone"].box(x, sy * D * 0.5, H + 0.05,
                           W / n * 0.98, 0.62, 0.14 + rng.uniform(-0.02, 0.02))

    # 柱础 6 x 4（面阔五间、进深三间）
    xs = [W * 0.5 * 0.78 * (i / 5.0 * 2 - 1) for i in range(6)]
    ys = [D * 0.5 * 0.70 * (j / 3.0 * 2 - 1) for j in range(4)]
    for i, x in enumerate(xs):
        for j, y in enumerate(ys):
            P["stone"].tube(0.58, 0.46, H, H + 0.20, n=12, cx=x, cy=y)
            P["stone"].disc(0.46, H + 0.20, n=12, cx=x, cy=y)
            # 残柱（约三分之一还立着）
            if (i * 4 + j) % 3 == 0:
                hh = 0.32 + ((i * 7 + j * 3) % 5) * 0.22
                P["wood"].tube(0.28, 0.26, H + 0.20, H + 0.20 + hh, n=10, cx=x, cy=y)

    # 残墙：断续砖墙，高低不齐，做出坍圮感
    def ruin_wall(x0, y0, x1, y1, hmax, nseg, thick=0.48):
        L = math.hypot(x1 - x0, y1 - y0)
        if L < 0.2:
            return
        ang = math.atan2(y1 - y0, x1 - x0)
        for k in range(nseg):
            t0, t1 = k / nseg, (k + 1) / nseg
            if rng.random() < 0.22:
                continue
            mx = x0 + (x1 - x0) * (t0 + t1) * 0.5
            my = y0 + (y1 - y0) * (t0 + t1) * 0.5
            hh = hmax * rng.uniform(0.30, 1.0)
            P["brick"].box(mx, my, H + hh * 0.5, L / nseg * 0.98, thick, hh, rot=ang)

    ruin_wall(-W * 0.5 * 0.86, -D * 0.5 * 0.86, -W * 0.10, -D * 0.5 * 0.86, 2.35, 7)
    ruin_wall(W * 0.22, -D * 0.5 * 0.86, W * 0.5 * 0.86, -D * 0.5 * 0.86, 1.65, 5)
    ruin_wall(-W * 0.5 * 0.86, D * 0.5 * 0.86, -W * 0.26, D * 0.5 * 0.86, 1.45, 5)
    ruin_wall(W * 0.14, D * 0.5 * 0.86, W * 0.5 * 0.86, D * 0.5 * 0.86, 2.05, 6)
    ruin_wall(-W * 0.5 * 0.86, -D * 0.30, -W * 0.5 * 0.86, D * 0.24, 1.85, 4)
    ruin_wall(W * 0.5 * 0.86, -D * 0.34, W * 0.5 * 0.86, D * 0.16, 1.55, 4)

    # 残墙顶上的碎瓦
    for _ in range(26):
        px = rng.uniform(-W * 0.46, W * 0.46)
        py = rng.choice((-1, 1)) * D * 0.5 * 0.86 + rng.uniform(-0.3, 0.3)
        P["tile"].box(px, py, H + rng.uniform(0.9, 2.3), rng.uniform(0.18, 0.34),
                      rng.uniform(0.14, 0.24), 0.06, rot=rng.uniform(0, 3.14))

    # 散落构件：柱顶石、残碑、瓦砾堆
    for k in range(9):
        a = rng.uniform(0, math.tau)
        r = rng.uniform(2.0, 9.0)
        cx = math.cos(a) * r
        cy = math.sin(a) * r * 0.42
        if rng.random() < 0.5:
            P["stone"].box(cx, cy, H + 0.09, rng.uniform(0.4, 0.9),
                           rng.uniform(0.3, 0.6), 0.18, rot=rng.uniform(0, 3.14))
        else:
            for m in range(3):
                P["tile"].box(cx + rng.uniform(-0.5, 0.5), cy + rng.uniform(-0.5, 0.5),
                              H + 0.06 + m * 0.02, rng.uniform(0.3, 0.6),
                              rng.uniform(0.2, 0.4), 0.08)

    # 遗址前的石阶（残）
    for k in range(3):
        P["stone"].box(0, D * 0.5 + 0.30 + (2 - k) * 0.36, H * (k + 1) / 3 * 0.5,
                       min(W * 0.36, 8.0), 0.36, H * (k + 1) / 3)
    return P


def stone_lion(stone, gold, x, y, rot=0.0, s=1.0):
    """元代石狮：蹲踞、前肢支撑、后肢弯曲、身背直挺、颌下三绺须、鬃毛螺旋"""
    ca, sa = math.cos(rot), math.sin(rot)

    def P(dx, dy, dz, sx, sy, sz, r=0.0):
        wx = x + dx * ca - dy * sa
        wy = y + dx * sa + dy * ca
        stone.box(wx, wy, dz, sx * s, sy * s, sz * s, rot=rot + r)

    P(0, 0, 0.24, 1.30, 1.10, 0.48)              # 须弥座
    P(0, 0, 0.52, 1.16, 0.98, 0.12)
    P(0, -0.10, 1.06, 0.62, 0.86, 0.92)          # 身背直挺
    P(0, 0.16, 1.30, 0.58, 0.40, 0.52)           # 胸
    for dx in (-0.19, 0.19):                      # 前肢直立支撑
        P(dx, 0.34, 0.94, 0.17, 0.26, 0.78)
        P(dx, 0.42, 0.60, 0.20, 0.22, 0.14)      # 爪
    for dx in (-0.22, 0.22):                      # 后肢弯曲
        P(dx, -0.28, 0.80, 0.20, 0.52, 0.50)
        P(dx, -0.06, 0.66, 0.20, 0.30, 0.18)
    P(0, 0.30, 1.72, 0.52, 0.48, 0.46)           # 头
    P(0, 0.48, 1.68, 0.34, 0.20, 0.30)           # 吻部
    for dx in (-0.15, 0.0, 0.15):                 # 颌下三绺须
        P(dx, 0.46, 1.52, 0.09, 0.10, 0.26)
    for k in range(7):                            # 鬃毛螺旋卷
        a = -0.9 + k * 0.30
        P(math.sin(a) * 0.26, -0.06 - math.cos(a) * 0.16, 1.62 + math.cos(a) * 0.16,
          0.15, 0.15, 0.15, r=a)
    for dx in (-0.14, 0.14):                      # 耳
        P(dx, 0.24, 1.94, 0.12, 0.12, 0.14)
    P(0, -0.56, 1.20, 0.16, 0.26, 0.72)           # 尾
    gold.box(x, y + 0.30 * s, 1.60 * s, 0.07, 0.05, 0.07)


# ============================ 地面 ============================
def ground_slab(part, x0, x1, y0, y1, z=-0.03, nx=1, ny=1):
    for i in range(nx):
        for j in range(ny):
            ax = x0 + (x1 - x0) * i / nx
            bx = x0 + (x1 - x0) * (i + 1) / nx
            ay = y0 + (y1 - y0) * j / ny
            by = y0 + (y1 - y0) * (j + 1) / ny
            part.quad((ax, ay, z), (bx, ay, z), (bx, by, z), (ax, by, z))


def axis_path(P, y0, y1, half=2.55, top=0.02):
    """中轴御路：条石逐块铺砌、留细缝，两侧压牙子石"""
    L = y1 - y0
    if L <= 0:
        return
    n = max(1, int(round(L / 0.95)))
    st = L / n
    for i in range(n):
        y = y0 + st * (i + 0.5)
        P["stone"].box(0, y, top - 0.055, half * 2.0, st - 0.05, 0.09)
    for sx in (-1, 1):
        P["brick"].box(sx * (half + 0.17), (y0 + y1) * 0.5, top - 0.02,
                       0.34, L, 0.13)


def build_ground(P):
    # 城外大地：夯土路面，避免建筑浮在虚空里；扩至 ±400 使鸟瞰不见板边
    ground_slab(P["paving"], -400, 400, -400, 400, -0.16, 4, 4)
    # 院内铺地：分两段避开石渠
    ground_slab(P["paving"], -X_WALL, X_WALL, Y_NWALL, Y_CANAL - 2.0, -0.04, 13, 25)
    ground_slab(P["paving"], -X_WALL, X_WALL, Y_CANAL + 2.0, Y_GATE + 1.5, -0.04, 13, 4)
    # 寺前广场（石板）
    ground_slab(P["paving"], -31, 31, Y_GATE + 1.5, Y_PAIFANG + 8, -0.06, 15, 10)
    # 中轴御路：条石逐块铺砌
    axis_path(P, Y_NWALL + 0.4, Y_CANAL - 2.0)
    axis_path(P, Y_CANAL + 2.0, Y_PAIFANG + 6.0, half=2.75)
    # 通向东西厢房的支路
    for sx in (-1, 1):
        ground_slab(P["stone"], sx * 2.55, sx * 15.2, 45.8, 49.4, 0.012, 7, 1)
    # 塔前月台外圈散水
    ground_slab(P["stone"], -13.2, 13.2, -13.2, 13.2, -0.02, 6, 6)


def build_canal(P):
    """寺前石渠（东西向）与渠岸：渠底 -1.24，水面 -1.05"""
    half = 2.0
    for sy in (1, -1):
        y = Y_CANAL + sy * half
        P["stone"].box(0, y, 0.18, 62, 0.55, 0.36)                # 压面石
        P["stone"].box(0, y + sy * 0.30, -0.60, 62, 0.22, 1.25)   # 渠壁
    # 渠底 + 水
    P["stone"].box(0, Y_CANAL, -1.24, 62, 4.2, 0.22)
    P["dark"].box(0, Y_CANAL, -1.05, 62, 3.9, 0.06)


# ============================ 院墙 ============================
def build_walls(P):
    w = X_WALL
    wp, wt, wb = P["plaster"], P["tile"], P["brick"]
    # 东西院墙（自北墙至山门）
    for sx in (-1, 1):
        G.wall_run(wp, wt, sx * w, Y_NWALL, sx * w, Y_GATE,
                   plinth=wb, pilaster=5.2)
    # 北院墙
    G.wall_run(wp, wt, -w, Y_NWALL, w, Y_NWALL, plinth=wb, pilaster=5.2)
    # 南院墙（山门两侧）
    G.wall_run(wp, wt, -w, Y_GATE, -6.9, Y_GATE, plinth=wb, pilaster=5.2)
    G.wall_run(wp, wt, 6.9, Y_GATE, w, Y_GATE, plinth=wb, pilaster=5.2)
    # 山门两侧掖门小门楼
    for sx in (-1, 1):
        P["plaster"].box(sx * 7.7, Y_GATE, 1.75, 1.5, 1.5, 3.6)
        G.roof(P["tile"], sx * 7.7, Y_GATE, 1.7, 1.7, 0.42, 3.62, 0.85, kind="wudian", seg=3)
    # 四角压顶
    for sx in (-1, 1):
        P["tile"].box(sx * w, Y_NWALL, 3.44, 1.6, 1.6, 0.22)
        P["tile"].box(sx * w, Y_GATE, 3.44, 1.6, 1.6, 0.22)


# ============================ 植物与小件 ============================
TREES = [
    (14.6, 65.5, 12.0, 71, "配榆", 0.98),
    (-15.2, 66.2, 11.0, 73, "配槐", 0.94),
    (20.6, -7.4, 15.0, 41, "宋槐", 1.06),
    (-15.6, -13.0, 16.5, 43, "清榆", 1.10),
    (-13.6, 48.0, 11.0, 47, "配槐", 0.92),
    (13.6, 52.5, 10.0, 53, "配槐", 0.86),
    (-16.5, -38.0, 12.0, 59, "配榆", 0.95),
    (22.8, 10.5, 13.0, 61, "配槐", 0.98),
    (-18.6, 3.0, 13.5, 67, "配槐", 1.00),
    (21.6, 24.0, 11.5, 69, "配榆", 0.94),
]


def build_plants(P):
    for (x, y, h, seed, _n, sp) in TREES:
        G.tree(P["bark"], P["leaf"], x, y, h=h, seed=seed, spread=sp,
               style="huai" if "槐" in _n else "yu")
        if abs(x) < X_WALL - 1.0:
            G.tree_pit(P["stone"], P["dark"], x, y, s=2.0 if h > 13 else 1.7)
    for (x, y, r, seed) in [(11.0, 18.6, 1.5, 71), (-11.4, 18.0, 1.3, 73),
                            (17.0, 33.0, 1.4, 77), (-17.2, 33.4, 1.5, 79),
                            (-19.0, -26.0, 1.4, 83), (20.0, 12.0, 1.2, 89)]:
        G.bush(P["bark"], P["leaf"], x, y, r, seed)
    # 墙根灌木：沿东西院墙与北墙点状散布，压住墙脚的空白
    rng = random.Random(303)
    for sx in (-1, 1):
        for k in range(7):
            y = 7.0 + k * 8.0 + rng.uniform(-1.2, 1.2)
            G.bush(P["bark"], P["leaf"], sx * (24.7 + rng.uniform(-0.3, 0.5)), y,
                   rng.uniform(0.95, 1.55), 300 + k + (0 if sx < 0 else 40))
    for k in range(6):
        x = -18.0 + k * 7.2 + rng.uniform(-0.8, 0.8)
        G.bush(P["bark"], P["leaf"], x, -42.3 + rng.uniform(-0.3, 0.3),
               rng.uniform(0.9, 1.4), 380 + k)


def build_props(P):
    # 山门前石狮一对
    for sx in (-1, 1):
        stone_lion(P["stone"], P["gold"], sx * 5.4, Y_GATE + 3.6, s=0.98)
    # 塔前石狮一对
    for sx in (-1, 1):
        stone_lion(P["stone"], P["gold"], sx * 6.0, 13.9, s=0.92)
    # 重门石狮一对（元代）
    for sx in (-1, 1):
        stone_lion(P["stone"], P["gold"], sx * 4.6, Y_CHONGMEN + 4.6, s=1.0)
    # 塔前大香炉
    G.incense_burner(P["stone"], P["gold"], 0, 15.4, s=1.02)
    # 幡杆（一进院中轴两侧，悬幡）
    for sx in (-1, 1):
        G.banner_pole(P["wood"], P["gold"], P["stone"], sx * 7.4, 49.6,
                      cloth=P["plaster"])
    # 石灯：一进院、重门后、塔后、后院各一对
    for y in (45.4, 31.5, -14.5, -21.0):
        for sx in (-1, 1):
            G.stone_lamp(P["stone"], P["gold"], sx * 5.2, y)
    # 塔前石供桌
    P["stone"].box(0, 11.9, 0.42, 2.6, 0.9, 0.84)
    P["stone"].box(0, 11.9, 0.88, 2.82, 1.06, 0.14)
    for sx in (-1, 1):
        P["stone"].box(sx * 0.9, 11.9, 0.20, 0.34, 0.72, 0.40)
    P["gold"].box(0, 11.9, 1.02, 0.34, 0.24, 0.16)
    # 明清古碑八通：前殿遗址两侧各四
    steles = [(-14.6, 26.2, 2.9), (-14.2, 23.4, 2.5), (-14.8, 20.6, 2.7), (-14.3, 18.0, 2.4),
              (14.6, 26.2, 2.8), (14.2, 23.4, 2.6), (14.8, 20.6, 2.3), (14.3, 18.0, 2.7)]
    for (x, y, h) in steles:
        G.stele(P["stone"], P["dark"], P["gold"], x, y, h=h, rot=math.pi * 0.5)
    # 后院经幢一对
    for sx in (-1, 1):
        P["stone"].box(sx * 7.0, -22.0, 0.20, 1.5, 1.5, 0.40)
        P["stone"].tube(0.52, 0.44, 0.40, 3.4, n=8, cx=sx * 7.0, cy=-22.0)
        P["gold"].sphere(sx * 7.0, -22.0, 3.55, 0.22, seg=8, ring=5)
    # 防火水缸：院墙内侧四只
    for (x, y) in ((-22.6, 34.5), (22.6, 34.5), (-22.6, -2.0), (22.6, -2.0)):
        G.water_vat(P["stone"], x, y)
    # 花坛：一进院与后院各一对
    for (x, y, w, d, sd) in ((-8.8, 43.2, 4.4, 2.6, 11), (8.8, 43.2, 4.4, 2.6, 13),
                             (-13.6, -35.0, 4.0, 2.4, 17), (13.6, -35.0, 4.0, 2.4, 19)):
        G.planter(P["brick"], P["stone"], P["bark"], P["leaf"], x, y, w, d, sd)


def build_village(P):
    """院墙外正定古城街坊：成组院落，留出东西向巷道"""
    rng = random.Random(2026)
    k = 0
    for side in (-1, 1):
        for col in range(3):
            x = side * (43.0 + col * 23.0)
            for row in range(3):
                y = -62.0 + row * 52.0 + rng.uniform(-3.0, 3.0)
                w = rng.uniform(15.0, 19.0)
                d = rng.uniform(16.0, 21.0)
                h = rng.uniform(3.5, 4.4)
                G.village_yard(P, x + rng.uniform(-1.5, 1.5), y, w, d, h, seed=k)
                k += 1
    # 巷道小树
    for side in (-1, 1):
        for row in range(3):
            y = -58.0 + row * 52.0
            G.tree(P["bark"], P["leaf"], side * 29.6, y, h=rng.uniform(8.5, 11.0),
                   seed=200 + row + (0 if side < 0 else 40), spread=0.92, style="yu")


# ============================ 主体组装 ============================
def main():
    clear_scene()
    P = new_parts()
    tex = os.path.join(HERE, "tex")

    # ---- 地面与渠 ----
    build_ground(P)
    build_canal(P)

    # ---- 牌坊 ----
    G.paifang(P["stone"], P["plaster"], P["tile"], P["wood"], P["gold"], P["caihua"],
              0, Y_PAIFANG, w=13.4, h=8.4)
    G.bridge(P["stone"], 0, Y_CANAL, span=7.4, width=4.6)

    # ---- 山门（三间，歇山，中开券门）----
    merge_all(P, hall(w=13.2, d=7.6, hcol=5.4, bays=3, kind="xieshan",
                      eave=1.80, plat_h=1.0, steps=5, door_bays=[1],
                      back_door=True, plaque_w=3.3), tx=0, ty=Y_GATE)

    # ---- 东西厢房（三间，硬山，带前廊）----
    for sx in (-1, 1):
        merge_all(P, hall(w=13.0, d=6.0, hcol=4.0, bays=3, kind="yingshan",
                          eave=1.25, plat_h=0.62, steps=2, door_bays=[1],
                          plat_extra=1.2, dg=False), rot=math.pi * 0.5 * sx,
                  tx=sx * 19.2, ty=Y_WING)

    # ---- 重门（三间，歇山）----
    merge_all(P, hall(w=11.4, d=6.4, hcol=4.9, bays=3, kind="xieshan",
                      eave=1.60, plat_h=0.88, steps=3, door_bays=[0, 1, 2],
                      back_door=True, plaque_w=2.8), tx=0, ty=Y_CHONGMEN)

    # ---- 前殿遗址 ----
    merge_all(P, hall_ruins(), tx=0, ty=Y_FRONT)

    # ---- 后殿（五间，歇山，前承抱厦）----
    merge_all(P, hall(w=19.6, d=10.8, hcol=6.0, bays=5, kind="xieshan",
                      eave=2.10, plat_h=1.30, steps=5, door_bays=[2],
                      back_door=False, plat_extra=2.0, rail=True,
                      plaque_w=4.4), tx=0, ty=Y_REAR)

    # ---- 院墙 ----
    build_walls(P)

    # ---- 植物 ----
    build_plants(P)

    # ---- 小品 ----
    build_props(P)

    # ---- 周边民居 ----
    build_village(P)

    # ---- 生成物体 ----
    objs = []
    names = {
        "stone": "S_Stone", "brick": "S_Brick", "plaster": "S_Wall",
        "wood": "S_Wood", "tile": "S_Roof", "paving": "S_Paving",
        "dark": "S_Dark", "gold": "S_Gold", "leaf": "S_Leaf",
        "bark": "S_Bark", "caihua": "S_Caihua", "metal": "S_Metal",
    }
    for k, part in P.items():
        ob = to_object(names[k], part, k, tex)
        if ob:
            objs.append(ob)

    faces = sum(len(o.data.polygons) for o in objs)
    print("SITE_PARTS:", [(o.name, len(o.data.polygons)) for o in objs])
    print("SITE_FACES:", faces)

    zs = [v.co.z for o in objs for v in o.data.vertices]
    xs = [v.co.x for o in objs for v in o.data.vertices]
    ys = [v.co.y for o in objs for v in o.data.vertices]
    print("SITE_BBOX x", round(min(xs), 1), round(max(xs), 1),
          "y", round(min(ys), 1), round(max(ys), 1),
          "z", round(min(zs), 2), round(max(zs), 2))

    glb = os.path.join(HERE, "site.glb")
    bpy.ops.export_scene.gltf(filepath=glb, export_format="GLB", export_apply=True,
                              export_yup=True, use_selection=False,
                              export_cameras=False, export_lights=False,
                              export_image_format="AUTO", export_texcoords=True,
                              export_normals=True)
    bpy.ops.wm.save_as_mainfile(filepath=os.path.join(HERE, "site.blend"))
    print("=== SITE DONE ===")
    print("glb_mb:", round(os.path.getsize(glb) / 1024.0 / 1024.0, 2))


main()
