"""把塔体 v3 + 塔院 + 网页夜景氛围合并成一个独立 .blend。

用法：
  blender -b model/lingxiao_tower.blend --python model/build_scene.py

产物：model/lingxiao_tower_scene.blend（贴图已打包，可单文件搬走）
网页里的灯笼 / 灯光 / 渐变天空 / 泛光是前端加的，不在这两份 .blend 里，
本脚本按网页参数在 Blender 中重建；glTF(Y-up) → Blender(Z-up) 坐标反变换 G()。
"""
import bpy
import math
import os
import importlib.util
from mathutils import Vector

HERE = os.path.dirname(bpy.data.filepath)
SITE = os.path.join(HERE, "site.blend")
DST = os.path.join(HERE, "lingxiao_tower_scene.blend")
scene = bpy.context.scene


def G(x, h, z):
    """网页(glTF, Y-up)坐标 → Blender(Z-up)坐标。"""
    return (x, -z, h)


def srgb(h):
    """#RRGGBB → linear RGB 元组（Blender 节点/灯光需要线性值）。"""
    h = h.lstrip("#")
    v = [int(h[i:i + 2], 16) / 255.0 for i in (0, 2, 4)]
    return tuple(c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4 for c in v)


def rgba(h):
    return (*srgb(h), 1.0)


# ── 1. 集合结构 ───────────────────────────────────────────────────────
root = bpy.data.collections.new("凌霄塔 · 完整场景")
scene.collection.children.link(root)
c_tower = bpy.data.collections.new("01 塔体 v3")
c_site = bpy.data.collections.new("02 塔院")
c_detail = bpy.data.collections.new("02b 周边细节（铺装 / 器物 / 大气）")
c_fx = bpy.data.collections.new("03 夜景氛围（灯光 / 相机 / 灯笼）")
for c in (c_tower, c_site, c_detail, c_fx):
    root.children.link(c)

tower_objs = [o for o in bpy.data.objects if o.type == "MESH"]
for o in tower_objs:
    for old in list(o.users_collection):
        old.objects.unlink(o)
    c_tower.objects.link(o)
for c in list(bpy.data.collections):
    if c.name == "Collection" and not c.objects and not c.children:
        bpy.data.collections.remove(c)

# ── 2. 追加塔院（连材质、贴图一起带进来） ─────────────────────────────
with bpy.data.libraries.load(SITE, link=False) as (src, dst):
    names = [n for n in src.objects if n.startswith("S_")]
    dst.objects = names
site_objs = [o for o in dst.objects if o is not None]
for o in site_objs:
    c_site.objects.link(o)

# 修正同名贴图产生的 .001 副本，统一指回 tex 目录，随后打包
for img in bpy.data.images:
    if img.source != "FILE" or img.packed_file:
        continue
    base = os.path.basename(bpy.path.abspath(img.filepath).replace("\\", "/"))
    target = os.path.join(HERE, "tex", base)
    if os.path.exists(target):
        img.filepath = os.path.join("//tex", base)

# ── 2b. 周边细节层（纯增量几何，不修改塔体与 site.blend 源网格） ──────
_spec = importlib.util.spec_from_file_location(
    "site_detail", os.path.join(HERE, "site_detail.py"))
_sd = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_sd)
detail_stats = _sd.build(c_detail, HERE)

# ── 2c. 树冠细化（周边细节第二轮） ────────────────────────────────────
# 从 S_Leaf 的球簇连通分量反推枝端，按原骨架重做四层冠形。
# 旧叶球只在这份合并场景里隐藏，site.blend 源文件与塔体均不改动；
# 想对比/回退，在 Outliner 里取消 S_Leaf 的隐藏、隐藏 D_12~D_15 即可。
_spec_f = importlib.util.spec_from_file_location(
    "site_foliage", os.path.join(HERE, "site_foliage.py"))
_sf = importlib.util.module_from_spec(_spec_f)
_spec_f.loader.exec_module(_sf)
foliage_stats = _sf.build(c_detail, leaf_obj=bpy.data.objects.get("S_Leaf"))
_leaf_old = bpy.data.objects.get("S_Leaf")
if _leaf_old and foliage_stats.get("clusters", 0):
    _leaf_old.hide_render = True
    _leaf_old.hide_viewport = True

