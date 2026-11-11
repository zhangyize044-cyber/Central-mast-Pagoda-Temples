# -*- coding: utf-8 -*-
"""R2 正式成片归档：双机位全分辨率渲染（不回存 .blend）"""
import bpy, os

HERE = os.path.dirname(os.path.abspath(__file__))
SHOTS = os.path.normpath(os.path.join(HERE, "..", "shots"))
bpy.ops.wm.open_mainfile(filepath=os.path.join(HERE, "lingxiao_tower_scene_snow_r2.blend"))
sc = bpy.context.scene
sc.frame_set(1)
sc.render.resolution_percentage = 100
try:
    sc.eevee.taa_render_samples = 96
except Exception:
    pass

for i, (cam_name, out) in enumerate((
        ("Cam_01 全景", "18-snow-r2-full.png"),
        ("Cam_02 塔院", "19-snow-r2-courtyard.png")), 1):
    cam = bpy.data.objects.get(cam_name)
    if not cam:
        print("ARCHIVE_SKIP", cam_name)
        continue
    sc.camera = cam
    sc.render.filepath = os.path.join(SHOTS, out)
    bpy.ops.render.render(write_still=True)
    print("ARCHIVE_DONE", sc.render.filepath)
print("ARCHIVE_ALL_DONE")
