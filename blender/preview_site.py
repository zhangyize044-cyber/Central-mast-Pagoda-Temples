# -*- coding: utf-8 -*-
"""院落环境预览：多机位渲染，检查布局与比例"""
import bpy
import math
import os
import mathutils

OUT = os.path.dirname(os.path.abspath(__file__))
bpy.ops.wm.open_mainfile(filepath=os.path.join(OUT, "lingxiao_tower.blend"))

# 追加 site.blend 的全部物体
site_blend = os.path.join(OUT, "site.blend")
with bpy.data.libraries.load(site_blend, link=False) as (src, dst):
    dst.objects = src.objects
for ob in dst.objects:
    if ob is not None:
        bpy.context.collection.objects.link(ob)

sc = bpy.context.scene

world = bpy.data.worlds.new("W")
sc.world = world
world.use_nodes = True
nt = world.node_tree
bg = next((n for n in nt.nodes if n.type == "BACKGROUND"), None)
bg.inputs[0].default_value = (0.165, 0.110, 0.075, 1.0)
bg.inputs[1].default_value = 1.0

# 三向平行光：主光低角度长影，补光冷，轮廓光暖
def add_sun(name, energy, color, rx, rz, ang=6.0):
    d = bpy.data.lights.new(name, type='SUN')
    d.energy = energy
    d.angle = math.radians(ang)
    d.color = color
    o = bpy.data.objects.new(name, d)
    bpy.context.collection.objects.link(o)
    o.rotation_euler = (math.radians(rx), 0, math.radians(rz))
    return o


add_sun("Key", 3.1, (1.00, 0.86, 0.70), 30, 32)
add_sun("Fill", 0.95, (0.58, 0.72, 1.00), 64, -142)
add_sun("Rim", 1.30, (1.00, 0.70, 0.42), 74, 196)

cam_data = bpy.data.cameras.new("Cam")
cam_data.lens = 42
cam = bpy.data.objects.new("Cam", cam_data)
bpy.context.collection.objects.link(cam)
sc.camera = cam

sc.render.engine = 'BLENDER_EEVEE_NEXT'
sc.render.resolution_x = 1280
sc.render.resolution_y = 860
sc.render.film_transparent = False
sc.eevee.taa_render_samples = 24
sc.view_settings.view_transform = 'Standard'
sc.view_settings.exposure = 1.05

SHOTS = [
    ("_v1_axis", (0, 196, 46), (0, 30, 13), 48),
    ("_v2_bird", (126, 140, 104), (0, 16, 5), 36),
    ("_v3_tower", (62, 56, 22), (0, 4, 19), 48),
    ("_v4_gate", (-56, 96, 28), (0, 44, 9), 42),
    ("_v5_web", (45, 57, 26), (0, 19, 0), 29),
    ("_v6_high", (58, 86, 44), (0, 16, 0), 40),
    ("_v7_bridge", (17, 88, 6.5), (0, 70, 3.0), 44),
    ("_d1_gate", (0, 77, 7.0), (0, 60, 5.0), 46),
    ("_d2_roof", (13, 46, 15.0), (0, 33, 10.5), 62),
    ("_d3_rear", (9, -12, 6.5), (0, -29, 6.0), 52),
    ("_d4_court", (20, 47, 10.0), (0, 36, 2.0), 42),
    ("_d5_wall", (12.5, 31.5, 2.4), (5.4, 36.8, 2.2), 50),
]

for name, pos, tgt, lens in SHOTS:
    cam.location = pos
    cam_data.lens = lens
    d = mathutils.Vector(tgt) - mathutils.Vector(pos)
    cam.rotation_euler = d.to_track_quat('-Z', 'Y').to_euler()
    sc.render.filepath = os.path.join(OUT, name + ".png")
    bpy.ops.render.render(write_still=True)
    print("RENDERED", name)

print("PREVIEW_SITE_DONE")
