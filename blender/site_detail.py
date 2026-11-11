# -*- coding: utf-8 -*-
"""凌霄塔 · 周边细节与氛围层（增量几何）

设计约束
--------
1. 完全不触碰塔体：不 import build_tower、不修改 lingxiao_tower.blend 里任何对象。
2. 完全不触碰 site.blend 源几何：本模块只「新增」对象，名字统一 D_ 前缀。
3. 坐标系与 site.blend 一致：Z-up，x 东西、y 南北（牌坊在 +y）、z 高度（米）。
4. 单文件场景由 build_scene.py 调用 build() 后统一 pack_all，故本层只用
   程序化材质，不引入任何外部贴图，避免新增外链依赖。

分层
----
A 铺装   实体青石板（错缝 / 微起伏 / 逐块色差）+ 湿痕 + 落叶苔痕
B 水石   石渠水面（低粗糙度 + 波纹 + 暖光倒影）
C 灯火   殿宇与古城民居的暖窗光点
D 大气   香炉青烟、院内贴地雾、远景大气透视雾、地平线柔化
E 收束   塔前月台散水边缘的碎石化（打破过于规整的直线）
"""
import bpy
import math
import random
from mathutils import Vector

TAU = math.tau
RNG = random.Random(20261108)

# 相机在 (47, 72, 31) 看向 (0, 1, 20.5)：视线朝 -y，故远景在 y 负方向。
CAM_XY = (47.0, 72.0)


# ────────────────────────────── 轻量网格容器 ──────────────────────────────
class Mesh:
    """逐顶点颜色 + 面列表，最后一次性落成一个 mesh 对象。"""

    def __init__(self):
        self.v = []
        self.c = []
        self.f = []

    def _v(self, p, col):
        self.v.append(tuple(p))
        self.c.append(tuple(col[:3]))
        return len(self.v) - 1

    def quad(self, p0, p1, p2, p3, c0, c1=None, c2=None, c3=None):
        c1 = c1 or c0
        c2 = c2 or c0
        c3 = c3 or c0
        a = self._v(p0, c0)
        b = self._v(p1, c1)
        c = self._v(p2, c2)
        d = self._v(p3, c3)
        self.f.append((a, b, c, d))

    def tri(self, p0, p1, p2, c0, c1=None, c2=None):
        c1 = c1 or c0
        c2 = c2 or c0
        a = self._v(p0, c0)
        b = self._v(p1, c1)
        c = self._v(p2, c2)
        self.f.append((a, b, c))

    def ngon(self, pts, col):
        idx = [self._v(p, col) for p in pts]
        self.f.append(tuple(idx))

    def face_count(self):
        return len(self.f)

    def to_object(self, name, mat, coll):
        if not self.f:
            return None
        me = bpy.data.meshes.new(name)
        me.from_pydata(self.v, [], self.f)
        me.update()
        ca = me.color_attributes.new(name="DCol", type="FLOAT_COLOR", domain="CORNER")
        for loop in me.loops:
            r, g, b = self.c[loop.vertex_index]
            ca.data[loop.index].color = (r, g, b, 1.0)
        me.materials.append(mat)
        ob = bpy.data.objects.new(name, me)
        coll.objects.link(ob)
        return ob


# ────────────────────────────── 材质工厂 ─────────────────────────────────
def _new(name):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    n = m.node_tree
    n.nodes.clear()
    out = n.nodes.new("ShaderNodeOutputMaterial")
    return m, n, out


def _attr(n):
    """读取 DCol。EEVEE Next 下 ShaderNodeAttribute 对 CORNER 域的
    FLOAT_COLOR 属性会退回默认白色，必须用专用的 Vertex Color 节点。"""
    try:
        a = n.nodes.new("ShaderNodeVertexColor")
        a.layer_name = "DCol"
    except Exception:
        a = n.nodes.new("ShaderNodeAttribute")
        a.attribute_name = "DCol"
    return a


