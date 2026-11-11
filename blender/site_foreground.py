# -*- coding: utf-8 -*-
"""凌霄塔 · 近景压角层（周边细节第三轮）

为什么不做「贴镜头」的前景
--------------------------
Cam_01 在 (47,72,31)、俯角仅约 7°、lens 33 mm，画面上缘对应的是
与相机等高的高空（z≈32 m），而画面里能看到的最近地面也有 ≈83 m。
所以在屏幕左上/右上塞一截"画外树枝"会变成悬在 30 m 空的假物件，
并且 Cam_02 在 (76,104,50) 会把它看成院墙上空的一团飘浮物。

本层改为**世界中真实落地的竖向实体**，靠明暗与位置形成前景框：
左侧院外巷道一棵 24 m 古槐、右侧靠西墙一组 8 m 石经幢与石灯，
两处都由双机位屏幕投影反算过，均落在画面边缘、不遮塔。

锚点（world → Cam_01 / Cam_02 屏幕坐标，v 自下而上）
---------------------------------------------------
古槐   (31, -34, 0)     → (0.09, 0.22) / (0.17, 0.50)
       树冠顶 z=24      → (0.07, 0.57) / (0.15, 0.72)
经幢   (-24, 26, 0)     → (0.88, 0.11) / (0.65, 0.47)
       幢顶 z≈8         → (0.89, 0.26) / (0.66, 0.55)

约束
----
* 不修改塔体、不修改 site.blend 源几何；产物全部 D_ 前缀归入 02b 集合。
* 材质纯程序化：不用顶点色（EEVEE Next 读不到 CORNER 域 FLOAT_COLOR）、
  不引外链贴图。前景按电影剪影处理，比院内中景再暗一档，只留一点
  极淡冷色自发光兜底，避免塌成纯黑。
* 坐标 Z-up，x 东西 / y 南北 / z 高度（米）。
"""
import bpy
import math
import random
from mathutils import Vector

TAU = math.tau
SEED = 20261109

TREE_XY = (31.0, -34.0)
TREE_H = 24.0
STONE_XY = (-24.0, 26.0)
RNG = random.Random(SEED)


# ────────────────────────────── 极简网格容器 ──────────────────────────────
class Geo:
    def __init__(self):
        self.v = []
        self.f = []

    def tri(self, a, b, c):
        i = len(self.v)
        self.v += [tuple(a), tuple(b), tuple(c)]
        self.f.append((i, i + 1, i + 2))

    def quad(self, a, b, c, d):
        i = len(self.v)
        self.v += [tuple(a), tuple(b), tuple(c), tuple(d)]
        self.f.append((i, i + 1, i + 2, i + 3))

    def ngon(self, pts):
        i = len(self.v)
        self.v += [tuple(p) for p in pts]
        self.f.append(tuple(range(i, i + len(pts))))

    def to_object(self, name, mat, coll):
        if not self.f:
            return None
        me = bpy.data.meshes.new(name)
        me.from_pydata(self.v, [], self.f)
        me.update()
        me.materials.append(mat)
        ob = bpy.data.objects.new(name, me)
        coll.objects.link(ob)
        return ob

    def faces(self):
        return len(self.f)


# ────────────────────────────── 几何基元 ─────────────────────────────────
def rod(g, p0, p1, r0, r1, n=6):
    """n 棱台：沿 p0→p1 生成侧面，用于树干与枝。"""
    a, b = Vector(p0), Vector(p1)
    d = (b - a).normalized()
    u = d.cross(Vector((0, 0, 1)))
    if u.length < 1e-4:
        u = d.cross(Vector((1, 0, 0)))
    u.normalize()
    v = d.cross(u).normalized()
    ring0 = [a + (u * math.cos(TAU * i / n) + v * math.sin(TAU * i / n)) * r0
             for i in range(n)]
    ring1 = [b + (u * math.cos(TAU * i / n) + v * math.sin(TAU * i / n)) * r1
             for i in range(n)]
    for i in range(n):
        j = (i + 1) % n
        g.quad(ring0[i], ring0[j], ring1[j], ring1[i])


