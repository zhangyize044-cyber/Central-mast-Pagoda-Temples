"""渲染开场 Reveal 的 8 个代表时刻（12 fps 低清小样），只渲不改文件。

环境变量
  REVEAL_SCALE    分辨率百分比，默认 60
  REVEAL_SAMPLES  EEVEE 采样，默认 24
"""
import bpy, os

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
SRC = os.path.join(HERE, "lingxiao_tower_scene_anim_reveal.blend")
SCALE = int(os.environ.get("REVEAL_SCALE", "60"))
SAMPLES = int(os.environ.get("REVEAL_SAMPLES", "24"))
OUTDIR = os.path.join(ROOT, "deliverables", "anim_stills")
os.makedirs(OUTDIR, exist_ok=True)

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

MOMENTS = [
    (0.00, "01 黑场 · 未显"),
    (0.35, "02 心柱生长"),
    (0.90, "03 扒梁张开"),
    (1.50, "04 八梁齐备"),
    (1.85, "05 外壳显形 · 下层冷光"),
    (2.20, "06 九级照出"),
    (2.90, "07 黄昏全景定住"),
    (3.60, "08 重音① 点灯"),
]
for i, (t, name) in enumerate(MOMENTS, start=1):
    f = F(t)
    sc.frame_set(f)
    out = os.path.join(OUTDIR, "_reveal_%02d.png" % i)
    sc.render.filepath = out
    bpy.ops.render.render(write_still=True)
    print("REVEAL_STILL", i, "f", f, "t", t, name, "cam", sc.camera.name, flush=True)
print("REVEAL_STILLS_DONE", len(MOMENTS))
