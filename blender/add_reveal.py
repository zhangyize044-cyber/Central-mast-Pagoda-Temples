"""在既有动画工程上叠加「结构先于全貌」开场 Reveal（0–3.5 s）。

输入：model/lingxiao_tower_scene_anim.blend（22 s / 8 拍，12 fps 节奏预览工程）
输出：model/lingxiao_tower_scene_anim_reveal.blend（独立场景线，输入不动）

设计（v2，依据首轮小样诊断修正）
- 第一眼不是黄昏全景，而是暗场里一根 17 m 塔心柱 + 八根扒梁依次点亮；
  九级外壳显形后由九盏冷白结构光自下而上照出，相机一气拉远成完整塔。
- 暗场必须「硬保持」到 1.6 s：BEZIER 会让曝光在 0.9 s 就爬回黄昏，
  所以 0–1.55 s 用 CONSTANT 钉死极暗值，1.6–2.4 s 才做 ramp。
- 心柱与扒梁是单一合并网格，灯没亮时木色实体也看得见。开场把材质
  Base Color 压成深棕、Emission 只给 0.22，靠小灯依次点亮读作「星图张开」，
  而不是自发光白骨架。
- 冷白结构光 2.45 s 前必须归零，否则 2.9 s 的黄昏全景会变成银色铝合金塔。
- 塔身是合并网格，无法逐层隐藏；「逐层合拢」用分层结构光表达，零几何改动。
- 3.5 s / 11.5 s 两个硬重音、九级点灯阶梯、90 BPM 格点全部保持不变。
- 全部新增对象收在「08 开场 Reveal」集合；既有对象只加开场关键帧。

按 fps 参数化：F(t) 从 sc.render.fps 读取，12 fps 出小样、24 fps 出终版都可重放。
"""
import bpy, os
from mathutils import Vector

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.environ.get("REVEAL_SRC", os.path.join(HERE, "lingxiao_tower_scene_anim.blend"))
OUT = os.environ.get("REVEAL_OUT", os.path.join(HERE, "lingxiao_tower_scene_anim_reveal.blend"))

bpy.ops.wm.open_mainfile(filepath=SRC)
sc = bpy.context.scene
FPS = sc.render.fps
N = sc.frame_end
F = lambda t: max(1, min(N, int(round(t * FPS)) + 1))

COLL_NAME = "08 开场 Reveal（结构显形 / 揭示机位）"
old = bpy.data.collections.get(COLL_NAME)
if old:
    for o in list(old.objects):
        bpy.data.objects.remove(o, do_unlink=True)
    bpy.data.collections.remove(old)
C = bpy.data.collections.new(COLL_NAME)
sc.collection.children.link(C)


def fcurves_of(idblock):
    ad = idblock.animation_data
    if not ad or not ad.action:
        return []
    act = ad.action
    out = []
    try:
        out.extend(list(act.fcurves))
    except Exception:
        pass
    if not out:
        for layer in getattr(act, "layers", []):
            for strip in getattr(layer, "strips", []):
                for bag in getattr(strip, "channelbags", []):
                    out.extend(list(bag.fcurves))
    return out


def constant(idblock):
    for fc in fcurves_of(idblock):
        for kp in fc.keyframe_points:
            kp.interpolation = "CONSTANT"


def smooth_between(idblock, a, b):
    """只把 [a, b) 区间的关键帧设 BEZIER：a 之前保持硬黑，b 之后保持定值。

    Blender 段插值由「前一个关键帧」决定，因此保持 a 之前 / b 处为
    CONSTANT，就能得到「硬黑 → 平滑 ramp → 定值 → 3.5 s 硬重音」。
    """
    for fc in fcurves_of(idblock):
        for kp in fc.keyframe_points:
            if a <= kp.co[0] < b:
                kp.interpolation = "BEZIER"
                kp.handle_left_type = "AUTO_CLAMPED"
                kp.handle_right_type = "AUTO_CLAMPED"


def aim(obj, target):
    obj.rotation_euler = (Vector(target) - obj.location).to_track_quat("-Z", "Y").to_euler()


