# -*- coding: utf-8 -*-
"""凌霄塔 · 雪景层（在 lingxiao_tower_scene.blend 基础上增量叠加）

用法：
  blender -b model/lingxiao_tower_scene.blend --python model/add_snow.py

产物：model/lingxiao_tower_scene_snow.blend（原场景不动，可随时对比回退）

思路
----
雪夜 != 换成白天：保留全部 28 盏暖光与灯笼体系，让积雪去接暖光，
形成「冷雪 · 暖灯」的对比，这是夜景雪景成立的要点。

三件事：
1. 积雪（材质层）：不改几何，在法线朝上的表面把 Base Color 混入积雪白。
   混合遮罩 = 世界法线 Z（坡度）+ 高度加成（越高越挂雪）+ 噪声破边，
   各类材质（屋面 / 地面 / 树冠 / 石作）配不同的覆盖率与阈值。
2. 飘雪（粒子层）：52000 粒实例化雪粒，静止悬浮在大体积内，
   双机位画面里是 2~4 px 的冷白点，配合 Fog Glow 泛光柔化。
3. 冷调（氛围层）：冷补光与天顶环境略提、渐变天空两端转冷、
   大铺地远景淡出色转雪夜冷灰；中段暖赭保留（暮色余晖是场景的招牌）。

约束
----
* 不修改塔体 / 塔院 / 周边细节的既有几何与节点，只在 Principled 的
  Base Color / Roughness 前插入混合节点，可整层删除恢复；
* 坐标 Z-up（米），与 build_scene.py 一致。
"""
import bpy
import os

HERE = os.path.dirname(bpy.data.filepath)
DST = os.path.join(HERE, "lingxiao_tower_scene_snow.blend")
scene = bpy.context.scene


def srgb(h):
    """#RRGGBB → linear RGB 元组（Blender 节点需要线性值）。"""
    h = h.lstrip("#")
    v = [int(h[i:i + 2], 16) / 255.0 for i in (0, 2, 4)]
    return tuple(c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4 for c in v)


def rgba(h):
    return (*srgb(h), 1.0)


SNOW = rgba("#D8E3F2")     # 积雪基色：冷白（暖光打上去呈暖白，冷补光呈青白）

# ── 1. 集合 ──────────────────────────────────────────────────────────
root = bpy.data.collections.get("凌霄塔 · 完整场景")
c_snow = bpy.data.collections.new("04 雪景（积雪 / 飘雪 / 冷调）")
(root or scene.collection).children.link(c_snow)


