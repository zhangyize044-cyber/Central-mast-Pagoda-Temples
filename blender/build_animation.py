"""按 deliverables/animation-beats.json 生成 22 s / 8 拍动画关键帧。

输入：model/lingxiao_tower_scene_dusk_period.blend（黄昏 + 砖木分期，对外主视觉基线）
输出：model/lingxiao_tower_scene_anim.blend（第六条独立场景线，前五条不动）

原则
- 主体几何一根不动；本脚本只新增「07 动画层」中的相机与灯光，并给已有对象
  打可见性 / 材质 / 曝光关键帧。删掉整个 07 集合即可回到静态主视觉。
- 相机切换用 timeline marker（scene.camera 是指针，不能直接打关键帧）。
- 硬重音用 CONSTANT 插值，不做渐亮；推拉镜头用线/贝塞尔插值。
- 天空色标不做动画：蓝调黄昏是本项目的视觉签名，硬改天空会闪帧。
  「天色压一档 / 入夜」改用曝光 + 环境背景强度 + 星点可见性 + 暖灯能量实现。

环境变量
  ANIM_FPS   帧率，默认 12（节奏预览）；终版设 24
  ANIM_OUT   输出 .blend 路径，默认 model/lingxiao_tower_scene_anim.blend
"""
import bpy, json, math, os
from mathutils import Vector

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
BEATS = os.path.join(ROOT, "deliverables", "animation-beats.json")
SRC = os.path.join(HERE, "lingxiao_tower_scene_dusk_period.blend")
OUT = os.environ.get("ANIM_OUT", os.path.join(HERE, "lingxiao_tower_scene_anim.blend"))
FPS = int(os.environ.get("ANIM_FPS", "12"))

cfg = json.load(open(BEATS, encoding="utf-8"))
DUR = float(cfg["duration"])
F = lambda t: max(1, int(round(t * FPS)) + 1)     # 时间码 → 帧号
N = int(round(DUR * FPS))

bpy.ops.wm.open_mainfile(filepath=SRC)
sc = bpy.context.scene

sc.render.fps = FPS
sc.frame_start = 1
sc.frame_end = N
sc.render.resolution_x = cfg["render"]["width"]
sc.render.resolution_y = cfg["render"]["height"]
sc.render.resolution_percentage = 100
sc.render.image_settings.file_format = "PNG"
sc.render.image_settings.color_mode = "RGB"

# 清掉可能存在的旧 marker（脚本可重放）
for m in list(sc.timeline_markers):
    sc.timeline_markers.remove(m)

# ── 动画专用集合：整层可删、可关 ────────────────────────────────────────
COLL_NAME = "07 动画层（节拍相机 / 分层灯 / 结构光效）"
old = bpy.data.collections.get(COLL_NAME)
if old:
    for o in list(old.objects):
        bpy.data.objects.remove(o, do_unlink=True)
    bpy.data.collections.remove(old)
C = bpy.data.collections.new(COLL_NAME)
sc.collection.children.link(C)


def fcurves_of(idblock):
    """兼容 Blender 4.4 slotted action：取出该数据块的所有 fcurve。"""
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
    """把该数据块所有关键帧设为 CONSTANT —— 硬切、硬跳全靠它。"""
    for fc in fcurves_of(idblock):
        for kp in fc.keyframe_points:
            kp.interpolation = "CONSTANT"


def smooth(idblock):
    for fc in fcurves_of(idblock):
        for kp in fc.keyframe_points:
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


# ── 1. 相机：补齐节拍表要求但基线里没有的两台 ────────────────────────────
CAM1 = bpy.data.objects.get("Cam_01 全景")
assert CAM1, "缺 Cam_01 全景"

cd = bpy.data.cameras.new("Cam_05 斗拱特写")
cd.lens = 62.0
cd.clip_end = 2000.0
CAM5 = bpy.data.objects.new("Cam_05 斗拱特写", cd)
C.objects.link(CAM5)

