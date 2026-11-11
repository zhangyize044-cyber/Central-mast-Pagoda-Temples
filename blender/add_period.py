"""砖木分期着色（呈现层，不动几何）

基线：lingxiao_tower_scene_dusk.blend
输出：lingxiao_tower_scene_dusk_period.blend

形制依据：凌霄塔下三层为宋代砖构，四层以上为金代重建的木构。
build_tower.py 原本按 brick_tiers=3 把塔身拆成 Body_Lower / Body_Upper
两组（用途是网页剖视），恰好与这条形制分界重合，因此不需要任何几何改动。

做法：在每个分期材质的「贴图 Color → Principled Base Color」之间插一个
MULTIPLY 色调节点，保留全部纹理细节，只做极其克制的色温偏移：
  宋砖构 → 冷青灰    金木构 → 暖赭木
节点 Fac 设为 0 即完整回退到未分期状态。

跨全塔、不归属任何一期的对象一律不动：
  Base_Stone / Body_Wood_Railing / Openings / Finial_Gold /
  Bells_Metal / Heart_Column_Braces

用法：
  blender -b model/lingxiao_tower_scene_dusk.blend --python model/add_period.py
  PERIOD_FINAL=1 blender -b ... --python ...   # 输出全分辨率正式成片
"""
import bpy
import os
from mathutils import Vector

HERE = os.path.dirname(os.path.abspath(__file__))
FINAL = os.environ.get("PERIOD_FINAL") == "1"
sc = bpy.context.scene

# ── 1. 分期色调 ────────────────────────────────────────────────────────
# 线性空间乘数。刻意不用强色块：这是主视觉，不是示意图；懂形制的人能读出
# 「下冷上暖」即可，观众第一眼看到的仍应是一座塔，不是一张分析图。
# 贴图本身是暖棕，乘一个接近白的数只会整体变亮／变暗，色相推不动。
# 因此拉开 RGB 通道比例，再用 FAC 把整体强度收回来。
LOWER = {
    "Body_Lower_mat":    (0.46, 0.78, 1.24, 1.0),   # 宋 · 青砖：压红、提蓝
    "Dougong_Brick_mat": (0.60, 0.84, 1.16, 1.0),
    "Eave_Lower_mat":    (0.68, 0.88, 1.12, 1.0),
}
UPPER = {
    "Body_Upper_mat":    (1.44, 1.02, 0.58, 1.0),   # 金 · 木构：提红、压蓝
    "Dougong_Wood_mat":  (1.20, 1.00, 0.82, 1.0),   # 已有青绿彩画，只轻带
    "Eave_Upper_mat":    (1.14, 1.00, 0.86, 1.0),   # 灰瓦不宜变暖成琉璃
}

# Fac 是强度旋钮：0 = 完全回退，0.7 上下 = 主视觉克制档，1 = 图版示意档。
FAC = float(os.environ.get("PERIOD_FAC", "0.72"))


def apply_tint(mat_name, tint, strength=FAC):
    m = bpy.data.materials.get(mat_name)
    if not m or not m.use_nodes:
        print("PERIOD_SKIP no_material", mat_name)
        return False
    nt = m.node_tree
    bsdf = next((n for n in nt.nodes if n.type == "BSDF_PRINCIPLED"), None)
    if not bsdf:
        print("PERIOD_SKIP no_bsdf", mat_name)
        return False
    bc = bsdf.inputs.get("Base Color")
    if bc is None or not bc.is_linked:
        print("PERIOD_SKIP no_texture", mat_name)
        return False

    mix = nt.nodes.get("PERIOD_TINT")
    if mix is None:
        src = bc.links[0].from_socket
        nt.links.remove(bc.links[0])
        mix = nt.nodes.new("ShaderNodeMixRGB")
        mix.name = "PERIOD_TINT"
        mix.label = "分期色调 · Fac=0 回退"
        mix.blend_type = "MULTIPLY"
        mix.location = (-180, 220)
        nt.links.new(src, mix.inputs[1])
        nt.links.new(mix.outputs["Color"], bc)
    mix.inputs[0].default_value = strength
    mix.inputs[2].default_value = tint
    print("PERIOD_OK tint", mat_name, tuple(round(v, 3) for v in tint))
    return True