def _blended(m):
    """EEVEE Next 的透明混合模式；不同版本属性名不同，逐个兜底。"""
    for key, val in (("surface_render_method", "BLENDED"),
                     ("surface_render_method", "DITHERED"),
                     ("blend_method", "BLEND")):
        try:
            setattr(m, key, val)
            return
        except Exception:
            continue


def mat_slab():
    """青石板：完全程序化，不依赖顶点色（EEVEE 下更可靠）。

    Object 坐标的 Voronoi cell ≈ 1.3 m ≈ 一块石板，给出逐块色阶；
    细噪给颗粒与微凹凸；整体锁在深青灰区间，避免 32 盏灯下过曝。
    """
    m, n, out = _new("D_Slab_青石板")
    tc = n.nodes.new("ShaderNodeTexCoord")
    vor = n.nodes.new("ShaderNodeTexVoronoi")
    vor.inputs["Scale"].default_value = 0.78
    vor.inputs["Randomness"].default_value = 0.85
    ramp = n.nodes.new("ShaderNodeValToRGB")
    ramp.color_ramp.elements[0].position = 0.08
    ramp.color_ramp.elements[0].color = (0.0080, 0.0076, 0.0070, 1.0)
    ramp.color_ramp.elements[1].position = 0.92
    ramp.color_ramp.elements[1].color = (0.0220, 0.0208, 0.0188, 1.0)
    noise = n.nodes.new("ShaderNodeTexNoise")
    noise.inputs["Scale"].default_value = 26.0
    noise.inputs["Detail"].default_value = 3.0
    grain = n.nodes.new("ShaderNodeValToRGB")
    grain.color_ramp.elements[0].color = (0.74, 0.72, 0.70, 1.0)
    grain.color_ramp.elements[1].color = (1.16, 1.14, 1.10, 1.0)
    mul = n.nodes.new("ShaderNodeMixRGB")
    mul.blend_type = "MULTIPLY"
    mul.inputs[0].default_value = 1.0
    bsdf = n.nodes.new("ShaderNodeBsdfPrincipled")
    bsdf.inputs["Roughness"].default_value = 0.86
    bump = n.nodes.new("ShaderNodeBump")
    bump.inputs["Strength"].default_value = 0.16
    bump.inputs["Distance"].default_value = 0.022
    n.links.new(tc.outputs["Object"], vor.inputs["Vector"])
    n.links.new(vor.outputs["Color"], ramp.inputs["Fac"])
    n.links.new(noise.outputs["Fac"], grain.inputs["Fac"])
    n.links.new(noise.outputs["Fac"], bump.inputs["Height"])
    n.links.new(ramp.outputs["Color"], mul.inputs[1])
    n.links.new(grain.outputs["Color"], mul.inputs[2])
    n.links.new(mul.outputs["Color"], bsdf.inputs["Base Color"])
    n.links.new(bump.outputs["Normal"], bsdf.inputs["Normal"])
    n.links.new(bsdf.outputs["BSDF"], out.inputs["Surface"])
    m.use_backface_culling = False
    return m


def mat_flat(name, rough, col, coat=0.0, palette=None):
    """固定暗色（或按空间 Noise 在色表间变化），不读顶点色。"""
    m, n, out = _new(name)
    bsdf = n.nodes.new("ShaderNodeBsdfPrincipled")
    bsdf.inputs["Roughness"].default_value = rough
    if coat:
        try:
            bsdf.inputs["Coat Weight"].default_value = coat
            bsdf.inputs["Coat Roughness"].default_value = 0.12
        except Exception:
            pass
    if palette:
        noise = n.nodes.new("ShaderNodeTexNoise")
        noise.inputs["Scale"].default_value = 3.2
        noise.inputs["Detail"].default_value = 2.0
        ramp = n.nodes.new("ShaderNodeValToRGB")
        els = ramp.color_ramp.elements
        els[0].position, els[0].color = 0.0, (*palette[0], 1.0)
        els[1].position, els[1].color = 1.0, (*palette[-1], 1.0)
        for i, c in enumerate(palette[1:-1], 1):
            e = els.new(i / (len(palette) - 1))
            e.color = (*c, 1.0)
        n.links.new(noise.outputs["Fac"], ramp.inputs["Fac"])
        n.links.new(ramp.outputs["Color"], bsdf.inputs["Base Color"])
    else:
        bsdf.inputs["Base Color"].default_value = (*col, 1.0)
    n.links.new(bsdf.outputs["BSDF"], out.inputs["Surface"])
    m.use_backface_culling = False
    return m