cd = bpy.data.cameras.new("Cam_06 结构剖视")
cd.lens = 44.0
cd.clip_end = 2000.0
CAM6 = bpy.data.objects.new("Cam_06 结构剖视", cd)
C.objects.link(CAM6)

# 拍 01 极缓推近 → 拍 03 静止 → 拍 07 拉回 → 拍 08 定格
T1 = (0.0, 0.0, 20.0)
cam_key(CAM1, F(0.0), (47.0, 72.0, 31.0), T1)
cam_key(CAM1, F(3.5), (44.5, 68.0, 29.5), T1)
cam_key(CAM1, F(8.0), (44.5, 68.0, 29.5), T1)
cam_key(CAM1, F(16.0), (47.0, 72.0, 31.0), T1)
cam_key(CAM1, F(22.0), (47.0, 72.0, 31.0), T1)
smooth(CAM1)

# 拍 04 推近 + 轻微环绕，对准四～六层斗拱（z≈20–28）
T5 = (0.0, 0.0, 25.0)
cam_key(CAM5, F(8.0), (20.0, 34.0, 21.0), T5)
cam_key(CAM5, F(11.5), (15.0, 26.0, 24.0), T5)
smooth(CAM5)

# 拍 06 缓慢上升看塔心柱与八根扒梁
# 机位要同时收进「下三层砖塔心室 + 四层以上塔心柱」，否则剖视只剩一根悬空骨架。
T6 = (0.0, 0.0, 20.0)
CAM6.data.lens = 38.0
cam_key(CAM6, F(11.5), (37.0, 47.0, 20.0), T6)
cam_key(CAM6, F(16.0), (33.0, 42.0, 27.0), (0.0, 0.0, 22.0))
smooth(CAM6)

MARKERS = [
    (F(0.0), "01 起 · 全景", CAM1),
    (F(8.0), "04 动 · 斗拱特写", CAM5),
    (F(11.5), "05 重音② · 剖开", CAM6),
    (F(16.0), "07 放 · 回全景", CAM1),
]
for fr, name, cam in MARKERS:
    m = sc.timeline_markers.new(name, frame=fr)
    m.camera = cam
sc.camera = CAM1
print("ANIM_OK markers=%d frames=1..%d fps=%d" % (len(MARKERS), N, FPS))

fCut, fBack = F(11.5), F(16.0)   # 重音② 剖开 / 第 7 拍回全景


# ── 2. 九级逐层点灯：新增 9 盏小范围暖点光，能量阶梯硬跳 ────────────────
# 现有 32 盏是全场景混光，无法按层控制。这里新增的分层灯带 cutoff_distance，
# 只照亮各层檐下局部，不会把整场重新推平。
TIER_LIGHTS = []
for i in range(9):
    r = 4.4 * (0.942 ** i)
    z = 2.0 + (i + 0.5) * 3.78
    d = r + 1.6
    ld = bpy.data.lights.new("Anim_Tier_%02d" % (i + 1), "POINT")
    ld.color = (1.0, 0.45, 0.18)
    ld.energy = 0.0
    ld.shadow_soft_size = 1.5
    ld.cutoff_distance = 16.0
    lo = bpy.data.objects.new("Anim_Tier_%02d · 第%d级檐下" % (i + 1, i + 1), ld)
    C.objects.link(lo)
    lo.location = (d * 0.55, d * 0.84, z)
    TIER_LIGHTS.append(ld)

# 第一盏在重音 ①（3.5s）硬跳亮，其余在 4.0–7.6s 每 0.4s 一盏。
# 关键：塔身原本已被 4 盏 Facade 灯 + 14000 高位形制光照亮，若只加分层灯，
# 九级点灯会完全读不出来。所以让「整体暖光水平」跟九级同步做阶梯上升：
# 点灯前塔身是冷白剪影（只有冷形制光），灯火自下而上把塔染成暖金。
TIER_TIMES = [3.5] + [4.0 + i * 0.45 for i in range(8)]
for ld, t in zip(TIER_LIGHTS, TIER_TIMES):
    f = F(t)
    for fr, e in [(max(1, f - 1), 0.0), (f, 6500.0),
                  (fCut - 1, 6500.0),          # 斗拱特写段保持全亮
                  (fCut, 0.0),                  # 剖开：全关，进暗场
                  (fBack - 1, 0.0),
                  (fBack, 1100.0),              # 夜景：降档常亮，不再推爆塔身
                  (N, 1100.0)]:
        ld.energy = e
        ld.keyframe_insert(data_path="energy", frame=fr)
    constant(ld)
