"""渲染开场 Reveal 的 3.5 s 动态小片段（12 fps / 43 帧低清），供节奏复核。

只渲染、不改文件。输出 deliverables/anim_reveal_frames/frame_0001..0043.png
"""
import bpy, os

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
SRC = os.path.join(HERE, "lingxiao_tower_scene_anim_reveal.blend")
OUTDIR = os.path.join(ROOT, "deliverables", "anim_reveal_frames")
os.makedirs(OUTDIR, exist_ok=True)
SCALE = int(os.environ.get("REVEAL_SEQ_SCALE", "50"))
SAMPLES = int(os.environ.get("REVEAL_SEQ_SAMPLES", "16"))

bpy.ops.wm.open_mainfile(filepath=SRC)
sc = bpy.context.scene
FPS = sc.render.fps
N = max(1, min(sc.frame_end, int(round(3.5 * FPS))))   # 3.5 s = 43 帧 @12fps

sc.render.resolution_percentage = SCALE
try:
    sc.eevee.taa_render_samples = SAMPLES
except Exception:
    pass
sc.render.image_settings.file_format = "PNG"
sc.render.image_settings.color_mode = "RGB"

for f in range(1, N + 1):
    sc.frame_set(f)
    sc.render.filepath = os.path.join(OUTDIR, "frame_%04d.png" % f)
    bpy.ops.render.render(write_still=True)
    if f == 1 or f % 8 == 0 or f == N:
        print("REVEAL_SEQ", f, "/", N, "cam", sc.camera.name, flush=True)
print("REVEAL_SEQ_DONE", N)