def mat_water():
    m, n, out = _new("D_Water_石渠")
    bsdf = n.nodes.new("ShaderNodeBsdfPrincipled")
    bsdf.inputs["Base Color"].default_value = (0.012, 0.022, 0.026, 1.0)
    bsdf.inputs["Roughness"].default_value = 0.085
    bsdf.inputs["Metallic"].default_value = 0.28
    wave = n.nodes.new("ShaderNodeTexWave")
    wave.wave_type = "BANDS"
    wave.bands_direction = "Y"
    wave.inputs["Scale"].default_value = 7.0
    wave.inputs["Distortion"].default_value = 3.2
    wave.inputs["Detail"].default_value = 2.0
    bump = n.nodes.new("ShaderNodeBump")
    bump.inputs["Strength"].default_value = 0.16
    bump.inputs["Distance"].default_value = 0.06
    n.links.new(wave.outputs["Color"], bump.inputs["Height"])
    n.links.new(bump.outputs["Normal"], bsdf.inputs["Normal"])
    n.links.new(bsdf.outputs["BSDF"], out.inputs["Surface"])
    m.use_backface_culling = False
    return m


def mat_emission(name, col, strength):
    m, n, out = _new(name)
    e = n.nodes.new("ShaderNodeEmission")
    e.inputs["Color"].default_value = (*col, 1.0)
    e.inputs["Strength"].default_value = strength
    n.links.new(e.outputs["Emission"], out.inputs["Surface"])
    m.use_backface_culling = False
    return m


def mat_haze(name, col, strength, fade="z", base=0.10):
    """透明↔Emission 混合，不透明度由 Generated 坐标渐隐，不读顶点色。

    fade='z'      底部浓、顶部淡（青烟 / 竖直雾幕）
    fade='radial' 中心浓、边缘淡（水平贴地雾，消掉矩形边）
    """
    m, n, out = _new(name)
    tc = n.nodes.new("ShaderNodeTexCoord")
    trans = n.nodes.new("ShaderNodeBsdfTransparent")
    emis = n.nodes.new("ShaderNodeEmission")
    emis.inputs["Color"].default_value = (*col, 1.0)
    emis.inputs["Strength"].default_value = strength
    mix = n.nodes.new("ShaderNodeMixShader")
    if fade == "z":
        sep = n.nodes.new("ShaderNodeSeparateXYZ")
        inv = n.nodes.new("ShaderNodeMath")
        inv.operation = "SUBTRACT"
        inv.inputs[0].default_value = 1.0
        amp = n.nodes.new("ShaderNodeMath")
        amp.operation = "MULTIPLY"
        amp.inputs[1].default_value = base
        n.links.new(tc.outputs["Generated"], sep.inputs["Vector"])
        n.links.new(sep.outputs["Z"], inv.inputs[1])
        n.links.new(inv.outputs[0], amp.inputs[0])
        n.links.new(amp.outputs[0], mix.inputs[0])
    else:
        sub = n.nodes.new("ShaderNodeVectorMath")
        sub.operation = "SUBTRACT"
        sub.inputs[1].default_value = (0.5, 0.5, 0.0)
        ln = n.nodes.new("ShaderNodeVectorMath")
        ln.operation = "LENGTH"
        mr = n.nodes.new("ShaderNodeMapRange")
        mr.clamp = True
        mr.inputs["From Min"].default_value = 0.0
        mr.inputs["From Max"].default_value = 0.62
        mr.inputs["To Min"].default_value = base
        mr.inputs["To Max"].default_value = 0.0
        n.links.new(tc.outputs["Generated"], sub.inputs[0])
        n.links.new(sub.outputs["Vector"], ln.inputs[0])
        n.links.new(ln.outputs["Value"], mr.inputs["Value"])
        n.links.new(mr.outputs["Result"], mix.inputs[0])
    n.links.new(trans.outputs[0], mix.inputs[1])
    n.links.new(emis.outputs[0], mix.inputs[2])
    n.links.new(mix.outputs[0], out.inputs["Surface"])
    m.use_backface_culling = False
    _blended(m)
    return m


