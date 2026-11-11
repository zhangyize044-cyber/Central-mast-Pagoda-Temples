# -*- coding: utf-8 -*-
"""把落版后的 PNG 序列与原创配乐合成带音轨的 H.264 MP4。

外部 ffmpeg 在本机是 0 字节空壳，仍走 Blender 内置 libavcodec / VSE。
    ANIM_FRAMES_DIR=... ANIM_SCORE=... blender -b --python model/encode_with_audio.py
输出 deliverables/anim_scored0001-0528.mp4，由宿主重命名为交付名。
"""
import os
import bpy

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
FRAMES = os.environ.get(
    "ANIM_FRAMES_DIR",
    os.path.join(ROOT, "deliverables", "anim_frames_master_final"))
SCORE = os.environ.get(
    "ANIM_SCORE",
    os.path.join(ROOT, "deliverables", "13-配乐-正定凌霄塔.wav"))
OUT = os.path.join(ROOT, "deliverables", "anim_scored")
W = int(os.environ.get("ANIM_W", "1600"))
H = int(os.environ.get("ANIM_H", "900"))
FPS = int(os.environ.get("ANIM_FPS", "24"))
N = int(os.environ.get("ANIM_N", "528"))

assert os.path.exists(SCORE), "缺配乐 " + SCORE

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

st = strips.new_image(name="凌霄塔展示短片", filepath=first,
                      channel=1, frame_start=1)
missing = []
for i in range(2, N + 1):
    name = "frame_%04d.png" % i
    if not os.path.exists(os.path.join(FRAMES, name)):
        missing.append(name)
        continue
    st.elements.append(name)
assert not missing, "缺帧 %d 个，例：%s" % (len(missing), missing[:5])

snd = strips.new_sound(name="原创配乐 · 钟磬鼓", filepath=SCORE,
                       channel=2, frame_start=1)
dur_frames = getattr(snd, "frame_duration", None) or \
    getattr(snd, "frame_final_duration", N)
print("SOUND_STRIP frames=%d duration=%.3f" %
      (dur_frames, dur_frames / float(FPS)))

sc.render.image_settings.file_format = "FFMPEG"
ff = sc.render.ffmpeg
ff.format = "MPEG4"
ff.codec = "H264"
ff.constant_rate_factor = "HIGH"
ff.ffmpeg_preset = "GOOD"
ff.audio_codec = "AAC"
if hasattr(ff, "audio_bitrate"):
    ff.audio_bitrate = 192
if hasattr(ff, "audio_mixrate"):
    ff.audio_mixrate = 48000
if hasattr(ff, "audio_channels"):
    try:
        ff.audio_channels = "STEREO"
    except Exception:
        pass
if hasattr(ff, "audio_volume"):
    ff.audio_volume = 1.0
sc.render.filepath = OUT
bpy.ops.render.render(animation=True)
print("ENCODE_WITH_AUDIO_DONE", OUT)
