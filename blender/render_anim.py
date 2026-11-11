"""渲染动画：8 拍代表帧 / 低清序列 / 终版全分辨率序列。

打开 build_animation.py 产出的动画工程，只渲染、不再改动。
环境变量
  ANIM_MODE    stills（默认）| sequence
  ANIM_SRC     输入 .blend，默认 model/lingxiao_tower_scene_anim.blend
  ANIM_SCALE   分辨率百分比，stills 默认 60，sequence 默认 50
  ANIM_SAMPLES EEVEE 采样，stills 默认 48，sequence 默认 16
  ANIM_FRAMES  sequence 模式下可指定 "1-80" 之类分段，默认 1..frame_end
  ANIM_FRAMES_DIR sequence 输出目录，默认 deliverables/anim_frames
"""
import bpy, os, json

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
SRC = os.environ.get("ANIM_SRC", os.path.join(HERE, "lingxiao_tower_scene_anim.blend"))
MODE = os.environ.get("ANIM_MODE", "stills")
SCALE = int(os.environ.get("ANIM_SCALE", "60" if MODE == "stills" else "50"))
SAMPLES = int(os.environ.get("ANIM_SAMPLES", "48" if MODE == "stills" else "16"))
DELIV = os.path.join(ROOT, "deliverables")

bpy.ops.wm.open_mainfile(filepath=SRC)
sc = bpy.context.scene
FPS = sc.render.fps
N = sc.frame_end
F = lambda t: max(1, min(N, int(round(t * FPS)) + 1))

sc.render.resolution_percentage = SCALE
try:
    sc.eevee.taa_render_samples = SAMPLES
except Exception:
    pass
sc.render.image_settings.file_format = "PNG"
sc.render.image_settings.color_mode = "RGB"

BEATS = [
    (1.5,  "01 起 · 静"),
    (3.7,  "02 重音① · 点灯"),
    (6.0,  "03 递 · 逐层点灯"),
    (9.5,  "04 动 · 推近斗拱"),
    (11.7, "05 重音② · 剖开"),
    (14.2, "06 递 · 扒梁"),
    (17.5, "07 放 · 回全景"),
    (20.5, "08 收 · 定格"),
]

if MODE == "stills":
    for idx, (t, name) in enumerate(BEATS, start=1):
        f = F(t)
        sc.frame_set(f)
        out = os.path.join(HERE, "_anim_beat_%02d.png" % idx)
        sc.render.filepath = out
        bpy.ops.render.render(write_still=True)
        print("ANIM_STILL", f, round(t, 2), name, "cam", sc.camera.name, "->", out)
    print("ANIM_STILLS_DONE")

elif MODE == "sequence":
    outdir = os.environ.get("ANIM_FRAMES_DIR", os.path.join(DELIV, "anim_frames"))
    os.makedirs(outdir, exist_ok=True)
    rng = os.environ.get("ANIM_FRAMES", "")
    if rng:
        a, b = rng.split("-")
        f0, f1 = int(a), int(b)
    else:
        f0, f1 = 1, N
    for f in range(f0, f1 + 1):
        sc.frame_set(f)
        sc.render.filepath = os.path.join(outdir, "frame_%04d.png" % f)
        bpy.ops.render.render(write_still=True)
        if f == f0 or f % 24 == 0 or f == f1:
            print("ANIM_SEQ", f, "/", f1, "cam", sc.camera.name, flush=True)
    print("ANIM_SEQ_DONE", f0, f1)

print("ANIM_RENDER_DONE")
