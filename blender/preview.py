# -*- coding: utf-8 -*-
"""快速预览渲染：确认塔的比例与细节"""
import bpy, math, os

OUT_DIR = os.path.dirname(os.path.abspath(__file__))
bpy.ops.wm.open_mainfile(filepath=os.path.join(OUT_DIR, "lingxiao_tower.blend"))

sc = bpy.context.scene

# 世界环境：暖棕
world = bpy.data.worlds.new("W")
sc.world = world
world.use_nodes = True
nt = world.node_tree
bg = next((n for n in nt.nodes if n.type == "BACKGROUND"), None)
if bg is None:
    bg = nt.nodes.new("ShaderNodeBackground")
    out = next((n for n in nt.nodes if n.type == "OUTPUT_WORLD"), None) or nt.nodes.new("ShaderNodeOutputWorld")
    nt.links.new(bg.outputs[0], out.inputs[0])
bg.inputs[0].default_value = (0.045, 0.022, 0.014, 1.0)
bg.inputs[1].default_value = 1.0

# 相机
cam_data = bpy.data.cameras.new("Cam")
cam_data.lens = 62
cam = bpy.data.objects.new("Cam", cam_data)
bpy.context.collection.objects.link(cam)
cam.location = (44.0, -62.0, 21.0)
# 指向塔身中部
import mathutils
target = mathutils.Vector((0, 0, 20.0))
direction = target - cam.location
cam.rotation_euler = direction.to_track_quat('-Z', 'Y').to_euler()
sc.camera = cam

# 主光
sun_d = bpy.data.lights.new("Sun", type='SUN')
sun_d.energy = 4.0
sun_d.angle = math.radians(6)
sun_d.color = (1.0, 0.80, 0.58)
sun = bpy.data.objects.new("Sun", sun_d)
bpy.context.collection.objects.link(sun)
sun.rotation_euler = (math.radians(58), 0, math.radians(38))

# 补光
fill_d = bpy.data.lights.new("Fill", type='AREA')
fill_d.energy = 9000
fill_d.size = 30
fill_d.color = (0.45, 0.60, 1.0)
fill = bpy.data.objects.new("Fill", fill_d)
bpy.context.collection.objects.link(fill)
fill.location = (-40, -30, 16)
fill.rotation_euler = (math.radians(80), 0, math.radians(-52))

# 轮廓光
rim_d = bpy.data.lights.new("Rim", type='AREA')
rim_d.energy = 12000
rim_d.size = 18
rim_d.color = (1.0, 0.72, 0.42)
rim = bpy.data.objects.new("Rim", rim_d)
bpy.context.collection.objects.link(rim)
rim.location = (18, 40, 34)
rim.rotation_euler = (math.radians(62), 0, math.radians(160))

sc.render.engine = 'BLENDER_EEVEE_NEXT'
sc.render.resolution_x = 760
sc.render.resolution_y = 1000
sc.render.film_transparent = False
sc.eevee.taa_render_samples = 32

sc.render.filepath = os.path.join(OUT_DIR, "_preview.png")
bpy.ops.render.render(write_still=True)
print("PREVIEW_DONE", sc.render.filepath)