print("ANIM_OK tier_lights=9 first=%s last=%s" % (TIER_TIMES[0], TIER_TIMES[-1]))

FACADES = [o for o in bpy.data.objects
           if o.type == "LIGHT" and o.name.startswith("Facade_")]
for o in FACADES:
    base = o.data.energy
    o.data.energy = base * 0.16
    o.data.keyframe_insert(data_path="energy", frame=1)
    for i, t in enumerate(TIER_TIMES):
        f = F(t)
        o.data.energy = base * (0.16 + 0.84 * (i + 1) / 9.0)
        o.data.keyframe_insert(data_path="energy", frame=f)
    for fr, k in [(fCut - 1, 1.0), (fCut, 0.22), (fBack - 1, 0.22),
                  (fBack, 0.82), (N, 0.82)]:
        o.data.energy = base * k
        o.data.keyframe_insert(data_path="energy", frame=fr)
    constant(o.data)
print("ANIM_OK facade_staircase=%d" % len(FACADES))

# 塔刹宝珠收亮（第 9 级之后），用一盏高位小灯点一下
finial = bpy.data.lights.new("Anim_Finial", "POINT")
finial.color = (1.0, 0.78, 0.42)
finial.energy = 0.0
finial.cutoff_distance = 12.0
fo = bpy.data.objects.new("Anim_Finial · 塔刹收亮", finial)
C.objects.link(fo)
fo.location = (0.0, 0.0, 40.0)
for fr, e in [(F(7.8) - 1, 0.0), (F(7.8), 900.0), (N, 900.0)]:
    finial.energy = e
    finial.keyframe_insert(data_path="energy", frame=fr)
constant(finial)


# ── 3. 重音② 剖开：外壳瞬隐 + 塔心柱自发光点亮 ─────────────────────────
# 「四层以上外壳」= 上部塔身 / 上六层檐 / 木斗拱 / 门窗 / 风铎 / 塔刹 / 栏杆。
# 下三层砖塔心室保持实体。硬切，不做渐隐。
UPPER_SHELL = ["Body_Upper", "Eave_Upper", "Dougong_Wood", "Openings",
               "Bells_Metal", "Finial_Gold", "Body_Wood_Railing"]
for name in UPPER_SHELL:
    o = bpy.data.objects.get(name)
    if not o:
        print("ANIM_WARN missing", name)
        continue
    for fr, hidden in [(1, False), (fCut - 1, False),
                       (fCut, True), (fBack - 1, True), (fBack, False), (N, False)]:
        o.hide_render = hidden
        o.keyframe_insert(data_path="hide_render", frame=fr)
    constant(o)
print("ANIM_OK xray_shell=%d cut=%d back=%d" % (len(UPPER_SHELL), fCut, fBack))