# ── 2d. 近景压角（周边细节第三轮） ────────────────────────────────────
# 不做贴镜头的悬空树枝：Cam_01 俯角仅 ~7°，画面上缘对应 z≈32 m 高空，
# 画外枝在 Cam_02 会变成飘浮物。改为两处真实落地的竖向实体——院外巷道
# 24 m 古槐 + 靠西墙 8 m 石经幢组，双机位屏幕投影都已反算过，不遮塔。
_spec_g = importlib.util.spec_from_file_location(
    "site_foreground", os.path.join(HERE, "site_foreground.py"))
_sg = importlib.util.module_from_spec(_spec_g)
_spec_g.loader.exec_module(_sg)
foreground_stats = _sg.build(c_detail)

# ── 3. 天空：网页 makeBackground() 的纵向渐变 ────────────────────────
world = scene.world or bpy.data.worlds.new("夜景穹顶")
scene.world = world
world.use_nodes = True
nt = world.node_tree
nt.nodes.clear()
out = nt.nodes.new("ShaderNodeOutputWorld")
bg = nt.nodes.new("ShaderNodeBackground")
tc = nt.nodes.new("ShaderNodeTexCoord")
sep = nt.nodes.new("ShaderNodeSeparateXYZ")
ramp = nt.nodes.new("ShaderNodeValToRGB")
ramp.color_ramp.interpolation = "EASE"
# 网页 gradient 从上到下；Window.Y 从下到上，故顺序反转
STOPS = [
    (0.00, "#050507"), (0.16, "#150C08"), (0.28, "#1A100A"),
    (0.52, "#1A0E08"), (0.62, "#2E1A0E"), (0.70, "#100C12"),
    (1.00, "#050508"),
]
cr = ramp.color_ramp
cr.elements[0].position, cr.elements[0].color = STOPS[0][0], rgba(STOPS[0][1])
cr.elements[1].position, cr.elements[1].color = STOPS[-1][0], rgba(STOPS[-1][1])
for pos, col in STOPS[1:-1]:
    e = cr.elements.new(pos)
    e.color = rgba(col)
bg.inputs["Strength"].default_value = 1.0
nt.links.new(tc.outputs["Window"], sep.inputs["Vector"])
nt.links.new(sep.outputs["Y"], ramp.inputs["Fac"])

# 星点改为实体发光面片（见 site_detail.build_stars）：World 里的
# Voronoi 取点在 EEVEE 下不稳定，且无法控制亮度与分布。
nt.links.new(ramp.outputs["Color"], bg.inputs["Color"])

# 相机射线走渐变天空；其余射线走一层弱暖环境光，
# 顶替网页的 RoomEnvironment IBL，让夜景里的塔身与屋面不至于塌成黑块。
lp = nt.nodes.new("ShaderNodeLightPath")
bg_env = nt.nodes.new("ShaderNodeBackground")
bg_env.inputs["Color"].default_value = rgba("#3A2C22")
bg_env.inputs["Strength"].default_value = 0.90
mixw = nt.nodes.new("ShaderNodeMixShader")
nt.links.new(lp.outputs["Is Camera Ray"], mixw.inputs[0])
nt.links.new(bg_env.outputs["Background"], mixw.inputs[1])
nt.links.new(bg.outputs["Background"], mixw.inputs[2])
nt.links.new(mixw.outputs[0], out.inputs["Surface"])

# ── 4. 灯光：按网页参数重建，强度保留相对比例 ────────────────────────
def light_obj(name, kind, col, energy, glpos, gltarget=(0, 0, 0)):
    d = bpy.data.lights.new(name, kind)
    d.energy = energy
    d.color = srgb(col)
    o = bpy.data.objects.new(name, d)
    c_fx.objects.link(o)
    o.location = G(*glpos)
    o.rotation_euler = (Vector(G(*gltarget)) - o.location).to_track_quat("-Z", "Y").to_euler()
    return o