def prism(g, cx, cy, z0, z1, r0, r1, n=8, rot=0.0):
    """竖直 n 棱台 + 上下盖，用于经幢幢身与石灯柱。"""
    lo = [(cx + r0 * math.cos(TAU * i / n + rot),
           cy + r0 * math.sin(TAU * i / n + rot), z0) for i in range(n)]
    hi = [(cx + r1 * math.cos(TAU * i / n + rot),
           cy + r1 * math.sin(TAU * i / n + rot), z1) for i in range(n)]
    for i in range(n):
        j = (i + 1) % n
        g.quad(lo[i], lo[j], hi[j], hi[i])
    g.ngon(list(reversed(lo)))
    g.ngon(hi)


def box(g, cx, cy, cz, sx, sy, sz):
    hx, hy, hz = sx * 0.5, sy * 0.5, sz * 0.5
    b = [(cx - hx, cy - hy, cz - hz), (cx + hx, cy - hy, cz - hz),
         (cx + hx, cy + hy, cz - hz), (cx - hx, cy + hy, cz - hz)]
    t = [(p[0], p[1], cz + hz) for p in b]
    g.quad(b[3], b[2], b[1], b[0])
    g.quad(t[0], t[1], t[2], t[3])
    for i in range(4):
        j = (i + 1) % 4
        g.quad(b[i], b[j], t[j], t[i])


def pyramid(g, cx, cy, z0, z1, r, n=4, rot=0.0):
    """攒尖顶：n 边底 + 一个尖，用于石灯与经幢宝顶。"""
    base = [(cx + r * math.cos(TAU * i / n + rot),
             cy + r * math.sin(TAU * i / n + rot), z0) for i in range(n)]
    apex = (cx, cy, z1)
    for i in range(n):
        g.tri(base[i], base[(i + 1) % n], apex)
    g.ngon(list(reversed(base)))


def blob(g, c, r, rz, n, rng, jitter=0.25):
    """不规则双锥叶团（与 site_foliage 同构，尺度更大、更暗）。"""
    eq = []
    for i in range(n):
        a = TAU * i / n + rng.uniform(-0.3, 0.3)
        rr = r * (1.0 + rng.uniform(-jitter, jitter))
        eq.append(c + Vector((rr * math.cos(a), rr * math.sin(a),
                              rng.uniform(-0.16, 0.16) * rz)))
    top = c + Vector((rng.uniform(-0.13, 0.13) * r,
                      rng.uniform(-0.13, 0.13) * r, rz * rng.uniform(0.80, 1.05)))
    bot = c + Vector((rng.uniform(-0.13, 0.13) * r,
                      rng.uniform(-0.13, 0.13) * r, -rz * rng.uniform(0.62, 0.88)))
    for i in range(n):
        j = (i + 1) % n
        g.tri(eq[i], eq[j], top)
        g.tri(eq[j], eq[i], bot)


def leaf_card(g, p, size, rng):
    """菱形叶片，打碎叶团轮廓。"""
    z = rng.uniform(-0.92, 0.92)
    th = rng.uniform(0, TAU)
    rr = math.sqrt(max(0.0, 1 - z * z))
    u = Vector((rr * math.cos(th), rr * math.sin(th), z))
    v = u.cross(Vector((rng.uniform(-1, 1), rng.uniform(-1, 1),
                        rng.uniform(-1, 1))))
    if v.length < 1e-4:
        v = u.cross(Vector((0, 0, 1)))
    v.normalize()
    w = size * rng.uniform(0.40, 0.64)
    g.quad(p - u * size, p + v * w, p + u * size, p - v * w)


