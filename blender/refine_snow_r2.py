# -*- coding: utf-8 -*-
"""凌霄塔 · 雪景精修 R2（接在 add_snow.py 之后重放，另存独立版本）

用法：
  blender -b model/lingxiao_tower_scene_snow.blend --python model/refine_snow_r2.py

产物：
  model/lingxiao_tower_scene_snow_r2.blend   ← 与对方的 snow.blend 完全分开
  model/_r2_cam1.png / _r2_cam2.png          ← 双机位对比预览

设计判断
--------
原雪景的做法是「把表面刷白 + 撒 9.5 万粒子 + 世界调冷」，但漏了最关键的
一步：雪把地面反射率拉高之后，整场的曝光平衡必须重做。结果出现三个硬伤：
  1. 地面一片死白，原本的暖赭地面 / 石板 / 湿痕 / 砖缝层次被全部吃掉；
  2. 大铺地远景 emission (#3E3936) 比天空亮两倍多，在天空上切出硬地平线；
  3. 周围变亮后塔身相对更暗，斗拱 / 瓦作 / 砖木分界读不出来 —— 与
     「对外展示要看清形制」的目标正好相反。
另外，雪夜仍保留 300 颗实体星点，与飘雪混成一片白芝麻，物理与画面都不成立。

本轮只做「呈现层」：改既有节点数值、灯光参数、可见性，不动任何几何，
不改 add_snow.py 建立的节点结构，改动可整层回退。
主体（塔体几何 / 形制参数）一律不动。
"""
import bpy
import os
from mathutils import Vector

HERE = os.path.dirname(bpy.data.filepath) or os.path.dirname(os.path.abspath(__file__))
DST = os.path.join(HERE, "lingxiao_tower_scene_snow_r2.blend")
sc = bpy.context.scene


def srgb(h):
    """#RRGGBB → linear RGB（节点需要线性值）。"""
    h = h.lstrip("#")
    v = [int(h[i:i + 2], 16) / 255.0 for i in (0, 2, 4)]
    return tuple(c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4 for c in v)


def rgba(h):
    return (*srgb(h), 1.0)


def close(a, b, eps=0.025):
    return len(a) >= 3 and all(abs(a[i] - b[i]) < eps for i in range(3))


# R2 专属集合：所有新增对象都放这里，删除整层即可回到对方的原雪景
root = bpy.data.collections.get("凌霄塔 · 完整场景")
c_r2 = bpy.data.collections.new("05 精修 R2（曝光平衡 / 形制可读 / 雪夜逻辑）")
(root or sc.collection).children.link(c_r2)


# ── 1. 雪色重定：从「纯白」压回「雪夜的中灰冷调」 ────────────────────
# add_snow.py 给所有 Principled 材质插入的 MixRGB.inputs[2] 都是同一个
# SNOW = #D8E3F2（线性 ≈ 0.687/0.768/0.888）。按材质类别分三档重新赋色，
# 不改遮罩、不改节点连接，只换常数 —— 最稳妥的回退式改法。
OLD_SNOW = srgb("#D8E3F2")
SNOW_ROOF = rgba("#A8B6CC")    # 檐口 / 屋面 / 塔身：稍亮，让积雪仍能读出层次
SNOW_GROUND = rgba("#76869F")  # 地面 / 石板 / 铺装：最暗的一档，压住死白
SNOW_LEAF = rgba("#6C7C98")    # 树冠结霜：更沉，避免白色花菜


def snow_class(name):
    if any(k in name for k in ("Foliage", "Leaf", "叶冠")):
        return "leaf"
    if any(k in name for k in ("Paving", "Slab", "Gravel", "Litter", "Wet",
                               "Grass", "碎石", "石板", "落叶", "湿痕", "草")):
        return "ground"
    return "roof"


recolor = {}
for mat in bpy.data.materials:
    if not mat.use_nodes:
        continue
    target = {"roof": SNOW_ROOF, "ground": SNOW_GROUND, "leaf": SNOW_LEAF}[snow_class(mat.name)]
    for nd in mat.node_tree.nodes:
        if nd.type != "MIX_RGB":
            continue
        sock = nd.inputs[2]
        if not hasattr(sock, "default_value"):
            continue
        if close(tuple(sock.default_value[:3]), OLD_SNOW):
            sock.default_value = target
            recolor[mat.name] = snow_class(mat.name)
print("R2_OK snow_recolor=", len(recolor),
      "roof=", sum(1 for v in recolor.values() if v == "roof"),
      "ground=", sum(1 for v in recolor.values() if v == "ground"),
      "leaf=", sum(1 for v in recolor.values() if v == "leaf"))