# 方向光（网页 DirectionalLight，默认照向原点）
light_obj("Key · 主光", "SUN", "#ffe6c8", 2.80, (54, 126, -46))
light_obj("Fill · 冷补光", "SUN", "#8CA4FF", 0.82, (-78, 34, 52))
light_obj("Rim · 暖轮廓", "SUN", "#ffa24e", 1.20, (-18, 48, 94))
light_obj("Front · 正面", "SUN", "#ffd9b8", 1.50, (34, 22, -72))
light_obj("SideWarm", "SUN", "#ffb072", 0.36, (-62, 34, -40))
# 网页 HemisphereLight → 一盏很弱的冷色顶光近似
light_obj("Hemi · 环境", "SUN", "#A8BCDE", 0.42, (12, 90, 18))

K = 12.0   # 网页 candela → Blender 瓦特的近似系数
for i, (x, h, z, inten, dist) in enumerate([
    (0, 3.4, -8, 132, 74),
    (0, 5.2, -60, 40, 34), (0, 4.8, -37, 40, 34),
    (5.0, 3.4, -20, 40, 34), (-5.0, 3.4, -20, 40, 34), (0, 5.4, 30, 40, 34),
    (0, 13, -34, 205, 56), (0, 11, 22, 170, 56),
    (-16, 9, 6, 130, 56), (16, 9, 6, 130, 56),
], 1):
    o = light_obj(f"WarmPoint_{i:02d}", "POINT", "#ffa656" if i <= 6 else "#ffb478",
                  inten * K, (x, h, z))
    o.data.shadow_soft_size = 1.2
    o.data.use_shadow = (i <= 2)

# 塔基四角上射投光灯
for i, (x, z) in enumerate([(8.4, 8.4), (-8.4, 8.4), (10.6, -10.6), (-10.6, -10.6)], 1):
    o = light_obj(f"Uplight_{i}", "SPOT", "#ffcf9e", 470 * K, (x, 1.6, z), (0, 25, 0))
    o.data.spot_size = 0.96
    o.data.spot_blend = 0.90
    o.data.shadow_soft_size = 0.8

# 塔身立面亮化：四面斜上柔光，做出自下而上的暖金渐变。
# 用有方向、有衰减的 AREA 光而非统一自发光，才不会把砖木抹成发光柱。
for i, (x, y) in enumerate([(20, 20), (-20, 20), (20, -20), (-20, -20)], 1):
    d = bpy.data.lights.new(f"Facade_{i}", "AREA")
    d.energy = 3200
    d.color = srgb("#ffc98a")
    d.shape = "DISK"
    d.size = 14
    o = bpy.data.objects.new(f"Facade_{i}", d)
    c_fx.objects.link(o)
    o.location = (x, y, 12.0)
    o.rotation_euler = (Vector((0, 0, 24)) - o.location).to_track_quat("-Z", "Y").to_euler()

# ── 5. 灯笼：网页里是前端生成的几何，模型文件里没有，这里重建 ───────
def emission_mat(name, col, strength):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    n = m.node_tree
    n.nodes.clear()
    e = n.nodes.new("ShaderNodeEmission")
    e.inputs["Color"].default_value = rgba(col)
    e.inputs["Strength"].default_value = strength
    o = n.nodes.new("ShaderNodeOutputMaterial")
    n.links.new(e.outputs["Emission"], o.inputs["Surface"])
    return m


mat_lit = emission_mat("Lantern_Lit", "#ffb267", 5.0)
mat_cap = emission_mat("Lantern_Cap", "#8a3512", 0.9)