# ────────────────────────────── 材质 ─────────────────────────────────────
def mat_solid(name, base, emit_cool=0.002, rough=0.92, var=0.30, bump=0.05):
    """石构：仍接一点场景暖光，但整体压到中景以下一档。"""
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    n = m.node_tree
    n.nodes.clear()
    out = n.nodes.new("ShaderNodeOutputMaterial")
    tc = n.nodes.new("ShaderNodeTexCoord")
    noise = n.nodes.new("ShaderNodeTexNoise")
    noise.inputs["Scale"].default_value = 3.4
    noise.inputs["Detail"].default_value = 3.0
    ramp = n.nodes.new("ShaderNodeValToRGB")
    ramp.color_ramp.elements[0].position = 0.20
    ramp.color_ramp.elements[0].color = tuple(x * (1 - var) for x in base) + (1.0,)
    ramp.color_ramp.elements[1].position = 0.82
    ramp.color_ramp.elements[1].color = tuple(x * (1 + var) for x in base) + (1.0,)
    bsdf = n.nodes.new("ShaderNodeBsdfPrincipled")
    bsdf.inputs["Roughness"].default_value = rough
    try:
        # 暖中性兜底，绝不用冷蓝：冷色自发光会把前景染成灰蓝石头感
        bsdf.inputs["Emission Color"].default_value = (0.50, 0.38, 0.26, 1.0)
        bsdf.inputs["Emission Strength"].default_value = emit_cool
    except Exception:
        pass
    if bump:
        bp = n.nodes.new("ShaderNodeBump")
        bp.inputs["Strength"].default_value = bump
        bp.inputs["Distance"].default_value = 0.03
        n.links.new(noise.outputs["Fac"], bp.inputs["Height"])
        n.links.new(bp.outputs["Normal"], bsdf.inputs["Normal"])
    n.links.new(tc.outputs["Object"], noise.inputs["Vector"])
    n.links.new(noise.outputs["Fac"], ramp.inputs["Fac"])
    n.links.new(ramp.outputs["Color"], bsdf.inputs["Base Color"])
    n.links.new(bsdf.outputs["BSDF"], out.inputs["Surface"])
    m.use_backface_culling = False
    return m


def mat_silhouette(name, col, var=0.34, scale=1.1, sky=0.42):
    """前景剪影专用：纯 Emission，完全不吃 32 盏场景灯。

    v1 用 Principled 漫反射 + 冷蓝自发光，大块朝上的叶团被方向光推成
    浅灰蓝"石头团"；v2 改纯 Emission 后颜色对了却平涂成一张纸。
    这里补一层**法线天光**：用 Geometry.Normal 与偏上方向做点积，
    朝上的面略亮、背光面压暗，模拟天光体积感，但仍不参与场景光照。
    """
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    n = m.node_tree
    n.nodes.clear()
    out = n.nodes.new("ShaderNodeOutputMaterial")
    tc = n.nodes.new("ShaderNodeTexCoord")
    noise = n.nodes.new("ShaderNodeTexNoise")
    noise.inputs["Scale"].default_value = scale
    noise.inputs["Detail"].default_value = 3.0
    noise.inputs["Roughness"].default_value = 0.68
    ramp = n.nodes.new("ShaderNodeValToRGB")
    ramp.color_ramp.elements[0].position = 0.18
    ramp.color_ramp.elements[0].color = tuple(x * (1 - var) for x in col) + (1.0,)
    ramp.color_ramp.elements[1].position = 0.84
    ramp.color_ramp.elements[1].color = tuple(x * (1 + var) for x in col) + (1.0,)

    geo = n.nodes.new("ShaderNodeNewGeometry")
    dot = n.nodes.new("ShaderNodeVectorMath")
    dot.operation = "DOT_PRODUCT"
    dot.inputs[1].default_value = (0.24, 0.18, 0.95)
    mr = n.nodes.new("ShaderNodeMapRange")
    mr.inputs["From Min"].default_value = -1.0
    mr.inputs["From Max"].default_value = 1.0
    mr.inputs["To Min"].default_value = 1.0 - sky
    mr.inputs["To Max"].default_value = 1.0 + sky
    mul = n.nodes.new("ShaderNodeMixRGB")
    mul.blend_type = "MULTIPLY"
    mul.inputs[0].default_value = 1.0
    e = n.nodes.new("ShaderNodeEmission")
    e.inputs["Strength"].default_value = 1.0

    n.links.new(tc.outputs["Object"], noise.inputs["Vector"])
    n.links.new(noise.outputs["Fac"], ramp.inputs["Fac"])
    n.links.new(geo.outputs["Normal"], dot.inputs[0])
    n.links.new(dot.outputs["Value"], mr.inputs["Value"])
    n.links.new(ramp.outputs["Color"], mul.inputs[1])
    n.links.new(mr.outputs["Result"], mul.inputs[2])
    n.links.new(mul.outputs["Color"], e.inputs["Color"])
    n.links.new(e.outputs["Emission"], out.inputs["Surface"])
    m.use_backface_culling = False
    return m


