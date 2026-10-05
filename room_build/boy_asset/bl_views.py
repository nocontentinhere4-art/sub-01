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
    # per camera: a depth pass (Z, EXR through the compositor) and the atlas texels' world position + normal (EMIT bakes);
    # the actual projection, depth test and blending happen in numpy (project_paint.py), where every step can be checked
    meta = json.load(open(os.path.join(VIEWS, "cameras.json")))
    S = 2048
    def bake_emit(vec_socket_builder, name):
        """bake an emission of a vector into a float atlas, skin slot only"""
        skin_slot = [i for i, mt in enumerate(m.materials) if mt.name == "boy_skin"][0]
        target = bpy.data.images.new(name, S, S, alpha=False, float_buffer=True); target.colorspace_settings.name = "Non-Color"
        for i, mt in enumerate(m.materials):
            nt = mt.node_tree; nt.nodes.clear()
            out = nt.nodes.new("ShaderNodeOutputMaterial"); em = nt.nodes.new("ShaderNodeEmission")
            nt.links.new(vec_socket_builder(nt), em.inputs[0]); nt.links.new(em.outputs[0], out.inputs[0])
            tn = nt.nodes.new("ShaderNodeTexImage"); tn.image = target if i == skin_slot else bpy.data.images.new("junk_%d" % i, 8, 8); nt.nodes.active = tn
        bpy.ops.object.select_all(action="DESELECT"); me.select_set(True); bpy.context.view_layer.objects.active = me
        scene.render.bake.use_selected_to_active = False; scene.cycles.samples = 1
        bpy.ops.object.bake(type="EMIT", use_clear=True, margin=2)
        return np.array(target.pixels[:], dtype=np.float32).reshape(S, S, 4)[:, :, :3]
    def pos_builder(nt):
        geo = nt.nodes.new("ShaderNodeNewGeometry"); vm = nt.nodes.new("ShaderNodeVectorMath"); vm.operation = "MULTIPLY_ADD"
        nt.links.new(geo.outputs["Position"], vm.inputs[0]); vm.inputs[1].default_value = (0.25, 0.25, 0.25); vm.inputs[2].default_value = (0.5, 0.5, 0.5)   # metres: -2..2 -> 0..1
        return vm.outputs[0]
    def nrm_builder(nt):
        geo = nt.nodes.new("ShaderNodeNewGeometry"); vm = nt.nodes.new("ShaderNodeVectorMath"); vm.operation = "MULTIPLY_ADD"
        nt.links.new(geo.outputs["Normal"], vm.inputs[0]); vm.inputs[1].default_value = (0.5, 0.5, 0.5); vm.inputs[2].default_value = (0.5, 0.5, 0.5)
        return vm.outputs[0]
    P = (bake_emit(pos_builder, "wpos") - 0.5) * 4.0; N = bake_emit(nrm_builder, "wnrm") * 2 - 1
    np.save(os.path.join(VIEWS, "wpos.npy"), P); np.save(os.path.join(VIEWS, "wnrm.npy"), N); print("baked world position / normal of the skin atlas")
    # depth per camera: Z pass to an EXR through the compositor
    scene.use_nodes = True; scene.view_layers[0].use_pass_z = True; scene.cycles.samples = 1
    tree = scene.node_tree; tree.nodes.clear(); rl = tree.nodes.new("CompositorNodeRLayers"); fo = tree.nodes.new("CompositorNodeOutputFile")
    fo.base_path = VIEWS; fo.format.file_format = "OPEN_EXR"; fo.format.color_depth = "32"; fo.file_slots[0].path = "depth_"
    tree.links.new(rl.outputs["Depth"], fo.inputs[0])
    for name, yaw in CAMS.items():
        cam = place_camera(name + "_d", yaw); cam.matrix_world = Matrix(meta[name]["matrix_world"]); scene.camera = cam; bpy.context.view_layer.update()
        fo.file_slots[0].path = "depth_" + name + "_"; scene.render.filepath = os.path.join(VIEWS, "junk_"); bpy.ops.render.render(write_still=False)
        exr = [f for f in os.listdir(VIEWS) if f.startswith("depth_" + name + "_") and f.endswith(".exr")][0]
        img = bpy.data.images.load(os.path.join(VIEWS, exr)); d = np.array(img.pixels[:], dtype=np.float32).reshape(RES, RES, 4)[:, :, 0]
        np.save(os.path.join(VIEWS, "depth_" + name + ".npy"), d[::-1]); print("depth", name, "range %.2f..%.2f" % (d[d < 1e9].min(), d[d < 1e9].max()))