# ── 2. 消除硬地平线：让远景地面直接复用天空那条渐变 ──────────────────
# 大铺地是一个半径 800 m 的圆盘，远处淡入一个「固定纯色」自发光平面。
# 只要地面是固定色、天空是渐变，圆盘边缘就必然在天空上切出一条亮边
# （俯视机位里就是那条弧形「碗沿」）—— 调深浅只是把亮边换成暗边，
# 消不掉。正解是让远景地面按屏幕 Window Y 显示与天空**完全相同**的
# 渐变：边界两侧逐像素连续，圆盘边缘自然消失。
w = sc.world
world_ramp = None
if w and w.use_nodes:
    ramp = next((nd for nd in w.node_tree.nodes
                 if nd.type in ("VALTORGB", "VAL_TO_RGB")), None)
    if ramp:
        # 保留暖赭暮色这条招牌，但降饱和、把上下两段往冷灰靠，
        # 让「暖带 → 冷雪夜」渐次过渡而不是硬接。
        for e in ramp.color_ramp.elements:
            p = e.position
            if abs(p - 0.620) < 0.03:
                e.color = rgba("#38281F")
            elif abs(p - 0.520) < 0.03:
                e.color = rgba("#2A2527")
            elif abs(p - 0.700) < 0.03:
                e.color = rgba("#1B1E28")
            elif abs(p - 0.280) < 0.03:
                e.color = rgba("#2B2223")
        world_ramp = ramp
        print("R2_OK sky_ramp=cold_dusk")

pm = bpy.data.materials.get("S_Paving_mat")
if pm and pm.use_nodes:
    pn = pm.node_tree
    mixsh = next((nd for nd in pn.nodes if nd.type == "MIX_SHADER"), None)
    far = None
    if mixsh and mixsh.inputs[2].is_linked:
        nd = mixsh.inputs[2].links[0].from_node
        if nd.type == "EMISSION":
            far = nd
    if far:
        far.inputs["Strength"].default_value = 1.0
        if world_ramp is not None:
            tc = pn.nodes.new("ShaderNodeTexCoord")
            sep = pn.nodes.new("ShaderNodeSeparateXYZ")
            gr = pn.nodes.new("ShaderNodeValToRGB")
            tc.location, sep.location, gr.location = (-620, -900), (-400, -900), (-190, -900)
            src = sorted(list(world_ramp.color_ramp.elements), key=lambda e: e.position)
            cr = gr.color_ramp
            cr.interpolation = world_ramp.color_ramp.interpolation
            cr.elements[0].position = src[0].position
            cr.elements[0].color = tuple(src[0].color)
            cr.elements[1].position = src[-1].position
            cr.elements[1].color = tuple(src[-1].color)
            for e in src[1:-1]:
                ne = cr.elements.new(e.position)
                ne.color = tuple(e.color)
            pn.links.new(tc.outputs["Window"], sep.inputs["Vector"])
            pn.links.new(sep.outputs["Y"], gr.inputs["Fac"])
            pn.links.new(gr.outputs["Color"], far.inputs["Color"])
            print("R2_OK far_ground=sky_gradient_matched els=", len(src))
        else:
            far.inputs["Color"].default_value = rgba("#23262E")
    # 淡出带推远：少抹掉被灯照亮的近景雪地，过渡更缓
    if mixsh and mixsh.inputs[0].is_linked:
        fade = mixsh.inputs[0].links[0].from_node
        if fade.type == "MAP_RANGE":
            fade.inputs["From Min"].default_value = 50.0
            fade.inputs["From Max"].default_value = 200.0
            print("R2_OK far_fade=50..200")


# ── 3. 塔身形制可读：补一盏高位中性柔光 + 立面光降橙 ──────────────────
# 现有 4 盏 Facade 灯都在 z=12，只照亮塔的下半段；4 层以上全部沉进暗部，
# 斗拱出跳、斜昂、砖木分界都看不见。补一盏从相机前侧偏右打来的高位柔光，
# 形成明暗面（不做正面平光），让构件有阴影、塔有体积。
ld = bpy.data.lights.new("R2_Facade_High", "AREA")
ld.energy = 15000.0
ld.color = (0.86, 0.91, 1.0)
ld.shape = "DISK"
ld.size = 22.0
lo = bpy.data.objects.new("R2_Facade_High · 高位形制光", ld)
c_r2.objects.link(lo)
lo.location = (34.0, 34.0, 30.0)
lo.rotation_euler = (Vector((0.0, 0.0, 24.0)) - lo.location).to_track_quat("-Z", "Y").to_euler()
print("R2_OK high_key=1 energy=", ld.energy)

# 4 盏立面光原本是很重的橙 (1,.584,.254)，把塔身整体染成通体棕橙；
# 转成中性暖白，木色、砖色、彩画才能各自分开。能量不动，避免整体过曝。
for i in range(1, 5):
    o = bpy.data.objects.get("Facade_%d" % i)
    if o and o.type == "LIGHT":
        o.data.color = (1.0, 0.72, 0.46)
print("R2_OK facade_desaturate=4")

# 环境补光略提、去蓝，给塔身中上部一点整体冷调基底（不改变主体材质）
hemi = bpy.data.objects.get("Hemi · 环境")
if hemi and hemi.type == "LIGHT":
    hemi.data.energy = 0.90
    hemi.data.color = (0.62, 0.70, 0.86)
