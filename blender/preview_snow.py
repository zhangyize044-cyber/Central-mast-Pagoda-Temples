# -*- coding: utf-8 -*-
"""雪景快速预览：双机位渲染确认积雪 / 飘雪 / 冷调效果（不回存 .blend）"""
import bpy, os

HERE = os.path.dirname(os.path.abspath(__file__))
bpy.ops.wm.open_mainfile(filepath=os.path.join(HERE, "lingxiao_tower_scene_snow.blend"))

sc = bpy.context.scene
sc.frame_set(1)
sc.render.resolution_percentage = 75
try:
    sc.eevee.taa_render_samples = 64
except Exception:
    pass

for i, cam_name in enumerate(("Cam_01 全景", "Cam_02 塔院"), 1):
    cam = bpy.data.objects.get(cam_name)
    if not cam:
        print("PREVIEW_SKIP", cam_name)
        continue
    sc.camera = cam
    sc.render.filepath = os.path.join(HERE, f"_snow_cam{i}.png")
    bpy.ops.render.render(write_still=True)
    print("PREVIEW_DONE", sc.render.filepath)