# Heart_Column_Braces 是单一合并网格，无法按八根梁分别控制；用材质自发光
# 让整根柱「点亮」，再用 8 盏放射方向的小灯依次亮起，读作扒梁逐根显形。
heart_mat = bpy.data.materials.get("Heart_Column_Braces_mat")
if heart_mat and heart_mat.use_nodes:
    bsdf = next((n for n in heart_mat.node_tree.nodes if n.type == "BSDF_PRINCIPLED"), None)
    if bsdf:
        # 纯白的根子在材质本身：原 Base Color 是浅木色，外壳一隐就被全局光
        # 照成象牙白。剖视段把它压成深棕，柱子重新吃光 —— 这样八根扒梁灯
        # 的依次亮才读得出来（纯 Emission 会完全不吃光，反而看不见变化）。
        bc = bsdf.inputs.get("Base Color")
        if bc:
            orig = tuple(bc.default_value)
            dark = (0.105, 0.052, 0.024, 1.0)
            for fr, v in [(1, orig), (fCut - 1, orig), (fCut, dark),
                          (fBack - 1, dark), (fBack, orig), (N, orig)]:
                bc.default_value = v
                bc.keyframe_insert(data_path="default_value", frame=fr)
            print("ANIM_OK heart_basecolor=dark_wood @", fCut)
        ec = bsdf.inputs.get("Emission Color")
        es = bsdf.inputs.get("Emission Strength")
        if ec:
            ec.default_value = (1.0, 0.58, 0.24, 1.0)
        if es:
            for fr, v in [(1, 0.0), (fCut - 1, 0.0), (fCut, 0.18),
                          (fBack - 1, 0.18), (fBack, 0.0), (N, 0.0)]:
                es.default_value = v
                es.keyframe_insert(data_path="default_value", frame=fr)
        constant(heart_mat.node_tree)
        print("ANIM_OK heart_emission=0.18 @", fCut)

core = bpy.data.lights.new("Anim_Core", "POINT")
core.color = (1.0, 0.80, 0.48)
core.energy = 0.0
core.cutoff_distance = 24.0
co = bpy.data.objects.new("Anim_Core · 塔心柱", core)
C.objects.link(co)
co.location = (0.0, 0.0, 26.0)

# Heart_Column_Braces 的八根扒梁在成片里读作四层「丰」字横杆，每层左右各一。
# 灯按 4 层 × 2 向分布，依次亮才看得出逐根显形，而不是一圈同时白。
BRACE_LIGHTS = []
for i in range(8):
    level, side = i // 2, i % 2
    z = 18.8 + level * 3.8
    x = 3.1 if side == 0 else -3.1
    ld = bpy.data.lights.new("Anim_Brace_%02d" % (i + 1), "POINT")
    ld.color = (1.0, 0.78, 0.44)
    ld.energy = 0.0
    ld.cutoff_distance = 7.0
    lo = bpy.data.objects.new("Anim_Brace_%02d · 第%d层扒梁%d" %
                              (i + 1, level + 1, side + 1), ld)
    C.objects.link(lo)
    lo.location = (x, 1.6, z)
    BRACE_LIGHTS.append(ld)

for fr, e in [(1, 0.0), (fCut - 1, 0.0), (fCut, 260.0),
              (fBack, 0.0), (N, 0.0)]:
    core.energy = e
    core.keyframe_insert(data_path="energy", frame=fr)
constant(core)

for i, ld in enumerate(BRACE_LIGHTS):
    t = 12.2 + i * 0.42
    f = F(t)
    for fr, e in [(1, 0.0), (f - 1, 0.0), (f, 700.0),
                  (fBack, 0.0), (N, 0.0)]:
        ld.energy = e
        ld.keyframe_insert(data_path="energy", frame=fr)
    constant(ld)
print("ANIM_OK brace_lights=8 staircase=12.2..%.2f" % (12.2 + 7 * 0.42))


# ── 4. 天色 / 入夜：曝光 + 环境背景强度 + 星点 + 暖灯全亮 ────────────────
# 天空色标保持蓝调黄昏不变（视觉签名）。重音①压一档，第 7 拍用星点与
# 暖灯全亮「放」回夜色，不做跨 .blend 拼接。
try:
    for fr, v in [(1, 0.95), (F(3.5) - 1, 0.95), (F(3.5), 0.80),
                  (fCut - 1, 0.80), (fCut, 0.70), (fBack - 1, 0.70),
                  (fBack, 0.82), (N, 0.82)]:
        sc.view_settings.exposure = v
        sc.keyframe_insert(data_path="view_settings.exposure", frame=fr)
    constant(sc)
    print("ANIM_OK exposure_keyframes=6")
except Exception as ex:
    print("ANIM_WARN exposure_keyframe_failed", ex)

