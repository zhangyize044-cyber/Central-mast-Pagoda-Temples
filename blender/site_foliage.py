# -*- coding: utf-8 -*-
"""凌霄塔 · 树冠细化层（周边细节第二轮）

思路
----
`site.blend` 里的 S_Leaf 是 26928 面的低模球簇（seg=6 / ring=3~4），
在夜景成片里是最露「程序化痕迹」的一处。本模块不去改源网格，而是：

1. 按顶点连通分量从 S_Leaf 反推出**每一个球簇的中心与半径**——这些
   位置正好是 site_geo.tree() 三级分枝的枝端，等于拿到了原树的骨架；
2. 在每个枝端用四层几何重做冠形：内芯体块 / 多尺度叶簇 / 轮廓叶片 /
   外露末梢细枝，让树冠有体积、有镂空边缘、有枝条穿透感；
3. 大树冠与墙根灌木按高度分层，密度不同，避免全场景一个模子。

约束
----
* 不修改塔体，不修改 site.blend 源几何；S_Leaf 由 build_scene.py 在
  合并场景里隐藏，随时可一键恢复。
* 材质纯程序化：上一轮已确认 EEVEE Next 读不到 CORNER 域顶点色，
  且 32 盏灯 + exposure 1.25 会把浅色漫反射推到饱和，故不用顶点色、
  不引入外链贴图，Base Color 全部按线性空间的暗绿取值。
* 坐标 Z-up，x 东西 / y 南北 / z 高度（米），与 site.blend 一致。
"""
import bpy
import math
import random
from collections import defaultdict
from mathutils import Vector

TAU = math.tau
SEED = 20261109


# ────────────────────────────── 极简网格容器 ──────────────────────────────
class Geo:
    """只收顶点与面，不写顶点色（本层刻意不依赖 DCol）。"""

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


# ────────────────────────────── 反推枝端球簇 ──────────────────────────────
def extract_clusters(obj):
    """site_geo.Part.sphere() 每个球都独占一批顶点，故按面连通分量即可
    精确还原每一团叶球；包围盒半长 ≈ 球半径（含 ry/rz 缩放）。"""
    me = obj.data
    mw = obj.matrix_world
    par = list(range(len(me.vertices)))

    def find(x):
        while par[x] != x:
            par[x] = par[par[x]]
            x = par[x]
        return x

    def union(a, b):
        ra, rb = find(a), find(b)
        if ra != rb:
            par[rb] = ra

    for poly in me.polygons:
        vs = poly.vertices
        v0 = vs[0]
        for k in range(1, len(vs)):
            union(v0, vs[k])

    groups = defaultdict(list)
    for v in me.vertices:
        groups[find(v.index)].append(mw @ v.co)

    out = []
    for pts in groups.values():
        if len(pts) < 8:          # 过滤孤立面等噪声
            continue
        lo = [min(p[k] for p in pts) for k in range(3)]
        hi = [max(p[k] for p in pts) for k in range(3)]
        c = Vector([(lo[k] + hi[k]) * 0.5 for k in range(3)])
        h = [(hi[k] - lo[k]) * 0.5 for k in range(3)]
        r = (h[0] + h[1]) * 0.5
        if r < 0.10 or h[2] < 0.06:
            continue
        out.append((c, r, h[2]))
    return out


# ────────────────────────────── 几何基元 ─────────────────────────────────
def _sphere_dir(rng, up_bias=0.0):
    z = rng.uniform(-1.0, 1.0) + up_bias
    z = max(-0.95, min(0.95, z))
    th = rng.uniform(0.0, TAU)
    rr = math.sqrt(max(0.0, 1.0 - z * z))
    return Vector((rr * math.cos(th), rr * math.sin(th), z))