def mat_star():
    """星点：固定冷白 Emission，不受夜景灯光影响；亮度层次由泛光阈值给出。"""
    m, n, out = _new("D_Star_夜空星点")
    e = n.nodes.new("ShaderNodeEmission")
    e.inputs["Color"].default_value = (0.34, 0.39, 0.50, 1.0)
    e.inputs["Strength"].default_value = 0.70
    n.links.new(e.outputs["Emission"], out.inputs["Surface"])
    m.use_backface_culling = False
    return m


def srgb(h):
    h = h.lstrip("#")
    v = [int(h[i:i + 2], 16) / 255.0 for i in (0, 2, 4)]
    return tuple(c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4
                 for c in v)


# ────────────────────────────── A 铺装 ───────────────────────────────────
def build_paving(slab, litter, wet, coll):
    """逐块实体石板；板缝露出底下较暗的 S_Paving，天然形成勾缝。"""
    regions = [
        (-25.0, 25.0, -43.0, 60.0, 1.30),   # 院内（主要可视区）
        (-31.0, 31.0, 61.0, 78.0, 1.45),   # 山门前广场
    ]
    count = 0
    for x0, x1, y0, y1, step in regions:
        rows = int((y1 - y0) / step)
        for r in range(rows):
            y = y0 + r * step
            shift = 0.5 * step if r % 2 else 0.0        # 错缝
            x = x0 - step + shift
            while x < x1:
                # 中轴御路已有 S_Stone 条石，跳过；塔基八角散水会被塔座盖住，照铺无妨
                if abs((x + step * 0.5)) > 2.95:
                    g = 0.038                              # 板缝 3.8 cm
                    ax, bx = x + g, x + step - g
                    ay, by = y + g, y + step - g
                    z = -0.010 + RNG.uniform(-0.009, 0.009)  # 微起伏
                    t = RNG.random()
                    # 青灰为主，少量偏暖 / 偏冷，模拟不同年代补配的石板
                    # 夜景里石板必须压得住：32 盏灯 + exposure 1.25 会把
                    # 浅色漫反射直接推到过曝白。目标是「深青石，局部被暖光点亮」。
                    if t < 0.12:
                        base = (0.070, 0.063, 0.055)
                    elif t < 0.28:
                        base = (0.056, 0.060, 0.064)
                    else:
                        k = RNG.uniform(0.055, 0.088)
                        base = (k, k * 0.965, k * 0.905)
                    # 四角轻微深浅差，打破纯色块
                    d = RNG.uniform(0.93, 1.07)
                    c0 = tuple(min(1.0, v * d) for v in base)
                    c1 = tuple(min(1.0, v * d * RNG.uniform(0.96, 1.04)) for v in base)
                    slab.quad((ax, ay, z), (bx, ay, z), (bx, by, z), (ax, by, z),
                              c0, c1, c0, c1)
                    count += 1
                x += step

    # 湿痕：灯笼 / 香炉 / 石灯附近的不规则低粗糙度水迹，负责接住暖光反射
    wet_spots = []
    for _ in range(70):
        cx = RNG.uniform(-21.0, 21.0)
        cy = RNG.uniform(-40.0, 58.0)
        wet_spots.append((cx, cy, RNG.uniform(0.45, 1.45), RNG.uniform(0.30, 0.85)))
    for cx, cy, rx, ry in wet_spots:
        pts = []
        for k in range(9):
            th = k * TAU / 9
            j = RNG.uniform(0.82, 1.14)
            pts.append((cx + rx * j * math.cos(th), cy + ry * j * math.sin(th),
                        0.008))
        wet.ngon(pts, (0.030, 0.032, 0.034))

    # 落叶 / 苔痕 / 碎草：压在墙根、树坑、石板缝上，破掉铺地的机械感
    trees = [(14.6, 65.5), (-15.2, 66.2), (20.6, -7.4), (-15.6, -13.0),
             (-13.6, 48.0), (13.6, 52.5), (-16.5, -38.0), (22.8, 10.5),
             (-18.6, 3.0), (21.6, 24.0)]
    spots = []
    for tx, ty in trees:
        for _ in range(34):
            th = RNG.uniform(0, TAU)
            rr = RNG.uniform(1.2, 5.4)
            spots.append((tx + rr * math.cos(th), ty + rr * math.sin(th)))
    for _ in range(230):
        sx = -1 if RNG.random() < 0.5 else 1
        spots.append((sx * RNG.uniform(22.0, 25.6), RNG.uniform(-42.0, 58.0)))
    for _ in range(190):
        spots.append((RNG.uniform(-23.0, 23.0), RNG.uniform(-42.0, 58.0)))
    palette = [(0.20, 0.105, 0.045), (0.26, 0.145, 0.055),
               (0.145, 0.155, 0.070), (0.205, 0.175, 0.100),
               (0.115, 0.135, 0.065)]
    for x, y in spots:
        s = RNG.uniform(0.09, 0.24)
        rot = RNG.uniform(0, TAU)
        col = palette[RNG.randrange(len(palette))]
        z = 0.014 + RNG.uniform(0, 0.006)
        p = [(x + s * math.cos(rot + k * 2.1), y + s * math.sin(rot + k * 2.1),
              z + (0.012 if k == 0 else 0.0)) for k in range(3)]
        litter.tri(*p, col)
    return count