w = sc.world
if w and w.use_nodes:
    # 「背景」的 Color 来自七段天空色标，Strength 是常数；给它打关键帧等于
    # 整体压暗天空而不改色标 —— 蓝调黄昏签名保住，入夜又读得出来。
    bg1 = w.node_tree.nodes.get("背景")
    if bg1:
        s1 = bg1.inputs["Strength"]
        for fr, v in [(1, 1.0), (F(3.5) - 1, 1.0), (F(3.5), 0.86),
                      (fCut - 1, 0.86), (fCut, 0.34), (fBack - 1, 0.34),
                      (fBack, 0.48), (N, 0.48)]:
            s1.default_value = v
            s1.keyframe_insert(data_path="default_value", frame=fr)
        print("ANIM_OK sky_strength=1.0->0.86->0.34(剖视暗场)->0.48")
    bg2 = w.node_tree.nodes.get("背景.001")
    if bg2:
        st = bg2.inputs["Strength"]
        for fr, v in [(1, 1.15), (F(3.5) - 1, 1.15), (F(3.5), 0.82),
                      (fCut - 1, 0.82), (fCut, 0.42), (fBack - 1, 0.42),
                      (fBack, 0.70), (N, 0.70)]:
            st.default_value = v
            st.keyframe_insert(data_path="default_value", frame=fr)
        print("ANIM_OK env_strength=1.15->0.82->0.42->0.70")
    constant(w.node_tree)

stars = bpy.data.objects.get("D_11 夜空星点")
if stars:
    for fr, h in [(1, True), (F(16.0) - 1, True), (F(16.0), False), (N, False)]:
        stars.hide_render = h
        stars.keyframe_insert(data_path="hide_render", frame=fr)
    constant(stars)
    print("ANIM_OK stars_on@", F(16.0))

# 塔身暖点在点灯前压到 20%，第 7 拍一次性跳到 130% —— 与压暗的天空形成
# 「灯火全亮」的放。院子里的 Lantern_*_Glow 不参与，保持环境氛围不塌。
WARM_PREFIX = ("WarmPoint_", "Uplight_")
warm = [o for o in bpy.data.objects
        if o.type == "LIGHT" and o.name.startswith(WARM_PREFIX)]
for o in warm:
    base = o.data.energy
    for fr, k in [(1, 0.20), (fCut - 1, 0.20), (fCut, 0.12),
                  (fBack - 1, 0.12), (fBack, 1.10), (N, 1.10)]:
        o.data.energy = base * k
        o.data.keyframe_insert(data_path="energy", frame=fr)
    constant(o.data)
print("ANIM_OK warm_lights_boost=%d (0.20->0.12->1.10)" % len(warm))

# 高位形制光是「蓝调黄昏专供」：外壳一剖开，裸露的塔心柱会被 14000W 冷白
# 柔光直接照成白骨；入夜后也不该留着白天般的冷补光。按拍收放。
FORM = [o for o in bpy.data.objects
        if o.type == "LIGHT" and o.name.startswith("Dusk_Form_High")]
for o in FORM:
    base = o.data.energy
    for fr, k in [(1, 1.0), (fCut - 1, 1.0), (fCut, 0.08),
                  (fBack - 1, 0.08), (fBack, 0.16), (N, 0.16)]:
        o.data.energy = base * k
        o.data.keyframe_insert(data_path="energy", frame=fr)
    constant(o.data)
print("ANIM_OK form_light=%d (1.0->0.08剖视->0.16夜景)" % len(FORM))


# ── 5. 场景备注与保存 ───────────────────────────────────────────────────
sc["anim_note"] = (
    "22s / 8拍 / %dfps。读 deliverables/animation-beats.json 生成。"
    "相机用 timeline marker 切换；硬重音 3.5s 点灯、11.5s 剖开用 CONSTANT 插值。"
    "主体几何未动；07 动画层可整层删除回到静态主视觉。落版文字在序列后处理叠加。"
) % FPS
sc["anim_beats"] = os.path.relpath(BEATS, ROOT).replace("\\", "/")

bpy.ops.wm.save_as_mainfile(filepath=OUT)
print("ANIM_SAVED", OUT)
print("ANIM_ALL_DONE")
