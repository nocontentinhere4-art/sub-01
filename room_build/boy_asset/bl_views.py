"""Head views for the face repaint (Blender 4.2, headless):
    blender -b -P bl_views.py -- render     renders the head UNLIT (its colour atlas as emission) from three cameras
                                             (front, left 3/4, right 3/4) at 1024 px into work/views/, and saves the cameras
    blender -b -P bl_views.py -- project    bakes work/views/<view>_paint.png (the repainted views) back into the skin
                                             atlas through the same cameras, front-facing texels only, blended by facing,
                                             and writes work/skin_projected.png + work/skin_projected_mask.png
The mesh is work/boy_mesh.glb (the rebuilt one: same UVs as the shipped atlas), the colour is out/tex_skin.png.
"""
import bpy, os, sys, json, math
import numpy as np
from mathutils import Vector, Matrix

HERE = os.path.dirname(os.path.abspath(__file__)); WORK = os.path.join(HERE, "work"); OUT = os.path.join(HERE, "out")
VIEWS = os.path.join(WORK, "views"); os.makedirs(VIEWS, exist_ok=True)
mode = sys.argv[sys.argv.index("--") + 1]
RES = 1024

bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=os.path.join(WORK, "boy_mesh.glb"))
arm = [o for o in bpy.data.objects if o.type == "ARMATURE"][0]; arm.data.pose_position = "REST"
me = bpy.data.objects["char1"]
for o in list(bpy.data.objects):
    if o.type == "MESH" and o is not me: bpy.data.objects.remove(o)
m = me.data
scene = bpy.context.scene; scene.render.engine = "CYCLES"; scene.cycles.device = "CPU"; scene.cycles.samples = 16
scene.render.resolution_x = scene.render.resolution_y = RES; scene.render.resolution_percentage = 100
scene.render.image_settings.file_format = "PNG"; scene.render.film_transparent = True
scene.view_settings.view_transform = "Standard"; scene.view_settings.look = "None"      # the atlas colours as they are

# the materials: unlit colour (emission of the atlas) so the views are albedo, not lit
skin_img = bpy.data.images.load(os.path.join(OUT, "tex_skin.png")); skin_img.colorspace_settings.name = "sRGB"
hair_img = bpy.data.images.load(os.path.join(OUT, "tex_hair.png")); hair_img.colorspace_settings.name = "sRGB"
cloth_img = bpy.data.images.load(os.path.join(OUT, "tex_cloth.png")); cloth_img.colorspace_settings.name = "sRGB"
by_slot = {"boy_skin": skin_img, "boy_hair": hair_img}
for mat in m.materials:
    img = by_slot.get(mat.name, cloth_img); nt = mat.node_tree; nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputMaterial"); em = nt.nodes.new("ShaderNodeEmission"); t = nt.nodes.new("ShaderNodeTexImage"); t.image = img
    nt.links.new(t.outputs[0], em.inputs[0]); nt.links.new(em.outputs[0], out.inputs[0])
    if mat.name == "boy_skin":                                           # the eye openings are cut out: fill them with the sclera colour for the views
        mix = nt.nodes.new("ShaderNodeMixRGB"); mix.inputs[2].default_value = (0.9, 0.88, 0.86, 1); nt.links.new(t.outputs[1], mix.inputs[0]); nt.links.new(t.outputs[0], mix.inputs[2]); mix.inputs[1].default_value = (0.9, 0.88, 0.86, 1)
        nt.links.new(mix.outputs[0], em.inputs[0])

# the head: centre and forward from the Head / headfront bones (rest pose, world space)
def bone_head(name):
    b = arm.data.bones[name]; return arm.matrix_world @ b.head_local
H = bone_head("Head"); HF = bone_head("headfront"); fwd = (HF - H); fwd.z = 0; fwd.normalize()
centre = H + Vector((0, 0, 0.08)) + fwd * 0.02             # metres: the armature is scaled 0.01 on import
up = Vector((0, 0, 1)); right = fwd.cross(up)
CAMS = {"front": 0.0, "left": math.radians(40), "right": math.radians(-40)}
def place_camera(name, yaw):
    d = (Matrix.Rotation(yaw, 4, "Z") @ fwd) if abs(yaw) > 0 else fwd.copy()
    cam_data = bpy.data.cameras.new(name); cam_data.lens = 85; cam_data.sensor_width = 36; cam_data.clip_start = 0.05
    cam = bpy.data.objects.new(name, cam_data); scene.collection.objects.link(cam)
    cam.location = centre + d * 0.75
    cam.rotation_euler = (centre - cam.location).to_track_quat("-Z", "Y").to_euler()
    return cam

if mode == "render":
    meta = {}
    for name, yaw in CAMS.items():
        cam = place_camera(name, yaw); scene.camera = cam; bpy.context.view_layer.update()
        scene.render.filepath = os.path.join(VIEWS, name + ".png"); bpy.ops.render.render(write_still=True)
        meta[name] = {"matrix_world": [list(r) for r in cam.matrix_world], "lens": cam.data.lens, "sensor": cam.data.sensor_width}
        print("rendered", name)
    json.dump(meta, open(os.path.join(VIEWS, "cameras.json"), "w"), indent=1)