# ────────────────────────────── B 水石 ───────────────────────────────────
def build_water(water, glow, coll):
    y0, y1 = 68.05, 71.95
    # 水面略高于原有 S_Dark 面片（-1.05），分 14 段做轻微波纹起伏
    for i in range(14):
        ax = -30.8 + 61.6 * i / 14
        bx = -30.8 + 61.6 * (i + 1) / 14
        za = -1.015 + 0.012 * math.sin(i * 1.7)
        zb = -1.015 + 0.012 * math.sin((i + 1) * 1.7)
        water.quad((ax, y0, za), (bx, y0, zb), (bx, y1, zb), (ax, y1, za),
                   (0.02, 0.03, 0.035))
    # 灯笼在渠面的暖色倒影：细长、断续、低强度
    for i in range(26):
        x = RNG.uniform(-26.0, 26.0)
        y = RNG.uniform(y0 + 0.2, y1 - 0.2)
        ln = RNG.uniform(0.30, 1.15)
        w = RNG.uniform(0.035, 0.10)
        glow.quad((x - w, y, -0.998), (x + w, y, -0.998),
                  (x + w * 0.6, y + ln, -0.998), (x - w * 0.6, y + ln, -0.998),
                  (0.30, 0.135, 0.045))


# ────────────────────────────── C 灯火 ───────────────────────────────────
def _window(b, x, y, z, w, h, axis, col):
    """axis='x' 面朝 ±x，axis='y' 面朝 ±y；窗光做成极薄的发光片。"""
    hw, hh = w * 0.5, h * 0.5
    if axis == "y":
        b.quad((x - hw, y, z - hh), (x + hw, y, z - hh),
               (x + hw, y, z + hh), (x - hw, y, z + hh), col)
    else:
        b.quad((x, y - hw, z - hh), (x, y + hw, z - hh),
               (x, y + hw, z + hh), (x, y - hw, z + hh), col)