# ── 2. 材质积雪层 ────────────────────────────────────────────────────
def build_mask(n, cover, lo, hi, hbias, hmax, nscale, wobble, anchor, mode="normal"):
    """构建积雪遮罩节点链，返回遮罩输出 socket。

    normal 模式（默认）：
      遮罩 = MapRange( 法线Z + 高度加成 + 噪声抖动 , lo→hi, 0→cover )
      * 法线 Z：地面/屋面 ≈1，墙面 ≈0，檐底为负 → 天然只积雪在朝上面；
      * 高度加成：塔身上部、高墙顶部额外挂雪（风携雪量随高度增加）；
      * 噪声（对象空间坐标）：破坏均匀雪线，做出片状积雪边缘。
    height 模式：
      遮罩 = MapRange( 世界高度Z(米) + 噪声抖动 , lo→hi, 0→cover )
      给平面着色的低模树冠用：冠体面片法线杂乱，按法线积雪会碎成
      三角碎片（预览第一、二轮已确认）；按世界高度渐变则天然平滑。
    """
    tc = n.nodes.new("ShaderNodeTexCoord")
    geo = n.nodes.new("ShaderNodeNewGeometry")
    sep_n = n.nodes.new("ShaderNodeSeparateXYZ")
    sep_p = n.nodes.new("ShaderNodeSeparateXYZ")
    noise = n.nodes.new("ShaderNodeTexNoise")
    noise.inputs["Scale"].default_value = nscale
    noise.inputs["Detail"].default_value = 3.0
    noise.inputs["Roughness"].default_value = 0.55
    sub = n.nodes.new("ShaderNodeMath")
    sub.operation = "SUBTRACT"
    sub.inputs[1].default_value = 0.5
    wob = n.nodes.new("ShaderNodeMath")
    wob.operation = "MULTIPLY"
    wob.inputs[1].default_value = wobble
    add_w = n.nodes.new("ShaderNodeMath")
    add_w.operation = "ADD"
    mask = n.nodes.new("ShaderNodeMapRange")
    mask.clamp = True
    mask.inputs["From Min"].default_value = lo
    mask.inputs["From Max"].default_value = hi
    mask.inputs["To Min"].default_value = 0.0
    mask.inputs["To Max"].default_value = cover

    n.links.new(tc.outputs["Object"], noise.inputs["Vector"])
    n.links.new(noise.outputs["Fac"], sub.inputs[0])
    n.links.new(sub.outputs["Value"], wob.inputs[0])
    n.links.new(geo.outputs["Position"], sep_p.inputs["Vector"])

    nodes = [tc, geo, sep_n, sep_p, noise, sub, wob, add_w, mask]
    if mode == "height":
        n.links.new(sep_p.outputs["Z"], add_w.inputs[0])
        n.links.new(wob.outputs["Value"], add_w.inputs[1])
        n.links.new(add_w.outputs["Value"], mask.inputs["Value"])
    else:
        hmap = n.nodes.new("ShaderNodeMapRange")
        hmap.clamp = True
        hmap.inputs["From Min"].default_value = 0.0
        hmap.inputs["From Max"].default_value = hmax
        hmap.inputs["To Min"].default_value = 0.0
        hmap.inputs["To Max"].default_value = hbias
        add_h = n.nodes.new("ShaderNodeMath")
        add_h.operation = "ADD"
        n.links.new(geo.outputs["Normal"], sep_n.inputs["Vector"])
        n.links.new(sep_p.outputs["Z"], hmap.inputs["Value"])
        n.links.new(sep_n.outputs["Z"], add_h.inputs[0])
        n.links.new(hmap.outputs["Result"], add_h.inputs[1])
        n.links.new(add_h.outputs["Value"], add_w.inputs[0])
        n.links.new(wob.outputs["Value"], add_w.inputs[1])
        n.links.new(add_w.outputs["Value"], mask.inputs["Value"])
        nodes.insert(6, hmap)
        nodes.insert(7, add_h)

    # 节点摆位：统一放在锚点节点左侧，竖向排开，避免堆成一坨
    bx, by = anchor.location.x - 900.0, anchor.location.y - 640.0
    for i, nd in enumerate(nodes):
        nd.location = (bx + (i % 6) * 150.0, by - (i // 6) * 190.0)
    return mask.outputs["Result"]


def add_snow(mat_name, cover, lo, hi, hbias=0.0, hmax=60.0, nscale=3.0, rough=0.5,
             wobble=0.22, mode="normal", emit_snow="#8FA2BE"):
    """Principled：Base Color / Roughness 前插入积雪混合；
    纯 Emission（前景剪影材质）：发光色混入霜白，让冠顶结霜。"""
    m = bpy.data.materials.get(mat_name)
    if not m or not m.use_nodes:
        return False
    n = m.node_tree
    bsdf = next((nd for nd in n.nodes if nd.type == "BSDF_PRINCIPLED"), None)
    emi = None
    if bsdf is None:
        # 找真正接进输出的 Emission 节点（剪影材质可能带多个）
        for nd in n.nodes:
            if nd.type == "EMISSION" and nd.outputs["Emission"].is_linked:
                emi = nd
                break
    if bsdf is None and emi is None:
        return False
    anchor = bsdf or emi
    mask_sock = build_mask(n, cover, lo, hi, hbias, hmax, nscale, wobble, anchor, mode)

    if bsdf is not None:
        # Base Color：原色 → 积雪白
        mix = n.nodes.new("ShaderNodeMixRGB")
        mix.inputs[2].default_value = SNOW
        base_in = bsdf.inputs["Base Color"]
        if base_in.is_linked:
            n.links.new(base_in.links[0].from_socket, mix.inputs[1])
        else:
            mix.inputs[1].default_value = tuple(base_in.default_value)
        n.links.new(mask_sock, mix.inputs[0])
        n.links.new(mix.outputs["Color"], base_in)

        # Roughness：积雪区略降粗糙度，接住灯笼 / 泛光的暖色高光
        rough_in = bsdf.inputs["Roughness"]
        if not rough_in.is_linked:
            rmul = n.nodes.new("ShaderNodeMath")
            rmul.operation = "MULTIPLY"
            rmul.inputs[1].default_value = 0.75
            rmix = n.nodes.new("ShaderNodeMixRGB")
            rmix.inputs[1].default_value = (rough_in.default_value,) * 3 + (1.0,)
            rmix.inputs[2].default_value = (rough,) * 3 + (1.0,)
            n.links.new(mask_sock, rmul.inputs[0])
            n.links.new(rmul.outputs["Value"], rmix.inputs[0])
            n.links.new(rmix.outputs["Color"], rough_in)
    else:
        # 剪影 / 发光材质：发光色 → 霜白（保持原强度，只换色相）
        mix = n.nodes.new("ShaderNodeMixRGB")
        mix.inputs[2].default_value = rgba(emit_snow)
        col_in = emi.inputs["Color"]
        if col_in.is_linked:
            n.links.new(col_in.links[0].from_socket, mix.inputs[1])
        else:
            mix.inputs[1].default_value = tuple(col_in.default_value)
        n.links.new(mask_sock, mix.inputs[0])
        n.links.new(mix.outputs["Color"], col_in)
    return True


# 各类表面配比：cover=最大覆盖率，lo→hi=法线Z过渡带，hbias/hmax=高度挂雪，
# wobble=噪声破边幅度（屋面大 > 墙面中 > 树冠小——树冠要的是整片软雪盖，
# 噪声太碎会把低模球簇打成「碎纸片」，预览第一轮已确认此问题）
SNOW_SPEC = {
    # —— 塔体 ——
    "Eave_Upper_mat":        dict(cover=0.88, lo=0.40, hi=0.72, hbias=0.08, hmax=60, nscale=1.0, rough=0.38, wobble=0.30),
    "Eave_Lower_mat":        dict(cover=0.88, lo=0.40, hi=0.72, hbias=0.08, hmax=60, nscale=1.0, rough=0.38, wobble=0.30),
    "Base_Stone_mat":        dict(cover=0.80, lo=0.35, hi=0.70, hbias=0.05, hmax=25, nscale=2.8, rough=0.50, wobble=0.25),
    "Body_Wood_Railing_mat": dict(cover=0.60, lo=0.45, hi=0.80, hbias=0.10, hmax=55, nscale=4.0, rough=0.55, wobble=0.22),
    # 塔身砖木壁面：留干净，只在上部让高度加成擦出一线挂雪
    "Body_Lower_mat":        dict(cover=0.50, lo=0.58, hi=0.88, hbias=0.25, hmax=55, nscale=4.0, rough=0.55, wobble=0.22),
    "Body_Upper_mat":        dict(cover=0.50, lo=0.58, hi=0.88, hbias=0.25, hmax=55, nscale=4.0, rough=0.55, wobble=0.22),
    "Dougong_Brick_mat":     dict(cover=0.45, lo=0.55, hi=0.85, hbias=0.20, hmax=50, nscale=4.5, rough=0.55, wobble=0.22),
    "Dougong_Wood_mat":      dict(cover=0.45, lo=0.55, hi=0.85, hbias=0.20, hmax=50, nscale=4.5, rough=0.55, wobble=0.22),
    # —— 塔院 ——
    "S_Roof_mat":            dict(cover=0.85, lo=0.42, hi=0.74, hbias=0.05, hmax=40, nscale=0.8, rough=0.42, wobble=0.30),
    "S_Paving_mat":          dict(cover=0.88, lo=0.30, hi=0.62, hbias=0.00, hmax=60, nscale=1.8, rough=0.45, wobble=0.22),
    "S_Stone_mat":           dict(cover=0.72, lo=0.35, hi=0.70, hbias=0.04, hmax=20, nscale=2.6, rough=0.50, wobble=0.25),
    "S_Wood_mat":            dict(cover=0.60, lo=0.45, hi=0.80, hbias=0.08, hmax=20, nscale=3.4, rough=0.55, wobble=0.22),
    "S_Wall_mat":            dict(cover=0.45, lo=0.58, hi=0.88, hbias=0.18, hmax=25, nscale=4.0, rough=0.55, wobble=0.22),
    "S_Brick_mat":           dict(cover=0.45, lo=0.58, hi=0.88, hbias=0.18, hmax=25, nscale=4.0, rough=0.55, wobble=0.22),
    "S_Caihua_mat":          dict(cover=0.30, lo=0.60, hi=0.90, hbias=0.12, hmax=20, nscale=4.5, rough=0.55, wobble=0.20),
    "S_Bark_mat":            dict(cover=0.30, lo=0.60, hi=0.90, hbias=0.15, hmax=25, nscale=3.5, rough=0.60, wobble=0.18),
    "S_Leaf_mat":            dict(cover=0.55, lo=0.30, hi=0.62, hbias=0.06, hmax=30, nscale=2.5, rough=0.60, wobble=0.10),
    # —— 周边细节 ——
    "D_Slab_青石板":          dict(cover=0.78, lo=0.32, hi=0.68, hbias=0.00, hmax=60, nscale=2.4, rough=0.48, wobble=0.25),
    "D_Gravel_碎石":          dict(cover=0.75, lo=0.32, hi=0.68, hbias=0.00, hmax=60, nscale=3.0, rough=0.48, wobble=0.25),
    "D_Litter_落叶苔痕":      dict(cover=0.65, lo=0.35, hi=0.72, hbias=0.00, hmax=60, nscale=3.5, rough=0.55, wobble=0.22),
    "D_Wet_湿痕":             dict(cover=0.55, lo=0.35, hi=0.72, hbias=0.00, hmax=60, nscale=3.0, rough=0.40, wobble=0.22),
    # 树冠：平面着色低模球簇 → 改用世界高度遮罩（mode=height，lo/hi=米），
    # 法线碎面不再打碎雪层；预览前两轮已确认「碎三角雪片」问题
    "D_Foliage_Core_内芯":    dict(cover=0.45, lo=4.0, hi=10.0, nscale=2.0, rough=0.60, wobble=0.10, mode="height"),
    "D_Foliage_Clump_叶簇":   dict(cover=0.50, lo=4.0, hi=10.0, nscale=2.0, rough=0.60, wobble=0.10, mode="height"),
    "D_Foliage_Leaf_叶片":    dict(cover=0.50, lo=4.0, hi=10.0, nscale=2.0, rough=0.60, wobble=0.10, mode="height"),
    "D_Foliage_Twig_细枝":    dict(cover=0.40, lo=5.0, hi=11.0, nscale=2.5, rough=0.60, wobble=0.12, mode="height"),
    "D_FG_Bark_前景树干":     dict(cover=0.25, lo=0.60, hi=0.90, hbias=0.15, hmax=24, nscale=3.5, rough=0.60, wobble=0.18),
    "D_FG_Leaf_前景叶冠":     dict(cover=0.15, lo=14.0, hi=22.0, nscale=1.8, rough=0.60, wobble=0.12, mode="height", emit_snow="#64718C"),
    "D_FG_Stone_前景石构":    dict(cover=0.75, lo=0.35, hi=0.70, hbias=0.04, hmax=20, nscale=2.8, rough=0.50, wobble=0.25),
    "D_FG_Grass_前景草石":    dict(cover=0.80, lo=0.32, hi=0.70, hbias=0.00, hmax=60, nscale=3.0, rough=0.55, wobble=0.20),
}
# 刻意不积雪：Openings（窗光要透亮）、金刹 / 铜铃（金属性雪挂不住）、
# 灯笼、星点、青烟、窗光、倒影等发光/特效材质。

snowed = [nm for nm, kw in SNOW_SPEC.items() if add_snow(nm, **kw)]
failed = [nm for nm in SNOW_SPEC if nm not in snowed]
print("SNOW_OK mats_snowed=", len(snowed), "/", len(SNOW_SPEC),
      "failed=", failed)


# ── 3. 大铺地远景淡出色：暖赭 → 雪夜暮霭 ─────────────────────────────
# build_scene 里 25~95 m 之外的地面淡入固定 emission #241307 对齐暖天空；
# 雪夜下改为「暮霭中的远处雪原」：中性微暖灰 + 淡出带推远到 45~160 m。
# 取色要点：要比天际暖暮色（#261811）亮、比近景冷白雪面暗，
# 雪原平面边缘（800 m 处）才不会在天空上切出硬直线（预览第三轮已确认）。
pm = bpy.data.materials.get("S_Paving_mat")
if pm and pm.use_nodes:
    pn = pm.node_tree
    mixsh = next((nd for nd in pn.nodes if nd.type == "MIX_SHADER"), None)
    if mixsh:
        if mixsh.inputs[2].is_linked:
            dark = mixsh.inputs[2].links[0].from_node
            if dark.type == "EMISSION":
                dark.inputs["Color"].default_value = rgba("#3E3936")
                dark.inputs["Strength"].default_value = 1.0
        # 淡出范围 25~95 → 45~160：少抹掉一块被灯照亮的近景雪地
        if mixsh.inputs[0].is_linked:
            fade = mixsh.inputs[0].links[0].from_node
            if fade.type == "MAP_RANGE":
                fade.inputs["From Min"].default_value = 45.0
                fade.inputs["From Max"].default_value = 160.0
        print("SNOW_OK paving_far_cold=1")


# ── 4. 飘雪粒子：大体积内静止悬浮的雪粒 ──────────────────────────────
def emission_mat(name, col, strength):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    nt.nodes.clear()
    e = nt.nodes.new("ShaderNodeEmission")
    e.inputs["Color"].default_value = rgba(col)
    e.inputs["Strength"].default_value = strength
    o = nt.nodes.new("ShaderNodeOutputMaterial")
    nt.links.new(e.outputs["Emission"], o.inputs["Surface"])
    return m


# 雪粒本体：0.045 m 低模球，放 5 km 外（相机 clip_end=2000，永不入画）
bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=1, radius=0.045,
                                      location=(5000.0, 5000.0, 0.0))
flake = bpy.context.object
flake.name = "N_SnowFlake 雪粒"
flake.data.materials.append(emission_mat("Snow_Flake", "#CBD9F0", 0.50))
for old in list(flake.users_collection):
    old.objects.unlink(flake)
c_snow.objects.link(flake)

# 发射体：x∈[-120,120] y∈[-120,50] z∈[0,115]（米）
# y 上界收到 50，距 Cam_01(y=72) ≥22 m，近景雪粒不会糊成大团
me = bpy.data.meshes.new("N_SnowField 飘雪域")
sx, sy, sz = 120.0, 85.0, 57.5
ox, oy, oz = 0.0, -35.0, 57.5
me.from_pydata(
    [(ox + dx * sx, oy + dy * sy, oz + dz * sz)
     for dz in (-1, 1) for dy in (-1, 1) for dx in (-1, 1)],
    [], [
        (0, 1, 3, 2), (4, 6, 7, 5), (0, 2, 6, 4), (1, 5, 7, 3),
        (0, 4, 5, 1), (2, 3, 7, 6),
    ])
me.update()
emit = bpy.data.objects.new("N_SnowField 飘雪域", me)
c_snow.objects.link(emit)

mod = emit.modifiers.new("SnowFall", "PARTICLE_SYSTEM")
ps = mod.particle_system
st = ps.settings
st.count = 95000
st.frame_start = 1
st.frame_end = 1            # 全部在第 1 帧就位（静止悬浮云）
st.lifetime = 480
st.emit_from = "VOLUME"
st.physics_type = "NEWTON"
st.effector_weights.gravity = 0.0
st.render_type = "OBJECT"
st.instance_object = flake
st.particle_size = 1.15
st.size_random = 0.70
emit.show_instancer_for_render = False   # 只渲染粒子，不渲染发射体立方体
try:
    ps.seed = 20261109
except Exception:
    pass
scene.frame_set(1)
print("SNOW_OK flakes=", st.count, "emit_from=", st.emit_from)


# ── 5. 冷调氛围：微调既有灯光 / 世界（数值级改动，不动节点结构） ─────
for name, energy in (("Fill · 冷补光", 1.55), ("Hemi · 环境", 0.66)):
    o = bpy.data.objects.get(name)
    if o and o.type == "LIGHT":
        o.data.energy = energy
print("SNOW_OK cool_lights=1")

w = scene.world
if w and w.use_nodes:
    nt = w.node_tree
    # 渐变天空两端（近黑）转冷微提，中段暖赭暮色保留
    ramp = next((nd for nd in nt.nodes if nd.type == "VAL_TO_RGB"), None)
    if ramp:
        ramp.color_ramp.elements[0].color = rgba("#0A0C13")
        ramp.color_ramp.elements[-1].color = rgba("#080A10")
        # 中段暖带压暗降饱和（预览第一轮：暖橙带 vs 冷蓝雪夜衔接生硬），
        # 保留暮色余晖的存在感，但不再从天幕里突兀跳出
        for e in ramp.color_ramp.elements:
            if abs(e.position - 0.62) < 0.03:
                e.color = rgba("#2E1F17")
            elif abs(e.position - 0.52) < 0.03:
                e.color = rgba("#262227")
            elif abs(e.position - 0.70) < 0.03:
                e.color = rgba("#171119")
    # 非相机射线的环境光：暖棕 → 冷灰蓝（模拟雪地冷反照）
    mixw = next((nd for nd in nt.nodes if nd.type == "MIX_SHADER"), None)
    if mixw and mixw.inputs[1].is_linked:
        env = mixw.inputs[1].links[0].from_node
        if env.type == "BACKGROUND":
            env.inputs["Color"].default_value = rgba("#363D4A")
            env.inputs["Strength"].default_value = 0.92
    print("SNOW_OK world_cold=1")


# ── 6. 保存 ──────────────────────────────────────────────────────────
try:
    bpy.ops.file.pack_all()
except Exception as exc:
    print("PACK_WARN", exc)

bpy.ops.wm.save_as_mainfile(filepath=DST, compress=True)
print("SNOW_OK file=", DST)
print("SNOW_OK size_mb=", round(os.path.getsize(DST) / 1024.0 / 1024.0, 2))
print("SNOW_OK collection=", c_snow.name,
      "objects=", len(c_snow.objects),
      "lights=", len([o for o in bpy.data.objects if o.type == "LIGHT"]))