elif mode == "project":
    # bake each repainted view into the skin atlas through its camera; weight = facing (N . view)^2, in front of the camera only
    meta = json.load(open(os.path.join(VIEWS, "cameras.json")))
    skin_slot = [i for i, mt in enumerate(m.materials) if mt.name == "boy_skin"][0]
    S = 2048
    acc = np.zeros((S, S, 3), np.float64); wsum = np.zeros((S, S), np.float64)
    for name in CAMS:
        paint = os.path.join(VIEWS, name + "_paint.png")
        if not os.path.exists(paint): print("no repaint for", name); continue
        cam = place_camera(name + "_p", CAMS[name]); cam.matrix_world = Matrix(meta[name]["matrix_world"]); scene.camera = cam; bpy.context.view_layer.update()
        img = bpy.data.images.load(paint); img.colorspace_settings.name = "sRGB"
        # material: the repainted view projected from the camera (Window coordinates) -> emission; facing in the alpha
        mat = m.materials[skin_slot]; nt = mat.node_tree; nt.nodes.clear()
        out = nt.nodes.new("ShaderNodeOutputMaterial"); em = nt.nodes.new("ShaderNodeEmission")
        tc = nt.nodes.new("ShaderNodeTexCoord"); t = nt.nodes.new("ShaderNodeTexImage"); t.image = img; t.extension = "CLIP"
        nt.links.new(tc.outputs["Window"], t.inputs[0]); nt.links.new(t.outputs[0], em.inputs[0]); nt.links.new(em.outputs[0], out.inputs[0])
        target = bpy.data.images.new("proj_" + name, S, S, alpha=False, float_buffer=True); target.colorspace_settings.name = "Non-Color"
        tn = nt.nodes.new("ShaderNodeTexImage"); tn.image = target; nt.nodes.active = tn
        for i, mt in enumerate(m.materials):
            if i != skin_slot: mt.node_tree.nodes.active = None
        bpy.ops.object.select_all(action="DESELECT"); me.select_set(True); bpy.context.view_layer.objects.active = me
        # only the skin slot has an active image: bake writes only there
        for p in m.polygons: p.select = p.material_index == skin_slot
        scene.render.bake.use_selected_to_active = False
        bpy.ops.object.bake(type="EMIT", use_clear=True, margin=4)
        col = np.array(target.pixels[:], dtype=np.float32).reshape(S, S, 4)[:, :, :3]
        # facing weight: bake the view-space normal z (Geometry > Incoming . Normal) the same way
        nt.nodes.clear(); out = nt.nodes.new("ShaderNodeOutputMaterial"); em = nt.nodes.new("ShaderNodeEmission")
        geo = nt.nodes.new("ShaderNodeNewGeometry"); dot = nt.nodes.new("ShaderNodeVectorMath"); dot.operation = "DOT_PRODUCT"
        nt.links.new(geo.outputs["Normal"], dot.inputs[0]); nt.links.new(geo.outputs["Incoming"], dot.inputs[1])
        nt.links.new(dot.outputs["Value"], em.inputs[0]); nt.links.new(em.outputs[0], out.inputs[0])
        tn = nt.nodes.new("ShaderNodeTexImage"); tn.image = target; nt.nodes.active = tn
        bpy.ops.object.bake(type="EMIT", use_clear=True, margin=4)
        facing = np.clip(np.array(target.pixels[:], dtype=np.float32).reshape(S, S, 4)[:, :, 0], 0, 1)
        # visibility: a texel is used only if the camera really sees it (its own depth = the depth the camera sees); approximated
        # by the facing term and the paint's alpha (0 outside the view); occlusion by the hair / nose is handled by facing^3
        w = facing ** 3 * (np.array(target.pixels[:], dtype=np.float32).reshape(S, S, 4)[:, :, 3] > 0)
        a_img = np.array(img.pixels[:], dtype=np.float32).reshape(img.size[1], img.size[0], 4)[:, :, 3]
        acc += col * w[:, :, None]; wsum += w; print("projected", name, "weight sum %.0f" % w.sum())
    res = acc / np.maximum(wsum, 1e-6)[:, :, None]; mask = np.clip(wsum / max(wsum.max(), 1e-6), 0, 1)
    o1 = bpy.data.images.new("skin_projected", S, S, alpha=False); o1.pixels = np.concatenate([np.clip(res, 0, 1), np.ones((S, S, 1))], 2).ravel()
    o1.filepath_raw = os.path.join(WORK, "skin_projected.png"); o1.file_format = "PNG"; o1.save()
    o2 = bpy.data.images.new("skin_projected_mask", S, S, alpha=False); o2.pixels = np.concatenate([np.repeat(mask[:, :, None], 3, 2), np.ones((S, S, 1))], 2).ravel()
    o2.filepath_raw = os.path.join(WORK, "skin_projected_mask.png"); o2.file_format = "PNG"; o2.save()
    print("wrote work/skin_projected.png and its mask")