def build_windows(b, coll):
    warm = [(0.95, 0.52, 0.18), (1.0, 0.62, 0.26), (0.86, 0.42, 0.14)]
    # 院内殿宇：山门 / 东西厢房 / 重门 / 后殿，窗格朝相机可见的两侧
    halls = [
        (0.0, 60.0, 3.9, 13.2, "y", [-4.6, -3.1, 3.1, 4.6]),
        (0.0, 37.0, 3.6, 11.4, "y", [-3.9, -2.4, 2.4, 3.9]),
        (0.0, -30.0, 4.2, 19.6, "y", [-7.2, -5.4, -2.0, 2.0, 5.4, 7.2]),
    ]
    for cx, cy, cz, _w, axis, offs in halls:
        for off in offs:
            c = warm[RNG.randrange(3)]
            _window(b, cx + off, cy + 3.92, cz, 0.62, 0.86, axis, c)
    for sx in (-1, 1):
        for off in (-3.9, -2.3, 2.3, 3.9):
            c = warm[RNG.randrange(3)]
            _window(b, sx * 19.2, 48.4 + off, 2.9, 0.58, 0.78, "x", c)

    # 古城民居：按 build_site.py 的街坊网格撒窗光，夜景里形成远处灯火层
    for side in (-1, 1):
        for col_i in range(3):
            cx = side * (43.0 + col_i * 23.0)
            for row in range(3):
                cy = -62.0 + row * 52.0
                for k in range(RNG.randint(2, 4)):
                    c = warm[RNG.randrange(3)]
                    ox = RNG.uniform(-7.0, 7.0)
                    oz = RNG.uniform(1.4, 3.1)
                    if RNG.random() < 0.5:
                        _window(b, cx + ox, cy + 9.6, oz, 0.55, 0.68, "y", c)
                    else:
                        _window(b, cx + side * 8.6, cy + ox, oz,
                                0.55, 0.68, "x", c)


# ────────────────────────────── D 大气 ───────────────────────────────────
def build_smoke(b, coll):
    """塔前香炉 (0, 15.4) 三缕青烟，面片朝相机，上宽下窄、渐隐。"""
    dx, dy = CAM_XY[0] - 0.0, CAM_XY[1] - 15.4
    L = math.hypot(dx, dy)
    px, py = -dy / L, dx / L                 # 带宽方向（垂直于视线）
    for s in range(3):
        ox = (s - 1) * 0.34
        rows = []
        for k in range(11):
            t = k / 10.0
            z = 1.75 + t * 9.2
            drift = math.sin(t * 4.2 + s * 1.7) * 0.62 * t + ox * (1 - t * 0.4)
            w = 0.22 + t * 1.30
            cx, cy = drift * px, 15.4 + drift * py
            dens = max(0.0, (0.13 * (1.0 - t) ** 1.20 + 0.008)
                       * (0.75 + 0.25 * math.sin(t * 9 + s)))
            col = (dens, dens * 0.94, dens * 0.86)
            rows.append((((cx - w * px), (cy - w * py), z, col),
                         ((cx + w * px), (cy + w * py), z, col)))
        for k in range(10):
            lo_l, lo_r = rows[k]
            up_l, up_r = rows[k + 1]
            b.quad(lo_l[:3], lo_r[:3], up_r[:3], up_l[:3],
                   lo_l[3], lo_r[3], up_r[3], up_l[3])