def blob(g, c, r, rz, n, rng, jitter=0.22, tilt=0.0):
    """不规则双锥体：n 个赤道点 + 顶/底，2n 个三角面。
    比球便宜，扰动后没有规整的经纬线。"""
    eq = []
    for i in range(n):
        a = TAU * i / n + rng.uniform(-0.28, 0.28)
        rr = r * (1.0 + rng.uniform(-jitter, jitter))
        eq.append(c + Vector((rr * math.cos(a), rr * math.sin(a),
                              rng.uniform(-0.16, 0.16) * rz + tilt)))
    top = c + Vector((rng.uniform(-0.14, 0.14) * r,
                      rng.uniform(-0.14, 0.14) * r,
                      rz * rng.uniform(0.78, 1.02)))
    bot = c + Vector((rng.uniform(-0.14, 0.14) * r,
                      rng.uniform(-0.14, 0.14) * r,
                      -rz * rng.uniform(0.62, 0.88)))
    for i in range(n):
        j = (i + 1) % n
        g.tri(eq[i], eq[j], top)
        g.tri(eq[j], eq[i], bot)


def leaf_card(g, p, size, rng):
    """一片菱形叶：随机 3D 朝向，法线大致朝冠外，负责打碎球形轮廓。"""
    u = _sphere_dir(rng).normalized()
    v = u.cross(_sphere_dir(rng))
    if v.length < 1e-4:
        v = u.cross(Vector((0, 0, 1)))
    v.normalize()
    w = size * rng.uniform(0.42, 0.66)
    a = p - u * size
    b = p + v * w
    c = p + u * size
    d = p - v * w
    g.quad(a, b, c, d)


def twig(g, a, b, w, rng):
    """末梢细枝：两片交叉的窄 quad，比圆柱便宜且夜景里读得出。"""
    d = (b - a)
    u = d.cross(Vector((0, 0, 1)))
    if u.length < 1e-4:
        u = d.cross(Vector((1, 0, 0)))
    u.normalize()
    v = d.cross(u).normalized()
    w *= rng.uniform(0.85, 1.15)
    g.quad(a + u * w, b + u * w * 0.28, b - u * w * 0.28, a - u * w)
    g.quad(a + v * w, b + v * w * 0.28, b - v * w * 0.28, a - v * w)


# ────────────────────────────── 程序化材质 ───────────────────────────────
def foliage_mat(name, base, rough=0.90, emit=0.0, var=0.42, bump=0.06):
    """暗绿哑光 + 米级噪声斑驳；极淡自发光兜底，避免夜景里塌成纯黑。
    数值是线性空间，参考原 S_Leaf 贴图 #3C4A26 的线性值 ≈ (0.045,0.068,0.019)。"""
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    n = m.node_tree
    n.nodes.clear()
    out = n.nodes.new("ShaderNodeOutputMaterial")

    tc = n.nodes.new("ShaderNodeTexCoord")
    noise = n.nodes.new("ShaderNodeTexNoise")
    noise.inputs["Scale"].default_value = 7.2
    noise.inputs["Detail"].default_value = 3.0
    noise.inputs["Roughness"].default_value = 0.68
    ramp = n.nodes.new("ShaderNodeValToRGB")
    ramp.color_ramp.elements[0].position = 0.22
    ramp.color_ramp.elements[0].color = tuple(x * (1.0 - var) for x in base) + (1.0,)
    ramp.color_ramp.elements[1].position = 0.80
    ramp.color_ramp.elements[1].color = tuple(x * (1.0 + var) for x in base) + (1.0,)

    bsdf = n.nodes.new("ShaderNodeBsdfPrincipled")
    bsdf.inputs["Roughness"].default_value = rough
    if emit:
        try:
            bsdf.inputs["Emission Color"].default_value = (*base, 1.0)
            bsdf.inputs["Emission Strength"].default_value = emit
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
    m.use_backface_culling = False       # 叶片是单面卡片，必须双面可见
    return m