def mat_lamp(name, col, strength):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    n = m.node_tree
    n.nodes.clear()
    out = n.nodes.new("ShaderNodeOutputMaterial")
    e = n.nodes.new("ShaderNodeEmission")
    e.inputs["Color"].default_value = (*col, 1.0)
    e.inputs["Strength"].default_value = strength
    n.links.new(e.outputs["Emission"], out.inputs["Surface"])
    m.use_backface_culling = False
    return m


# ────────────────────────────── A 寺外古槐 ──────────────────────────────
def build_tree(wood, crown, rng):
    x, y = TREE_XY
    h = TREE_H

    # 主干：5 段带弯曲，底部 0.82 m 收到 0.34 m；朝画面内（-x,+y）略倾
    # 主干止于 0.62h ≈ 14.9 m，其上由主枝撑开树冠
    pts = [(x, y, 0.0)]
    for i in range(1, 6):
        t = i / 5.0
        pts.append((x - 0.85 * t + rng.uniform(-0.16, 0.16),
                    y + 0.55 * t + rng.uniform(-0.16, 0.16),
                    h * 0.62 * t))
    for i in range(5):
        r0 = 0.82 - i * 0.105
        rod(wood, pts[i], pts[i + 1], r0, r0 * 0.88, n=9)
    # 根部起鼓
    for k in range(6):
        a = k * TAU / 6 + 0.2
        box(wood, x + math.cos(a) * 0.95, y + math.sin(a) * 0.95,
            0.42, 0.72, 0.72, 0.85)

    top = Vector(pts[-1])
    tips = []

    # 一级主枝 4 根：向外放射，略偏向画面内（-x,+y）
    for k in range(4):
        a = TAU * k / 4 + rng.uniform(-0.35, 0.35)
        length = rng.uniform(5.4, 7.8)
        d = Vector((math.cos(a) * 0.92 - 0.20,
                    math.sin(a) * 0.92 + 0.16,
                    rng.uniform(0.32, 0.62))).normalized()
        p1 = top + d * length
        rod(wood, top, p1, 0.34, 0.20, n=6)
        # 二级枝
        for j in range(3):
            a2 = a + rng.uniform(-0.85, 0.85)
            d2 = Vector((math.cos(a2) * 0.9 - 0.16,
                         math.sin(a2) * 0.9 + 0.12,
                         rng.uniform(0.10, 0.50))).normalized()
            p2 = p1 + d2 * rng.uniform(2.6, 4.4)
            rod(wood, p1, p2, 0.18, 0.09, n=5)
            tips.append(p2)
        tips.append(p1)
    # 冠顶再补一簇
    tips.append(top + Vector((-0.6, 0.4, 4.2)))

    # 叶团：每个枝端 1 大团 + 4 中团 + 若干叶片；尺度略放大、间距收紧，
    # 让树冠连成一片而不是几朵互不挨着的"云"
    for t in tips:
        c = t + Vector((rng.uniform(-0.8, 0.8), rng.uniform(-0.8, 0.8),
                        rng.uniform(-0.4, 0.7)))
        r = rng.uniform(1.90, 2.90)
        blob(crown, c, r, r * rng.uniform(0.76, 0.98), 6, rng, jitter=0.28)
        for _ in range(4):
            d = Vector((rng.uniform(-1, 1), rng.uniform(-1, 1),
                        rng.uniform(-0.5, 0.9))).normalized()
            p = c + d * r * rng.uniform(0.60, 1.02)
            sr = r * rng.uniform(0.42, 0.58)
            blob(crown, p, sr, sr * 0.90, 4, rng, jitter=0.32)
        for _ in range(10):
            d = Vector((rng.uniform(-1, 1), rng.uniform(-1, 1),
                        rng.uniform(-0.4, 1.0))).normalized()
            p = c + d * r * rng.uniform(1.02, 1.36)
            leaf_card(crown, p, r * rng.uniform(0.15, 0.26), rng)

    # 冠心补团：填掉主枝放射留下的中央空洞
    hub = top + Vector((-0.5, 0.3, 3.0))
    for k in range(5):
        a = TAU * k / 5 + rng.uniform(-0.3, 0.3)
        c = hub + Vector((math.cos(a) * rng.uniform(1.6, 3.0),
                          math.sin(a) * rng.uniform(1.6, 3.0),
                          rng.uniform(-0.6, 1.2)))
        rr = rng.uniform(1.9, 2.7)
        blob(crown, c, rr, rr * 0.86, 6, rng, jitter=0.26)
        for _ in range(7):
            d = Vector((rng.uniform(-1, 1), rng.uniform(-1, 1),
                        rng.uniform(-0.3, 1))).normalized()
            leaf_card(crown, c + d * rr * rng.uniform(1.0, 1.35),
                      rr * rng.uniform(0.15, 0.25), rng)
    return len(tips)