def build_ground_haze(b, coll):
    """院内贴地薄雾：5×9 网格，边缘顶点密度为 0，避免看见矩形边。"""
    nx, ny = 5, 9
    x0, x1, y0, y1 = -38.0, 38.0, -52.0, 72.0
    z = 0.42
    grid = []
    for j in range(ny + 1):
        row = []
        fy = j / ny
        for i in range(nx + 1):
            fx = i / nx
            edge = min(fx, 1 - fx, fy, 1 - fy)
            fade = min(1.0, edge / 0.28)
            d = 0.085 * fade * (0.72 + 0.28 * math.sin(fx * 7 + fy * 5))
            row.append(((x0 + (x1 - x0) * fx, y0 + (y1 - y0) * fy, z),
                        (d, d * 0.87, d * 0.72)))
        grid.append(row)
    for j in range(ny):
        for i in range(nx):
            p0, c0 = grid[j][i]
            p1, c1 = grid[j][i + 1]
            p2, c2 = grid[j + 1][i + 1]
            p3, c3 = grid[j + 1][i]
            b.quad(p0, p1, p2, p3, c0, c1, c2, c3)


def build_distance_haze(b, coll):
    """远景大气透视：只在地平线附近立一道极淡的竖直雾幕。

    第一版曾铺成覆盖 ±400 m 的水平大平面，结果从俯视机位看过去
    整片地面被染成橙色，还把硬地平线抬成一条黑斜线——水平雾在
    鸟瞰里会被看成「地面本身」。改成竖直窄带，只负责让远处民居
    与天空暖带之间有一层过渡，融合主要交给 S_Paving 的远端 emission。
    """
    y = -168.0
    x0, x1 = -300.0, 300.0
    zs = [-0.4, 1.2, 3.5, 7.0, 12.0, 19.0, 28.0]
    dens = [0.105, 0.095, 0.072, 0.045, 0.020, 0.006, 0.0]
    cols = len(xs := [x0 + (x1 - x0) * i / 14 for i in range(15)])
    for k in range(len(zs) - 1):
        d0, d1 = dens[k], dens[k + 1]
        for i in range(cols - 1):
            # 横向也渐隐，避免雾幕两端出现竖直切口
            f0 = min(1.0, min(i, (cols - 1) - i) / 3.0)
            f1 = min(1.0, min(i + 1, (cols - 1) - (i + 1)) / 3.0)
            c0 = (d0 * f0, d0 * f0 * 0.80, d0 * f0 * 0.62)
            c1 = (d0 * f1, d0 * f1 * 0.80, d0 * f1 * 0.62)
            c2 = (d1 * f1, d1 * f1 * 0.80, d1 * f1 * 0.62)
            c3 = (d1 * f0, d1 * f0 * 0.80, d1 * f0 * 0.62)
            b.quad((xs[i], y, zs[k]), (xs[i + 1], y, zs[k]),
                   (xs[i + 1], y, zs[k + 1]), (xs[i], y, zs[k + 1]),
                   c0, c1, c2, c3)


# ────────────────────────────── E 收束 ───────────────────────────────────
def build_gravel(b, coll):
    """月台散水外缘与墙根的碎石，打散过于笔直的铺装边界。"""
    for _ in range(420):
        th = RNG.uniform(0, TAU)
        r = RNG.uniform(12.8, 15.2)
        x, y = r * math.cos(th), r * math.sin(th)
        s = RNG.uniform(0.055, 0.16)
        k = RNG.uniform(0.17, 0.29)
        z = 0.012
        b.tri((x - s, y - s * 0.6, z), (x + s, y - s * 0.3, z),
              (x, y + s, z + 0.02), (k, k * 0.95, k * 0.85))