n_ok = 0
for name, tint in LOWER.items():
    n_ok += apply_tint(name, tint)
for name, tint in UPPER.items():
    n_ok += apply_tint(name, tint)

# ── 2. 独立集合：分界锚点与分期特写机位 ──────────────────────────────────
c = bpy.data.collections.get("06 砖木分期（宋砖 / 金木）")
if c is None:
    c = bpy.data.collections.new("06 砖木分期（宋砖 / 金木）")
    sc.collection.children.link(c)

for label, z in (
    ("分界 · 三层顶／四层起 z≈16.85 m", 16.85),
    ("塔基顶 z≈2.00 m", 2.00),
    ("塔身顶 z≈35.83 m", 35.83),
):
    if bpy.data.objects.get(label):
        continue
    e = bpy.data.objects.new(label, None)
    c.objects.link(e)
    e.empty_display_type = "PLAIN_AXES"
    e.empty_display_size = 1.8
    e.location = (0.0, 0.0, z)

cam_name = "Cam_04 分期特写"
cam = bpy.data.objects.get(cam_name)
if cam is None:
    cd = bpy.data.cameras.new(cam_name)
    cd.lens = 45.0
    cd.clip_end = 2000.0
    cam = bpy.data.objects.new(cam_name, cd)
    c.objects.link(cam)
    # 退到约 55 m，让 z≈16.85 m 的砖木分界落在画面中部，
    # 下三层上部与四～六层同框，塔不被上下裁死。
    cam.location = (30.0, 46.0, 23.0)
    cam.rotation_euler = (Vector((0.0, 0.0, 17.0)) - cam.location).to_track_quat("-Z", "Y").to_euler()

sc["period_note"] = (
    "下三层宋砖构（冷青灰）／四层以上金木构（暖赭），仅色调校正，几何未动；"
    "PERIOD_TINT 节点 Fac 为强度旋钮：0=回退，%.2f=主视觉，1=图版示意。"
    "分界 z≈16.85 m。" % FAC
)

# ── 3. 保存（保存的是全分辨率、全景机位的正式状态） ──────────────────────
sc.camera = bpy.data.objects.get("Cam_01 全景")
sc.render.resolution_x, sc.render.resolution_y = 1600, 1000
sc.render.resolution_percentage = 100
sc.render.image_settings.file_format = "PNG"
try:
    sc.eevee.taa_render_samples = 96
except Exception:
    pass
sc.frame_set(1)

out_blend = os.path.join(HERE, "lingxiao_tower_scene_dusk_period.blend")
bpy.ops.wm.save_as_mainfile(filepath=out_blend)
print("PERIOD_SAVED", out_blend, "tinted_materials", n_ok)

# ── 4. 出片（预览 60%，正式 100%） ──────────────────────────────────────
if not FINAL:
    sc.render.resolution_percentage = 60
    try:
        sc.eevee.taa_render_samples = 48
    except Exception:
        pass

shots = (
    ("Cam_01 全景", 1600, 1000,
     "../shots/22-dusk-period-full.png" if FINAL else "_period_wide.png"),
    (cam_name, 1400, 900,
     "../shots/23-dusk-period-detail.png" if FINAL else "_period_detail.png"),
)
for cam_n, rx, ry, out in shots:
    ob = bpy.data.objects.get(cam_n)
    if not ob:
        print("PERIOD_RENDER_SKIP", cam_n)
        continue
    sc.camera = ob
    sc.render.resolution_x, sc.render.resolution_y = rx, ry
    sc.render.filepath = os.path.abspath(os.path.join(HERE, out))
    bpy.ops.render.render(write_still=True)
    print("PERIOD_RENDER_DONE", sc.render.filepath)

print("PERIOD_ALL_DONE final=", FINAL)
