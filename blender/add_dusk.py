# -*- coding: utf-8 -*-
"""凌霄塔 · 蓝调黄昏主视觉（月夜母版之后的独立增量预设）

用法：
  blender -b model/lingxiao_tower_scene.blend --python model/add_dusk.py

产物：
  model/lingxiao_tower_scene_dusk.blend   ← 独立第三份场景，母版与雪景两份都不动
  model/_dusk_wide.png / _dusk_portrait.png  ← 60% 复核预览

设计判断
--------
对外展示要的是「看得见的形制」，月夜把斗拱出跳、斜昂、瓦作、砖木分界
全压进暗部，观众只记住气氛。蓝调黄昏保留东方夜色与暖窗灯火，但让
塔身结构读得出来。关键不是把整场提亮 —— 那会把塔糊成发光柱，而是
三件事分开做：

  1. 天空：从「近黑 + 一条暗橙带」拉成蓝调时刻的层次（天顶靛蓝 →
     中段蓝紫 → 地平线暖赭余晖），色阶拉开但不过曝；
  2. 环境：非相机射线的环境背景由暖棕转冷蓝灰，让阴影走冷、木构与
     砖构的色差能分开；
  3. 塔身：单独补一盏高位中性柔光 + 立面光去橙、环境天光略提，
     只照亮构件，不抬地面亮度。

配套：星点隐藏（蓝调时刻不该满天星）、泛光收敛（亮天空下 Glare 会把
暖带糊平）、Uplight 下调（黄昏不需要那么强的上射灯）、暖灯点略提
（冷调里反而更跳）。远景大铺地复用天空同一条渐变，避免地平线硬边。

主体几何、形制参数、贴图一律不动；全部改动收在集合「05 蓝调黄昏」，
新增对象整层可删，参数改动可通过重跑母版回退。
"""
import bpy
import os
from mathutils import Vector

HERE = os.path.dirname(bpy.data.filepath) or os.path.dirname(os.path.abspath(__file__))
DST = os.path.join(HERE, "lingxiao_tower_scene_dusk.blend")
sc = bpy.context.scene


def srgb(h):
    """#RRGGBB → linear RGB（节点需要线性值）。"""
    h = h.lstrip("#")
    v = [int(h[i:i + 2], 16) / 255.0 for i in (0, 2, 4)]
    return tuple(c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4 for c in v)


def rgba(h):
    return (*srgb(h), 1.0)


root = bpy.data.collections.get("凌霄塔 · 完整场景")
c_dusk = bpy.data.collections.new("05 蓝调黄昏（天空 / 环境 / 形制光 / 竖版机位）")
(root or sc.collection).children.link(c_dusk)


# ── 1. 天空：蓝调时刻的七段渐变 ───────────────────────────────────────
# Window.Y：0 = 画面底，1 = 画面顶。母版 0.62 是那条暖赭暮色带，
# 保留它的位置，只把色阶从「暗橙」提到「有存在感的余晖」，
# 其余各段由冷灰蓝渐次过渡到天顶靛蓝。
SKY = {
    0.000: "#171C2B",
    0.160: "#232A40",
    0.280: "#2E3449",
    0.520: "#3A3E5E",   # 暖带下缘，冷蓝紫（收紧暖色扩散）
    0.620: "#6B3E2C",   # 地平线赭红余晖：比首版降饱和、压暗，含蓄不艳
    0.700: "#2E3A60",   # 暖带上缘转冷蓝
    1.000: "#1B2745",   # 天顶深靛蓝
}

world_ramp = None
w = sc.world
if w and w.use_nodes:
    ramp = next((nd for nd in w.node_tree.nodes
                 if nd.type in ("VALTORGB", "VAL_TO_RGB")), None)
    if ramp:
        for e in ramp.color_ramp.elements:
            hit = min(SKY, key=lambda p: abs(p - e.position))
            if abs(hit - e.position) < 0.03:
                e.color = rgba(SKY[hit])
        world_ramp = ramp
        print("DUSK_OK sky_ramp=blue_hour stops=", len(SKY))

    # 非相机射线的环境背景：暖棕 → 冷蓝灰，给塔身一个冷色基底
    mixw = next((nd for nd in w.node_tree.nodes if nd.type == "MIX_SHADER"), None)
    if mixw:
        for idx in (1, 2):
            if mixw.inputs[idx].is_linked:
                bg = mixw.inputs[idx].links[0].from_node
                if bg.type == "BACKGROUND" and bg.name != "背景":
                    bg.inputs["Color"].default_value = rgba("#5C6A8A")
                    bg.inputs["Strength"].default_value = 1.15
                    print("DUSK_OK env_cold=", bg.name)
print("DUSK_OK world_done")


