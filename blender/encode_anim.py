"""用 Blender 内置 FFmpeg 把 PNG 序列编码成 H264 MP4。

外部 ffmpeg 在本机是 0 字节空壳，Blender 自带 libavcodec 可用。
输入：deliverables/anim_frames_final/frame_0001..0264.png
输出：deliverables/anim_preview.mp4（脚本不追加帧号，文件名由宿主重命名）
"""
import bpy, os

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
FRAMES = os.environ.get(
    "ANIM_FRAMES_DIR",
    os.path.join(ROOT, "deliverables", "anim_frames_final"))
OUT = os.path.join(ROOT, "deliverables", "anim_preview")
W = int(os.environ.get("ANIM_W", "800"))
H = int(os.environ.get("ANIM_H", "500"))
FPS = int(os.environ.get("ANIM_FPS", "12"))
N = int(os.environ.get("ANIM_N", "264"))

bpy.ops.wm.read_factory_settings(use_empty=True)
sc = bpy.context.scene
sc.render.resolution_x = W
sc.render.resolution_y = H
sc.render.resolution_percentage = 100
sc.render.fps = FPS
sc.frame_start = 1
sc.frame_end = N
sc.render.use_sequencer = True

se = sc.sequence_editor_create()
strips = getattr(se, "strips", None) or getattr(se, "sequences", None)
first = os.path.join(FRAMES, "frame_0001.png")
assert os.path.exists(first), "缺首帧 " + first
st = strips.new_image(name="凌霄塔展示短片", filepath=first, channel=1, frame_start=1)
missing = []
for i in range(2, N + 1):
    name = "frame_%04d.png" % i
    if not os.path.exists(os.path.join(FRAMES, name)):
        missing.append(name)
        continue
    st.elements.append(name)
assert not missing, "缺帧 %d 个，例：%s" % (len(missing), missing[:5])
print("ENCODE_OK frames=%d" % (len(st.elements)))

sc.render.image_settings.file_format = "FFMPEG"
sc.render.ffmpeg.format = "MPEG4"
sc.render.ffmpeg.codec = "H264"
sc.render.ffmpeg.constant_rate_factor = "HIGH"
sc.render.ffmpeg.ffmpeg_preset = "GOOD"
sc.render.ffmpeg.audio_codec = "NONE"
sc.render.filepath = OUT
bpy.ops.render.render(animation=True)
print("ENCODE_DONE", OUT)