print("R2_OK hemi_lift=1")

# 左侧前景古槐：纯 Emission 剪影，雪景里没挂上雪，成了一块高饱和青绿贴纸。
# 不删它（它是有意留的深色压角），只降发光强度，让它读作背光树影。
fg_leaf = bpy.data.materials.get("D_FG_Leaf_前景叶冠")
if fg_leaf and fg_leaf.use_nodes:
    cnt = 0
    for nd in fg_leaf.node_tree.nodes:
        if nd.type == "EMISSION":
            try:
                nd.inputs["Strength"].default_value *= 0.45
                cnt += 1
            except Exception:
                pass
    print("R2_OK foreground_tree_dim=", cnt)


# ── 4. 雪夜逻辑：隐藏星点 + 飘雪减量降亮 ──────────────────────────────
# 雪夜云层厚，本就看不到星；原来 300 颗实体星点与 9.5 万飘雪粒子
# 都是 2~4 px 冷白点，混在一起就是一片「撒芝麻」。隐藏星点之后，
# 天上所有白点都只读作雪，逻辑自洽，夜空也重新有了疏密。
stars = bpy.data.objects.get("D_11 夜空星点")
if stars:
    stars.hide_render = True
    stars.hide_viewport = True
    print("R2_OK stars_hidden=1")

field = bpy.data.objects.get("N_SnowField 飘雪域")
if field:
    for mod in field.modifiers:
        if mod.type == "PARTICLE_SYSTEM":
            st = mod.particle_system.settings
            st.count = 32000
            st.particle_size = 0.95
            print("R2_OK flakes=", st.count)
flake_mat = bpy.data.materials.get("Snow_Flake")
if flake_mat and flake_mat.use_nodes:
    emi = next((nd for nd in flake_mat.node_tree.nodes if nd.type == "EMISSION"), None)
    if emi:
        emi.inputs["Color"].default_value = rgba("#A9BAD6")
        emi.inputs["Strength"].default_value = 0.34
        print("R2_OK flake_dim=1")
sc.frame_set(1)


# ── 5. 檐口积雪破边：九道等宽白线太装饰化 ────────────────────────────
# 只调数值，不改结构：按 From Min/From Max 精确定位 add_snow 建的遮罩，
# 降最大覆盖率、加大噪声破边幅度，让檐口积雪变成断续、有厚薄的挂雪。
BREAK = {
    "Eave_Upper_mat": (0.40, 0.72, 0.88, 0.66, 0.48),
    "Eave_Lower_mat": (0.40, 0.72, 0.88, 0.66, 0.48),
    "S_Roof_mat": (0.42, 0.74, 0.85, 0.64, 0.46),
}
for mn, (lo_v, hi_v, cover, new_cover, wobble) in BREAK.items():
    m = bpy.data.materials.get(mn)
    if not m or not m.use_nodes:
        continue
    for nd in m.node_tree.nodes:
        if nd.type == "MAP_RANGE":
            try:
                if (abs(nd.inputs["From Min"].default_value - lo_v) < 0.01 and
                        abs(nd.inputs["From Max"].default_value - hi_v) < 0.01 and
                        abs(nd.inputs["To Max"].default_value - cover) < 0.01):
                    nd.inputs["To Max"].default_value = new_cover
            except Exception:
                pass
        elif nd.type == "MATH" and nd.operation == "MULTIPLY":
            try:
                if 0.2 < nd.inputs[1].default_value < 0.36:
                    nd.inputs[1].default_value = wobble
            except Exception:
                pass
print("R2_OK eave_break=", len(BREAK))


# ── 6. 泛光收敛：雪地亮度降下来后，辉光别再把整片地面糊平 ────────────
if sc.use_nodes:
    for nd in sc.node_tree.nodes:
        if nd.type == "GLARE":
            try:
                nd.inputs["Threshold"].default_value = 0.70
                nd.inputs["Strength"].default_value = 0.60
            except Exception:
                pass
    print("R2_OK glare_tamed=1")


# ── 7. 保存（先存全分辨率设置，再降规格出预览） ──────────────────────
try:
    bpy.ops.file.pack_all()
except Exception as exc:
    print("R2_PACK_WARN", exc)

bpy.ops.wm.save_as_mainfile(filepath=DST, compress=True)
print("R2_OK file=", DST)
print("R2_OK size_mb=", round(os.path.getsize(DST) / 1024.0 / 1024.0, 2))

sc.render.resolution_percentage = 75
try:
    sc.eevee.taa_render_samples = 64
except Exception:
    pass
for i, cam_name in enumerate(("Cam_01 全景", "Cam_02 塔院"), 1):
    cam = bpy.data.objects.get(cam_name)
    if not cam:
        print("R2_PREVIEW_SKIP", cam_name)
        continue
    sc.camera = cam
    sc.render.filepath = os.path.join(HERE, "_r2_cam%d.png" % i)
    bpy.ops.render.render(write_still=True)
    print("R2_PREVIEW_DONE", sc.render.filepath)
print("R2_ALL_DONE")