# ── 2. 远景大铺地复用天空渐变，地平线不切硬边 ────────────────────────
pm = bpy.data.materials.get("S_Paving_mat")
if pm and pm.use_nodes and world_ramp is not None:
    pn = pm.node_tree
    mixsh = next((nd for nd in pn.nodes if nd.type == "MIX_SHADER"), None)
    far = None
    if mixsh and mixsh.inputs[2].is_linked:
        nd = mixsh.inputs[2].links[0].from_node
        if nd.type == "EMISSION":
            far = nd
    if far:
        # 已存在 Window.Y → ColorRamp 链（R2 做法）则直接复用，否则新建
        gr = None
        if far.inputs["Color"].is_linked:
            src = far.inputs["Color"].links[0].from_node
            if src.type in ("VALTORGB", "VAL_TO_RGB"):
                gr = src
        if gr is None:
            tc = pn.nodes.new("ShaderNodeTexCoord")
            sep = pn.nodes.new("ShaderNodeSeparateXYZ")
            gr = pn.nodes.new("ShaderNodeValToRGB")
            tc.location, sep.location, gr.location = (-620, -900), (-400, -900), (-190, -900)
            pn.links.new(tc.outputs["Window"], sep.inputs["Vector"])
            pn.links.new(sep.outputs["Y"], gr.inputs["Fac"])
            pn.links.new(gr.outputs["Color"], far.inputs["Color"])
        src_els = sorted(list(world_ramp.color_ramp.elements), key=lambda e: e.position)
        cr = gr.color_ramp
        cr.interpolation = world_ramp.color_ramp.interpolation
        # 重建色标：先把已有两端对齐，补中间，再删多余
        while len(cr.elements) > 2:
            cr.elements.remove(cr.elements[-1])
        cr.elements[0].position = src_els[0].position
        cr.elements[0].color = tuple(src_els[0].color)
        cr.elements[1].position = src_els[-1].position
        cr.elements[1].color = tuple(src_els[-1].color)
        for e in src_els[1:-1]:
            ne = cr.elements.new(e.position)
            ne.color = tuple(e.color)
        print("DUSK_OK far_ground=sky_gradient stops=", len(src_els))
    # 淡出带推远一点，少抹掉被灯照亮的近景院落
    if mixsh and mixsh.inputs[0].is_linked:
        fade = mixsh.inputs[0].links[0].from_node
        if fade.type == "MAP_RANGE":
            fade.inputs["From Min"].default_value = 45.0
            fade.inputs["From Max"].default_value = 190.0


# ── 3. 灯光：环境转冷 + 立面单独提亮 + 暖点更跳 ──────────────────────
LIGHT_SPEC = {
    # 四盏立面光：去橙转中性暖白，略提能量，让木色／砖色／彩画各自分开
    "Facade_1": dict(energy=4200, color=(1.0, 0.72, 0.46)),
    "Facade_2": dict(energy=4200, color=(1.0, 0.72, 0.46)),
    "Facade_3": dict(energy=4200, color=(1.0, 0.72, 0.46)),
    "Facade_4": dict(energy=4200, color=(1.0, 0.72, 0.46)),
    # 天光：冷补光与环境都提一档，阴影走冷蓝，构件体积才立得住
    "Fill · 冷补光": dict(energy=1.30, color=(0.42, 0.55, 1.0)),
    "Hemi · 环境": dict(energy=1.10, color=(0.62, 0.72, 0.92)),
    # 主光／正面光略降并去饱和，避免亮天空下整体过曝
    "Key · 主光": dict(energy=2.20, color=(1.0, 0.86, 0.72)),
    "Front · 正面": dict(energy=1.30, color=(1.0, 0.80, 0.65)),
    # 逆光轮廓略提，给塔一个黄昏的镶边
    "Rim · 暖轮廓": dict(energy=1.60, color=(1.0, 0.42, 0.14)),
    "SideWarm": dict(energy=0.50, color=(1.0, 0.50, 0.24)),
    # 上射灯下调：月夜靠它撑塔，黄昏里会过曝
    "Uplight_1": dict(energy=3800),
    "Uplight_2": dict(energy=3800),
    "Uplight_3": dict(energy=3800),
    "Uplight_4": dict(energy=3800),
}
n_spec = 0
for name, kw in LIGHT_SPEC.items():
    o = bpy.data.objects.get(name)
    if not o or o.type != "LIGHT":
        continue
    for k, v in kw.items():
        setattr(o.data, k, v)
    n_spec += 1
print("DUSK_OK light_spec=", n_spec)

# 灯笼与暖窗点光统一提 25%：冷调里暖点才跳得出来
n_warm = 0
for o in bpy.data.objects:
    if o.type == "LIGHT" and o.name.startswith(("Lantern_", "WarmPoint_")):
        o.data.energy *= 1.25
        n_warm += 1