# ────────────────────────────── F 夜空 ───────────────────────────────────
def build_stars(b, coll):
    """World 里用 Voronoi 取星点在 EEVEE 下不稳定；改成半径 720 m 的
    实体发光小面片，朝向场景原点，只有上半球、避开地平线暖带。"""
    R = 720.0
    rng = random.Random(8811)
    up = Vector((0, 0, 1))
    placed = 0
    tries = 0
    while placed < 300 and tries < 5000:
        tries += 1
        z = rng.uniform(0.20, 1.0)
        th = rng.uniform(0, TAU)
        r = math.sqrt(max(0.0, 1.0 - z * z))
        p = Vector((R * r * math.cos(th), R * r * math.sin(th), R * z))
        n = -p.normalized()
        t1 = n.cross(up)
        if t1.length < 1e-4:
            t1 = n.cross(Vector((1, 0, 0)))
        t1.normalize()
        t2 = n.cross(t1).normalized()
        s = rng.uniform(0.55, 1.45)
        lum = rng.uniform(0.22, 0.80)
        c = (lum * 0.78, lum * 0.85, lum)
        b.quad(p - t1 * s - t2 * s, p + t1 * s - t2 * s,
               p + t1 * s + t2 * s, p - t1 * s + t2 * s, c)
        placed += 1


# ────────────────────────────── 入口 ─────────────────────────────────────
def build(coll, here=None):
    """在 coll 中生成全部周边细节，返回统计字典。"""
    slab = Mesh()
    litter = Mesh()
    wet = Mesh()
    water = Mesh()
    glow = Mesh()
    windows = Mesh()
    smoke = Mesh()
    haze = Mesh()
    gravel = Mesh()
    stars = Mesh()

    n_slab = build_paving(slab, litter, wet, coll)
    build_water(water, glow, coll)
    build_windows(windows, coll)
    build_smoke(smoke, coll)
    build_ground_haze(haze, coll)
    # 远景竖直雾幕默认停用：S_Paving 的远端 emission 已经把地面与天空
    # 暖带融合好了，雾幕在鸟瞰里反而会露出横向边界的矩形硬边。
    # 需要更强的远景大气时再解除注释，并同步给它加横向渐隐。
    # build_distance_haze(mist, coll)
    build_gravel(gravel, coll)
    build_stars(stars, coll)

    groups = [
        ("D_01 青石板铺装", slab, mat_slab()),
        ("D_02 落叶苔痕", litter, mat_flat(
            "D_Litter_落叶苔痕", 0.92, (0.05, 0.03, 0.01),
            palette=[(0.052, 0.026, 0.010), (0.074, 0.042, 0.016),
                     (0.028, 0.038, 0.016), (0.055, 0.046, 0.026),
                     (0.024, 0.030, 0.014)])),
        ("D_03 地面湿痕", wet, mat_flat(
            "D_Wet_湿痕", 0.13, (0.010, 0.011, 0.012), coat=0.55)),
        ("D_04 石渠水面", water, mat_water()),
        ("D_05 渠面暖光倒影", glow, mat_emission("D_Reflection_倒影",
                                                srgb("#c87432"), 0.85)),
        ("D_06 殿宇民居窗光", windows, mat_emission("D_Window_窗光",
                                                   srgb("#ffb45a"), 3.4)),
        ("D_07 香炉青烟", smoke, mat_haze(
            "D_Smoke_青烟", srgb("#6e6660"), 0.22, fade="z", base=0.065)),
        ("D_08 院内贴地雾", haze, mat_haze(
            "D_Mist_贴地雾", srgb("#9a7a58"), 0.35, fade="radial", base=0.060)),
        ("D_10 月台散水碎石", gravel, mat_flat(
            "D_Gravel_碎石", 0.95, (0.045, 0.042, 0.038))),
        ("D_11 夜空星点", stars, mat_star()),
    ]
    total = 0
    for name, mesh, mat in groups:
        ob = mesh.to_object(name, mat, coll)
        if ob:
            total += mesh.face_count()
    print("DETAIL_OK objects=", len(groups), "faces=", total, "slabs=", n_slab)
    return {"objects": len(groups), "faces": total, "slabs": n_slab}