def cam_key(cam, frame, loc, target):
    cam.location = loc
    aim(cam, target)
    cam.keyframe_insert(data_path="location", frame=frame)
    cam.keyframe_insert(data_path="rotation_euler", frame=frame)


DARK_END = F(1.55)         # 暗场结束、开始 ramp
SHELL_ON = F(1.60)         # 外壳显形
RAMP_END = F(2.40)         # 黄昏到位
F35 = F(3.5)               # 重音①，切回原全景机位
fCut = F(11.5)

# ── 1. 揭示机位：一根柱的近景 → 一气拉远成全塔 ──────────────────────────
cd = bpy.data.cameras.new("Cam_07 结构揭示")
cd.lens = 50.0
cd.clip_end = 2000.0
CAM7 = bpy.data.objects.new("Cam_07 结构揭示", cd)
C.objects.link(CAM7)

cam_key(CAM7, F(0.0), (11.0, 15.0, 26.0), (0.0, 0.0, 25.5))
cam_key(CAM7, F(0.8), (12.5, 17.0, 26.2), (0.0, 0.0, 25.0))
cam_key(CAM7, F(1.6), (20.0, 29.0, 27.0), (0.0, 0.0, 23.0))
cam_key(CAM7, F(2.4), (44.5, 68.0, 29.5), (0.0, 0.0, 20.0))
cam_key(CAM7, F(3.5), (44.5, 68.0, 29.5), (0.0, 0.0, 20.0))
for fr, lens in [(F(0.0), 50.0), (F(1.6), 46.0), (F(2.4), 33.0), (F(3.5), 33.0)]:
    cd.lens = lens
    cd.keyframe_insert(data_path="lens", frame=fr)
for blk in (CAM7, cd):
    for fc in fcurves_of(blk):
        for kp in fc.keyframe_points:
            kp.interpolation = "BEZIER"
            kp.handle_left_type = "AUTO_CLAMPED"
            kp.handle_right_type = "AUTO_CLAMPED"

CAM1 = bpy.data.objects.get("Cam_01 全景")
assert CAM1, "缺 Cam_01 全景"
for m in list(sc.timeline_markers):
    if m.frame == 1:
        m.name = "01 起 · 结构 Reveal"
        m.camera = CAM7
        break
else:
    m = sc.timeline_markers.new("01 起 · 结构 Reveal", frame=1)
    m.camera = CAM7
for m in list(sc.timeline_markers):
    if m.frame == F35:
        m.camera = CAM1
        m.name = "02 重音① · 回全景 / 点灯"
        break
else:
    m = sc.timeline_markers.new("02 重音① · 回全景 / 点灯", frame=F35)
    m.camera = CAM1
cam_key(CAM1, F(0.0), (44.5, 68.0, 29.5), (0.0, 0.0, 20.0))
cam_key(CAM1, F(3.5), (44.5, 68.0, 29.5), (0.0, 0.0, 20.0))
constant(CAM1)
print("REVEAL_OK camera=Cam_07 markers=",
      sorted([(m.frame, m.camera.name if m.camera else None) for m in sc.timeline_markers]))

# ── 2. 开场暗场：外壳全隐，只留塔心柱与扒梁 ─────────────────────────────
TOWER = ["Base_Stone", "Body_Lower", "Body_Upper", "Eave_Lower", "Eave_Upper",
         "Dougong_Brick", "Dougong_Wood", "Openings", "Bells_Metal",
         "Finial_Gold", "Body_Wood_Railing"]
for name in TOWER:
    o = bpy.data.objects.get(name)
    if not o:
        print("REVEAL_WARN missing", name)
        continue
    o.hide_render = True
    o.keyframe_insert(data_path="hide_render", frame=1)
    o.keyframe_insert(data_path="hide_render", frame=SHELL_ON - 1)
    o.hide_render = False
    o.keyframe_insert(data_path="hide_render", frame=SHELL_ON)
    o.keyframe_insert(data_path="hide_render", frame=fCut - 1)
    constant(o)