print("DUSK_OK warm_points=", n_warm)

# 新增一盏高位中性柔光：现有 Facade 全在 z=12，只照到塔下半段，
# 四层以上的斗拱／斜昂／瓦作仍沉在暗部。从相机前侧偏右打，出明暗面。
ld = bpy.data.lights.new("Dusk_Form_High", "AREA")
ld.energy = 14000.0
ld.color = (0.88, 0.92, 1.0)
ld.shape = "DISK"
ld.size = 24.0
lo = bpy.data.objects.new("Dusk_Form_High · 高位形制光", ld)
c_dusk.objects.link(lo)
lo.location = (34.0, 34.0, 32.0)
lo.rotation_euler = (Vector((0.0, 0.0, 25.0)) - lo.location).to_track_quat("-Z", "Y").to_euler()
print("DUSK_OK form_key=1")


# ── 4. 星点、泛光、曝光 ───────────────────────────────────────────────
stars = bpy.data.objects.get("D_11 夜空星点")
if stars:
    stars.hide_render = True
    stars.hide_viewport = True
    print("DUSK_OK stars_hidden=1（蓝调时刻不该满天星）")

# 左侧前景古槐是纯 Emission 剪影，亮天空下会显成高饱和绿贴纸；
# 只降发光强度，保留它作为深色压角的构图作用，不改颜色链路。
fg = bpy.data.materials.get("D_FG_Leaf_前景叶冠")
if fg and fg.use_nodes:
    n = 0
    for nd in fg.node_tree.nodes:
        if nd.type == "EMISSION":
            nd.inputs["Strength"].default_value *= 0.50
            n += 1
    print("DUSK_OK foreground_tree_dim=", n)

if sc.use_nodes:
    for nd in sc.node_tree.nodes:
        if nd.type == "GLARE":
            nd.inputs["Threshold"].default_value = 0.78
            nd.inputs["Strength"].default_value = 0.50
        elif nd.type in ("MIX_RGB", "MIX"):
            for sock in nd.inputs:
                if sock.name == "Fac" and not sock.is_linked:
                    sock.default_value = 0.45
    print("DUSK_OK glare_tamed=1")

# 天空提亮约 7 倍后，曝光要往下收，否则暖带与塔基都会过曝；
# 塔身亮度由灯负责，不靠曝光硬拉。
sc.view_settings.exposure = 0.95
print("DUSK_OK exposure=", sc.view_settings.exposure)


# ── 5. 竖版封面机位（2:3） ───────────────────────────────────────────
# 竖版 AUTO fit 下 sensor_width=36 对应较长边（高），lens 54 时垂直
# FOV ≈ 36.9°；距塔约 88 m 时垂直覆盖约 59 m，41 m 的塔占约 70%，
# 上方留约 20% 天空给标题落款。
cd = bpy.data.cameras.new("Cam_03 竖版封面")
cd.lens = 54.0
cd.sensor_fit = "AUTO"
cd.clip_end = 2000.0
co = bpy.data.objects.new("Cam_03 竖版封面", cd)
c_dusk.objects.link(co)
co.location = (44.0, 76.0, 18.0)
co.rotation_euler = (Vector((0.0, 0.0, 23.0)) - co.location).to_track_quat("-Z", "Y").to_euler()
print("DUSK_OK portrait_camera=1 lens=", cd.lens)


# ── 6. 保存（先存横版全分辨率设置） ──────────────────────────────────
try:
    bpy.ops.file.pack_all()
except Exception as exc:
    print("DUSK_PACK_WARN", exc)

bpy.ops.wm.save_as_mainfile(filepath=DST, compress=True)
print("DUSK_OK file=", DST)
print("DUSK_OK size_mb=", round(os.path.getsize(DST) / 1024.0 / 1024.0, 2))


# ── 7. 正式成片（不改已保存的 .blend 横版设置） ──────────────────────
SHOTS = os.path.normpath(os.path.join(HERE, "..", "shots"))
sc.frame_set(1)
sc.render.resolution_percentage = 100
try:
    sc.eevee.taa_render_samples = 96
except Exception:
    pass

renders = (
    ("Cam_01 全景", 1600, 1000, "20-dusk-full.png"),
    ("Cam_03 竖版封面", 1000, 1500, "21-dusk-portrait.png"),
)
for cam_name, rx, ry, out in renders:
    cam = bpy.data.objects.get(cam_name)
    if not cam:
        print("DUSK_RENDER_SKIP", cam_name)
        continue
    sc.camera = cam
    sc.render.resolution_x, sc.render.resolution_y = rx, ry
    sc.render.filepath = os.path.join(SHOTS, out)
    bpy.ops.render.render(write_still=True)
    print("DUSK_RENDER_DONE", sc.render.filepath)
print("DUSK_ALL_DONE")