# ────────────────────────────── B 石经幢与石灯 ──────────────────────────
def build_stone(stone, lamp, rng):
    x, y = STONE_XY

    # 经幢：基座 → 三段八角幢身 → 三层幢盘 → 宝顶，总高 ≈ 8 m
    box(stone, x, y, 0.22, 2.60, 2.60, 0.44)
    box(stone, x, y, 0.52, 2.10, 2.10, 0.18)
    z = 0.61
    for i in range(3):
        hz = 1.55 if i == 0 else 1.30
        r0 = 0.76 - i * 0.07
        prism(stone, x, y, z, z + hz, r0, r0 * 0.94, n=8, rot=TAU / 16)
        z += hz
        prism(stone, x, y, z, z + 0.16, r0 * 1.28, r0 * 1.16, n=8, rot=TAU / 16)
        z += 0.16
    prism(stone, x, y, z, z + 0.34, 0.52, 0.34, n=8, rot=TAU / 16)
    pyramid(stone, x, y, z + 0.34, z + 1.28, 0.40, n=8, rot=TAU / 16)

    # 双石灯：分列经幢两侧，高 ≈ 2.2 m，灯室四面透出暖光
    lamps = []
    for sx in (-1, 1):
        lx = x + sx * 3.05
        box(stone, lx, y, 0.16, 1.10, 1.10, 0.32)
        prism(stone, lx, y, 0.32, 1.42, 0.24, 0.20, n=6)
        box(stone, lx, y, 1.52, 0.92, 0.92, 0.20)     # 灯室下枋
        box(stone, lx, y, 1.96, 0.92, 0.92, 0.16)     # 灯室上枋
        for k in range(4):
            a = TAU * k / 4
            # 四角立柱，中间留空透光
            box(stone, lx + math.cos(a + TAU / 8) * 0.40,
                y + math.sin(a + TAU / 8) * 0.40, 1.74, 0.13, 0.13, 0.44)
        pyramid(stone, lx, y, 2.04, 2.46, 0.72, n=4, rot=TAU / 8)
        # 灯芯：小发光盒，藏在灯室内
        box(lamp, lx, y, 1.74, 0.34, 0.34, 0.30)
        lamps.append((lx, y, 1.74))

    # 短石栏：沿 x 方向 6.4 m，望柱 + 栏板，把经幢基座与地面收在一起
    for k in range(5):
        px = x - 3.2 + k * 1.6
        box(stone, px, y - 1.65, 0.48, 0.30, 0.30, 0.96)
        pyramid(stone, px, y - 1.65, 0.96, 1.16, 0.22, n=4, rot=TAU / 8)
    for k in range(4):
        px = x - 2.4 + k * 1.6
        box(stone, px, y - 1.65, 0.52, 1.34, 0.14, 0.50)
    return lamps