print("REVEAL_OK shell_hidden_until", SHELL_ON, "objects", len(TOWER))

# 心柱与扒梁是同一合并网格：0–0.2 s 也隐藏，第一帧才是真正的纯黑，
# 0.2 s 才「生长」出来。之后一路可见，不影响 11.5 s 剖视。
heart_obj = bpy.data.objects.get("Heart_Column_Braces")
if heart_obj:
    f_born = F(0.20)
    for fr, h in [(1, True), (max(1, f_born - 1), True),
                  (f_born, False), (N, False)]:
        heart_obj.hide_render = h
        heart_obj.keyframe_insert(data_path="hide_render", frame=fr)
    constant(heart_obj)
    print("REVEAL_OK heart_hidden_until", f_born)

# ── 3. 心柱压深棕 + 低自发光，靠小灯依次点亮 ─────────────────────────────
# 原 Base Color (0.323,0.195,0.072) 在世界光下就是浅木色，暗场里也会显形。
# 压到接近黑的深棕，只在开场段生效；2.4 s 恢复原色，不影响 11.5 s 剖视。
heart_mat = bpy.data.materials.get("Heart_Column_Braces_mat")
DARK_WOOD = (0.012, 0.006, 0.003, 1.0)
if heart_mat and heart_mat.use_nodes:
    bsdf = next((n for n in heart_mat.node_tree.nodes if n.type == "BSDF_PRINCIPLED"), None)
    if bsdf:
        bc = bsdf.inputs.get("Base Color")
        if bc:
            orig = tuple(bc.default_value)
            for fr, v in [(1, DARK_WOOD), (RAMP_END, orig), (fCut - 1, orig),
                          (fCut, DARK_WOOD), (F(16.0) - 1, DARK_WOOD),
                          (F(16.0), orig), (N, orig)]:
                bc.default_value = v
                bc.keyframe_insert(data_path="default_value", frame=fr)
            print("REVEAL_OK heart_basecolor=dark_0..2.4")
        es = bsdf.inputs.get("Emission Strength")
        if es:
            for fr, v in [(1, 0.0), (F(0.15), 0.10), (DARK_END, 0.10),
                          (RAMP_END, 0.0), (fCut - 1, 0.0)]:
                es.default_value = v
                es.keyframe_insert(data_path="default_value", frame=fr)
        constant(heart_mat.node_tree)
        smooth_between(heart_mat.node_tree, 1, F(0.15))
        print("REVEAL_OK heart_emission=0.10（让扒梁灯成为唯一主光）")

core = bpy.data.lights.get("Anim_Core")
if core:
    for fr, e in [(1, 0.0), (F(0.2), 70.0), (DARK_END, 70.0),
                  (RAMP_END, 0.0), (fCut - 1, 0.0)]:
        core.energy = e
        core.keyframe_insert(data_path="energy", frame=fr)
    constant(core)
    smooth_between(core, 1, F(0.2))

# 八根扒梁 0.58–1.42 s 依次亮，每根 0.12 s；心柱自发光压到 0.10 后，
# 这 8 盏灯是暗场里唯一的主光，「逐根张开」才读得出来。
for i in range(8):
    ld = bpy.data.lights.get("Anim_Brace_%02d" % (i + 1))
    if not ld:
        continue
    f = F(0.58 + i * 0.12)
    for fr, e in [(1, 0.0), (max(1, f - 1), 0.0), (f, 420.0),
                  (DARK_END, 420.0), (SHELL_ON + 1, 0.0),
                  (F(12.2) - 1, 0.0)]:
        ld.energy = e
        ld.keyframe_insert(data_path="energy", frame=fr)
    constant(ld)
print("REVEAL_OK brace_open=8 420W @0.58..1.42")