LANTERNS = [
    (-4.4, 4.9, -63.4), (4.4, 4.9, -63.4),
    (-3.7, 4.5, -40.2), (3.7, 4.5, -40.2),
    (-6.7, 5.4, 24.3), (6.7, 5.4, 24.3),
    (-6.2, 3.5, -14.4), (6.2, 3.5, -14.4),
]
for i, gp in enumerate(LANTERNS, 1):
    x, y, z = G(*gp)
    bpy.ops.mesh.primitive_uv_sphere_add(segments=10, ring_count=8, radius=0.17,
                                         location=(x, y, z))
    body = bpy.context.object
    body.name = f"Lantern_{i:02d}_Body"
    body.scale.z = 1.28
    body.data.materials.append(mat_lit)
    for j, dz in enumerate((0.24, -0.24), 1):
        bpy.ops.mesh.primitive_cylinder_add(vertices=6, radius=0.055, depth=0.05,
                                            location=(x, y, z + dz))
        cap = bpy.context.object
        cap.name = f"Lantern_{i:02d}_Cap{j}"
        cap.data.materials.append(mat_cap)
    bpy.ops.mesh.primitive_cylinder_add(vertices=4, radius=0.012, depth=0.42,
                                        location=(x, y, z + 0.48))
    cord = bpy.context.object
    cord.name = f"Lantern_{i:02d}_Cord"
    cord.data.materials.append(mat_cap)
    lp = light_obj(f"Lantern_{i:02d}_Glow", "POINT", "#ff9a4a", 30 * K, gp)
    lp.data.shadow_soft_size = 0.5
    lp.data.use_shadow = False

for o in bpy.data.objects:
    if o.name.startswith("Lantern_"):
        for old in list(o.users_collection):
            old.objects.unlink(o)
        c_fx.objects.link(o)

# ── 5.5 材质对齐：补网页的自发光，并让远端铺地淡出到背景 ────────────
def principled(mat_name):
    m = bpy.data.materials.get(mat_name)
    if not m or not m.use_nodes:
        return None
    return next((n for n in m.node_tree.nodes if n.type == "BSDF_PRINCIPLED"), None)


def add_emission(mat_name, col, strength):
    b = principled(mat_name)
    if not b:
        return
    try:
        b.inputs["Emission Color"].default_value = rgba(col)
        b.inputs["Emission Strength"].default_value = strength
    except Exception:
        pass


# 网页 prepModel 里金刹 0.12 / 树叶 0.30 的自发光
for nm in ("Finial_Gold_mat", "S_Gold_mat"):
    add_emission(nm, "#8a6218", 0.12)
add_emission("S_Leaf_mat", "#24300f", 0.30)

# 院落屋面原本是「贴图 + 纯漫反射」的平板，夜景里读不出瓦垄。
# 用对象空间（米）的细密条带做凹凸，配合略降的粗糙度接住暖光，
# 让大殿与民居屋顶有瓦作方向感，而不是一整片灰白。
rm = bpy.data.materials.get("S_Roof_mat")
if rm and rm.use_nodes:
    rn = rm.node_tree
    rbsdf = next(n for n in rn.nodes if n.type == "BSDF_PRINCIPLED")
    rtc = rn.nodes.new("ShaderNodeTexCoord")
    wave = rn.nodes.new("ShaderNodeTexWave")
    wave.wave_type = "BANDS"
    wave.bands_direction = "X"
    wave.inputs["Scale"].default_value = 2.4     # 约 0.42 m 一道瓦垄
    wave.inputs["Distortion"].default_value = 0.85
    wave.inputs["Detail"].default_value = 1.5
    rbump = rn.nodes.new("ShaderNodeBump")
    rbump.inputs["Strength"].default_value = 0.13
    rbump.inputs["Distance"].default_value = 0.045
    rn.links.new(rtc.outputs["Object"], wave.inputs["Vector"])
    rn.links.new(wave.outputs["Color"], rbump.inputs["Height"])
    rn.links.new(rbump.outputs["Normal"], rbsdf.inputs["Normal"])
    rbsdf.inputs["Roughness"].default_value = 0.70
    print("ROOF_GRAIN_OK")

# 主要提亮交给方向光（保留法线明暗）；自发光只留极淡一层兜底，
# 给太多会把砖木抹成一根没有层次的发光柱。
TOWER_MATS = [
    "Base_Stone_mat", "Bells_Metal_mat", "Body_Lower_mat", "Body_Upper_mat",
    "Body_Wood_Railing_mat", "Dougong_Brick_mat", "Dougong_Wood_mat",
    "Eave_Lower_mat", "Eave_Upper_mat", "Openings_mat",
]
for nm in TOWER_MATS:
    add_emission(nm, "#7a5622", 0.025 if nm.startswith("Eave_") else 0.04)