# ────────────────────────────── 冠形生成 ─────────────────────────────────
def build_cluster(core, clump, leaf, branch, c, r, rz, is_tree, rng):
    """把一团低模球替换成四层冠形；所有位置都围绕原球心，不改骨架。"""
    # 1) 内芯：维持体积，半径收到 0.55~0.70 倍，让外缘出现镂空
    k = rng.uniform(0.68, 0.80)
    blob(core, c, r * k, rz * k * 0.92, 6 if is_tree else 5, rng,
         jitter=0.26, tilt=rng.uniform(-0.10, 0.10) * rz)

    # 2) 多尺度叶簇：贴在 0.60~1.10 r 的壳层，上半略密
    ncl = 6 if is_tree else 3
    for _ in range(ncl):
        d = _sphere_dir(rng, up_bias=0.22).normalized()
        rad = r * rng.uniform(0.60, 1.08)
        p = c + Vector((d.x * rad, d.y * rad, d.z * rad * (rz / max(r, 0.1)) * 0.82))
        sr = r * rng.uniform(0.19, 0.34)
        blob(clump, p, sr, sr * rng.uniform(0.70, 1.05), 3, rng, jitter=0.32)

    # 3) 轮廓叶片：撒在 0.88~1.22 r 外缘，负责把光滑球边打碎
    nlf = 11 if is_tree else 5
    for _ in range(nlf):
        d = _sphere_dir(rng, up_bias=0.16).normalized()
        rad = r * rng.uniform(0.94, 1.28)
        p = c + Vector((d.x * rad, d.y * rad, d.z * rad * (rz / max(r, 0.1)) * 0.78))
        leaf_card(leaf, p, r * rng.uniform(0.085, 0.175), rng)

    # 4) 外露末梢枝：只在乔木上做，让 S_Bark 的枝条视觉上穿进叶冠
    if is_tree:
        for _ in range(3):
            d = _sphere_dir(rng, up_bias=0.42).normalized()
            p0 = c + d * r * 0.34
            p1 = c + d * r * rng.uniform(1.05, 1.32)
            twig(branch, p0, p1, r * 0.032, rng)


# ────────────────────────────── 入口 ─────────────────────────────────────
def build(coll, leaf_obj=None, here=None):
    """在 coll 中生成细化树冠，返回统计字典。"""
    if leaf_obj is None:
        leaf_obj = bpy.data.objects.get("S_Leaf")
    if leaf_obj is None or leaf_obj.type != "MESH":
        print("FOLIAGE_SKIP no S_Leaf")
        return {"clusters": 0, "faces": 0, "objects": 0}

    clusters = extract_clusters(leaf_obj)
    if not clusters:
        print("FOLIAGE_SKIP no clusters")
        return {"clusters": 0, "faces": 0, "objects": 0}

    core, clump, leaf, branch = Geo(), Geo(), Geo(), Geo()
    rng = random.Random(SEED)
    n_tree = n_bush = 0

    # 以簇心为种子的一部分，保证每次重建结果完全一致
    for (c, r, rz) in clusters:
        is_tree = c.z > 2.5 and r > 0.42
        key = (round(c.x * 100) * 73856093) ^ (round(c.y * 100) * 19349663) \
              ^ (round(c.z * 100) * 83492791) ^ (round(r * 1000) * 2654435761) ^ SEED
        local = random.Random(key & 0xffffffff)
        build_cluster(core, clump, leaf, branch, c, r, rz, is_tree, local)
        n_tree += int(is_tree)
        n_bush += int(not is_tree)

    groups = [
        ("D_12 树冠·内芯体块", core, foliage_mat(
            "D_Foliage_Core_内芯", (0.0060, 0.0100, 0.0042), emit=0.004, var=0.26)),
        ("D_13 树冠·多尺度叶簇", clump, foliage_mat(
            "D_Foliage_Clump_叶簇", (0.0100, 0.0155, 0.0062), emit=0.006, var=0.28)),
        ("D_14 树冠·轮廓叶片", leaf, foliage_mat(
            "D_Foliage_Leaf_叶片", (0.0135, 0.0200, 0.0078), emit=0.008,
            var=0.26, bump=0.0)),
        ("D_15 树冠·外露末梢枝", branch, foliage_mat(
            "D_Foliage_Twig_细枝", (0.0080, 0.0060, 0.0040), emit=0.0,
            var=0.22, bump=0.0)),
    ]
    total = 0
    made = 0
    for name, geo, mat in groups:
        ob = geo.to_object(name, mat, coll)
        if ob:
            made += 1
            total += geo.faces()
    print("FOLIAGE_OK clusters=", len(clusters), "tree=", n_tree,
          "bush=", n_bush, "objects=", made, "faces=", total)
    return {"clusters": len(clusters), "tree": n_tree, "bush": n_bush,
            "objects": made, "faces": total}