# ── 4. 九盏冷白结构光：外壳显形后自下而上把塔「照出来」 ──────────────────
# 700 W、中性偏冷（不是纯蓝），2.45 s 前全部归零，保证 2.9 s 是纯黄昏。
for i in range(9):
    r = 4.4 * (0.942 ** i)
    z = 2.0 + (i + 0.5) * 3.78
    d = r + 1.6
    ld = bpy.data.lights.new("Anim_Reveal_Tier_%02d" % (i + 1), "POINT")
    ld.color = (0.94, 0.94, 0.97)
    ld.energy = 0.0
    ld.shadow_soft_size = 1.8
    ld.cutoff_distance = 20.0
    lo = bpy.data.objects.new("Anim_Reveal_Tier_%02d · 冷白结构光" % (i + 1), ld)
    C.objects.link(lo)
    lo.location = (d * 0.55, d * 0.84, z)
    f = F(1.62 + i * 0.065)
    for fr, e in [(1, 0.0), (max(1, f - 1), 0.0), (f, 480.0),
                  (F(2.30), 480.0), (F(2.45), 0.0), (N, 0.0)]:
        ld.energy = e
        ld.keyframe_insert(data_path="energy", frame=fr)
    constant(ld)
print("REVEAL_OK reveal_tier_lights=9 480W @1.62..2.14 off@2.45")

# ── 5. 暗场 → 黄昏：0–1.55 s 硬黑，1.6–2.4 s 才 ramp ───────────────────
for fr, v in [(1, -0.90), (DARK_END, -0.90), (RAMP_END, 0.95), (F35 - 1, 0.95)]:
    sc.view_settings.exposure = v
    sc.keyframe_insert(data_path="view_settings.exposure", frame=fr)
constant(sc)
smooth_between(sc, DARK_END, RAMP_END)
print("REVEAL_OK exposure=-0.90 hold->0.95")

w = sc.world
if w and w.use_nodes:
    for node_name, vals in [("背景", (0.020, 1.0)), ("背景.001", (0.015, 1.15))]:
        nd = w.node_tree.nodes.get(node_name)
        if not nd:
            continue
        s = nd.inputs["Strength"]
        for fr, v in [(1, vals[0]), (DARK_END, vals[0]),
                      (RAMP_END, vals[1]), (F35 - 1, vals[1])]:
            s.default_value = v
            s.keyframe_insert(data_path="default_value", frame=fr)
    constant(w.node_tree)
    smooth_between(w.node_tree, DARK_END, RAMP_END)
    print("REVEAL_OK sky/env hold-ramp")


def ramp_light_energy(o, base):
    """开场压到 0，1.6–2.4 s ramp 回 base；3.5 s 起的既有阶梯不动。"""
    for fr, e in [(1, 0.0), (DARK_END, 0.0), (RAMP_END, base), (F35 - 1, base)]:
        o.data.energy = e
        o.data.keyframe_insert(data_path="energy", frame=fr)
    constant(o.data)
    smooth_between(o.data, DARK_END, RAMP_END)


for o in bpy.data.objects:
    if o.type != "LIGHT":
        continue
    n = o.name
    if n.startswith("Dusk_Form_High"):
        ramp_light_energy(o, 14000.0)
    elif n.startswith("Facade_"):
        ramp_light_energy(o, 672.0 * 0.16)
    elif n.startswith("WarmPoint_") or n.startswith("Uplight_"):
        ramp_light_energy(o, max(1.0, o.data.energy))
print("REVEAL_OK light_ramp done")

# ── 6. 场景备注与保存 ───────────────────────────────────────────────────
sc["reveal_note"] = (
    "0–3.5 s 结构先于全貌：0–1.55 s 硬暗场，心柱压深棕 + 八扒梁 260 W 依次亮；"
    "1.6 s 外壳显形、九盏 700 W 冷白结构光自下而上照出九级；"
    "1.6–2.4 s 曝光/天空/形制光 ramp 回黄昏，Cam_07 一气拉远成全景；"
    "2.45 s 冷白光归零。3.5 s / 11.5 s 硬重音与九级暖灯阶梯不变。"
    "主体几何未动；08 开场 Reveal 集合可整层删除。"
)
bpy.ops.wm.save_as_mainfile(filepath=OUT)
print("REVEAL_SAVED", OUT)
print("REVEAL_ALL_DONE")