# ────────────────────────────── C 下缘收束 ──────────────────────────────
def build_ground_litter(grass, rng):
    """两处锚点周围贴地的草丛与碎石：低矮、暗、不成片，只打散地面直线。"""
    for (cx, cy, spread, count) in ((TREE_XY[0], TREE_XY[1], 6.5, 90),
                                    (STONE_XY[0], STONE_XY[1], 3.5, 46),
                                    (35.0, -11.0, 5.0, 42),
                                    (-20.0, 26.0, 4.0, 36)):
        for _ in range(count):
            px = cx + rng.uniform(-spread, spread)
            py = cy + rng.uniform(-spread, spread)
            z = 0.035
            if rng.random() < 0.62:
                # 两三片细长草叶
                for _ in range(rng.randint(2, 3)):
                    a = rng.uniform(0, TAU)
                    hh = rng.uniform(0.18, 0.46)
                    w = rng.uniform(0.035, 0.075)
                    dx, dy = math.cos(a) * w, math.sin(a) * w
                    grass.tri((px - dx, py - dy, z), (px + dx, py + dy, z),
                              (px + rng.uniform(-0.10, 0.10),
                               py + rng.uniform(-0.10, 0.10), z + hh))
            else:
                r = rng.uniform(0.07, 0.19)
                grass.ngon([(px + r * math.cos(TAU * i / 5),
                             py + r * math.sin(TAU * i / 5), z)
                            for i in range(5)])


# ────────────────────────────── 入口 ─────────────────────────────────────
def build(coll, here=None):
    """在 coll 中生成近景压角层，返回统计字典。"""
    rng = random.Random(SEED)
    wood, crown, stone, lamp, grass = Geo(), Geo(), Geo(), Geo(), Geo()

    tips = build_tree(wood, crown, rng)
    build_stone(stone, lamp, rng)
    build_ground_litter(grass, rng)

    # 前景古槐朝塔那根枝上悬一盏灯笼：给左侧剪影一个暖色锚点与尺度参照。
    # 只做自发光几何，不新增灯光对象，避免改动既有 32 盏灯的配光平衡。
    lx, ly, lz = TREE_XY[0] - 3.8, TREE_XY[1] + 2.6, 15.2
    prism(lamp, lx, ly, lz - 0.28, lz + 0.28, 0.25, 0.25, n=8, rot=TAU / 16)
    prism(lamp, lx, ly, lz + 0.28, lz + 0.38, 0.29, 0.13, n=8, rot=TAU / 16)
    prism(lamp, lx, ly, lz - 0.38, lz - 0.28, 0.13, 0.29, n=8, rot=TAU / 16)
    rod(lamp, (lx, ly, lz + 0.38), (lx, ly, lz + 1.15), 0.014, 0.014, n=4)

    groups = [
        ("D_16 前景古槐·树干与枝", wood, mat_silhouette(
            "D_FG_Bark_前景树干", (0.0052, 0.0042, 0.0032),
            var=0.30, scale=1.8, sky=0.30)),
        ("D_17 前景古槐·叶冠剪影", crown, mat_silhouette(
            "D_FG_Leaf_前景叶冠", (0.0080, 0.0140, 0.0088),
            var=0.38, scale=1.1, sky=0.44)),
        ("D_18 前景石经幢与石灯", stone, mat_solid(
            "D_FG_Stone_前景石构", (0.0042, 0.0040, 0.0036),
            emit_cool=0.006, var=0.24)),
        ("D_19 石灯与枝上灯笼暖光", lamp, mat_lamp(
            "D_FG_Lamp_暖光", (1.0, 0.30, 0.07), 0.85)),
        ("D_20 前景草丛与碎石", grass, mat_silhouette(
            "D_FG_Grass_前景草石", (0.0050, 0.0078, 0.0042),
            var=0.34, scale=5.0, sky=0.20)),
    ]
    total = 0
    made = 0
    for name, geo, mat in groups:
        if geo.to_object(name, mat, coll):
            made += 1
            total += geo.faces()
    print("FOREGROUND_OK tree_tips=", tips, "objects=", made, "faces=", total)
    return {"objects": made, "faces": total, "tree_tips": tips}