# 800 m 大铺地：压暗 + 随距原点距离淡出到近黑，
# 消掉「亮地面 / 黑天空」之间那条硬地平线，同时保住院内的铺装纹理。
pm = bpy.data.materials.get("S_Paving_mat")
if pm and pm.use_nodes:
    pn = pm.node_tree
    bsdf = next(n for n in pn.nodes if n.type == "BSDF_PRINCIPLED")
    mout = next(n for n in pn.nodes if n.type == "OUTPUT_MATERIAL")
    img = next((n for n in pn.nodes if n.type == "TEX_IMAGE"), None)
    if img:
        mul = pn.nodes.new("ShaderNodeMixRGB")
        mul.blend_type = "MULTIPLY"
        mul.inputs[0].default_value = 1.0
        mul.inputs[2].default_value = (0.30, 0.26, 0.23, 1.0)
        pn.links.new(img.outputs["Color"], mul.inputs[1])
        pn.links.new(mul.outputs["Color"], bsdf.inputs["Base Color"])
        # 远景（未被实体石板覆盖的区域）靠这层凹凸读出铺装纹理，
        # 否则 25 m 之外仍是一整片无质感的灰褐。
        pbump = pn.nodes.new("ShaderNodeBump")
        pbump.inputs["Strength"].default_value = 0.18
        pbump.inputs["Distance"].default_value = 0.035
        pn.links.new(img.outputs["Color"], pbump.inputs["Height"])
        pn.links.new(pbump.outputs["Normal"], bsdf.inputs["Normal"])
        bsdf.inputs["Roughness"].default_value = 0.88
    geo = pn.nodes.new("ShaderNodeNewGeometry")
    vlen = pn.nodes.new("ShaderNodeVectorMath")
    vlen.operation = "LENGTH"
    mr = pn.nodes.new("ShaderNodeMapRange")
    mr.clamp = True
    mr.inputs["From Min"].default_value = 25.0
    mr.inputs["From Max"].default_value = 95.0
    mr.inputs["To Min"].default_value = 0.0
    mr.inputs["To Max"].default_value = 1.0
    # 远端用固定 emission 而非漫反射：不受 32 盏灯影响，颜色对齐天空暖赭带，
    # 地面与天空在地平线处自然衔接，不会出现「亮地面 / 纯黑天空」的硬线。
    dark = pn.nodes.new("ShaderNodeEmission")
    dark.inputs["Color"].default_value = rgba("#241307")
    dark.inputs["Strength"].default_value = 1.0
    mixsh = pn.nodes.new("ShaderNodeMixShader")
    pn.links.new(geo.outputs["Position"], vlen.inputs[0])
    pn.links.new(vlen.outputs["Value"], mr.inputs["Value"])
    pn.links.new(mr.outputs["Result"], mixsh.inputs[0])
    pn.links.new(bsdf.outputs["BSDF"], mixsh.inputs[1])
    pn.links.new(dark.outputs[0], mixsh.inputs[2])
    pn.links.new(mixsh.outputs[0], mout.inputs["Surface"])
    print("PAVING_FADE_OK")

# ── 6. 相机：网页「全景」与「塔院」两个机位 ──────────────────────────
def make_cam(name, glpos, gltarget, lens):
    d = bpy.data.cameras.new(name)
    o = bpy.data.objects.new(name, d)
    c_fx.objects.link(o)
    o.location = G(*glpos)
    o.rotation_euler = (Vector(G(*gltarget)) - o.location).to_track_quat("-Z", "Y").to_euler()
    d.lens = lens
    d.clip_end = 2000
    return o


cam_full = make_cam("Cam_01 全景", (47, 31, -72), (0, 20.5, -1), 33)
make_cam("Cam_02 塔院", (76, 50, -104), (0, 7, -17), 30)
scene.camera = cam_full

# ── 7. 渲染设置：贴近网页 ACES + exposure 1.56 + bloom ───────────────
try:
    scene.render.engine = "BLENDER_EEVEE_NEXT"
except Exception:
    try:
        scene.render.engine = "BLENDER_EEVEE"
    except Exception:
        pass
scene.render.resolution_x = 1600
scene.render.resolution_y = 1000
scene.render.resolution_percentage = 100
scene.render.image_settings.file_format = "PNG"
scene.render.film_transparent = False
try:
    scene.render.image_settings.color_mode = "RGB"
except Exception:
    pass
try:
    scene.view_settings.view_transform = "AgX"
    scene.view_settings.look = "AgX - Medium High Contrast"
except Exception:
    try:
        scene.view_settings.view_transform = "Filmic"
    except Exception:
        pass
scene.view_settings.exposure = 1.25
scene.view_settings.gamma = 1.0
try:
    scene.eevee.taa_render_samples = 96
except Exception:
    pass

# 泛光：EEVEE Next 无内置 bloom，用合成器 Fog Glow 近似 UnrealBloomPass
bloom_ok = False
try:
    scene.use_nodes = True
    cn = scene.node_tree
    cn.nodes.clear()
    rl = cn.nodes.new("CompositorNodeRLayers")
    gl = cn.nodes.new("CompositorNodeGlare")
    co = cn.nodes.new("CompositorNodeComposite")
    gl.glare_type = "FOG_GLOW"
    gl.quality = "HIGH"
    # 4.4 起 Glare 改用输入 socket 控制阈值/强度/尺寸，threshold 属性已废弃。
    gl.inputs["Threshold"].default_value = 0.55
    gl.inputs["Strength"].default_value = 0.80
    gl.inputs["Size"].default_value = 0.32
    gl.inputs["Smoothness"].default_value = 0.15
    cn.links.new(rl.outputs["Image"], gl.inputs["Image"])
    # mix 属性存盘后会被 Blender 重映射（-0.8 → -0.45），不可靠；
    # 改取纯光晕输出，用 ADD 手动叠回原图，强度由 fac 精确控制。
    add = cn.nodes.new("CompositorNodeMixRGB")
    add.blend_type = "ADD"
    add.inputs[0].default_value = 0.70
    cn.links.new(rl.outputs["Image"], add.inputs[1])
    cn.links.new(gl.outputs["Glare"], add.inputs[2])
    cn.links.new(add.outputs[0], co.inputs["Image"])
    bloom_ok = True
except Exception as exc:
    print("BLOOM_SKIP", exc)
    try:
        scene.use_nodes = False
    except Exception:
        pass

# ── 8. 打包全部贴图，保存单文件 ──────────────────────────────────────
try:
    bpy.ops.file.pack_all()
except Exception as exc:
    print("PACK_WARN", exc)

# 材质预览默认套 Blender 自带白昼 HDR（forest.exr），夜景模型会灰扑扑的。
# 打开两个开关，让视口直接用场景的世界与 28 盏灯，打开文件即是夜景氛围。
for sc in bpy.data.screens:
    for area in sc.areas:
        if area.type != "VIEW_3D":
            continue
        sp = area.spaces.active
        sp.clip_end = 2000
        sp.shading.type = "MATERIAL"
        sp.shading.use_scene_world = True
        sp.shading.use_scene_lights = True
        if sp.region_3d:
            sp.region_3d.view_perspective = "CAMERA"

bpy.ops.wm.save_as_mainfile(filepath=DST, compress=True)

meshes = [o for o in bpy.data.objects if o.type == "MESH"]
imgs = [i for i in bpy.data.images if i.source == "FILE"]
print("SCENE_OK file=", DST)
print("SCENE_OK size_mb=", round(os.path.getsize(DST) / 1024.0 / 1024.0, 2))
print("SCENE_OK tower=", len(tower_objs), "site=", len(site_objs),
      "meshes=", len(meshes), "faces=", sum(len(o.data.polygons) for o in meshes))
print("SCENE_OK lights=", len([o for o in bpy.data.objects if o.type == "LIGHT"]),
      "cams=", len([o for o in bpy.data.objects if o.type == "CAMERA"]),
      "lanterns=", len([o for o in bpy.data.objects if o.name.startswith("Lantern_")]))
print("SCENE_OK imgs=", len(imgs), "packed=", sum(bool(i.packed_file) for i in imgs))
print("SCENE_OK detail=", detail_stats)
print("SCENE_OK foliage=", foliage_stats)
print("SCENE_OK foreground=", foreground_stats)
print("SCENE_OK bloom=", bloom_ok, "engine=", scene.render.engine,
      "view=", scene.view_settings.view_transform)
