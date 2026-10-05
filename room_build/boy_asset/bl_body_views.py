"""Body views for the clothes repaint (Blender 4.2, headless), the same idea as bl_views.py for the face:
    blender -b -P bl_body_views.py -- render    unlit full-body renders (colour atlases as emission) from four cameras
                                                 (front, back, left, right) at 1536 px into work/body/, + cameras.json
    blender -b -P bl_body_views.py -- project   world position / normal bakes of the CLOTH atlas (2048) and the skin atlas,
                                                 and a depth map per camera, for project_paint.py --body
"""
import bpy, os, sys, json, math
import numpy as np
from mathutils import Vector, Matrix

HERE = os.path.dirname(os.path.abspath(__file__)); WORK = os.path.join(HERE, "work"); OUT = os.path.join(HERE, "out")
VIEWS = os.path.join(WORK, "body"); os.makedirs(VIEWS, exist_ok=True)
mode = sys.argv[sys.argv.index("--") + 1]
RES = 1536

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
scene.view_settings.view_transform = "Standard"; scene.view_settings.look = "None"

skin_img = bpy.data.images.load(os.path.join(OUT, "tex_skin.png")); skin_img.colorspace_settings.name = "sRGB"
hair_img = bpy.data.images.load(os.path.join(OUT, "tex_hair.png")); hair_img.colorspace_settings.name = "sRGB"
cloth_img = bpy.data.images.load(os.path.join(OUT, "tex_cloth.png")); cloth_img.colorspace_settings.name = "sRGB"
by_slot = {"boy_skin": skin_img, "boy_hair": hair_img}
for mat in m.materials:
    img = by_slot.get(mat.name, cloth_img); nt = mat.node_tree; nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputMaterial"); em = nt.nodes.new("ShaderNodeEmission"); t = nt.nodes.new("ShaderNodeTexImage"); t.image = img
    nt.links.new(t.outputs[0], em.inputs[0]); nt.links.new(em.outputs[0], out.inputs[0])
    if mat.name == "boy_skin":
        mix = nt.nodes.new("ShaderNodeMixRGB"); mix.inputs[1].default_value = (0.9, 0.88, 0.86, 1); nt.links.new(t.outputs[1], mix.inputs[0]); nt.links.new(t.outputs[0], mix.inputs[2]); nt.links.new(mix.outputs[0], em.inputs[0])

bb = [me.matrix_world @ Vector(c) for c in me.bound_box]
lo = Vector((min(v.x for v in bb), min(v.y for v in bb), min(v.z for v in bb))); hi = Vector((max(v.x for v in bb), max(v.y for v in bb), max(v.z for v in bb)))
centre = (lo + hi) / 2; height = hi.z - lo.z
def bone_head(name): return arm.matrix_world @ arm.data.bones[name].head_local
H = bone_head("Head"); HF = bone_head("headfront"); fwd = (HF - H); fwd.z = 0; fwd.normalize()
CAMS = {"front": 0.0, "back": math.pi, "left": math.radians(90), "right": math.radians(-90)}
def place_camera(name, yaw):
    d = Matrix.Rotation(yaw, 4, "Z") @ fwd
    cam_data = bpy.data.cameras.new(name); cam_data.lens = 85; cam_data.sensor_width = 36; cam_data.clip_start = 0.1
    cam = bpy.data.objects.new(name, cam_data); scene.collection.objects.link(cam)
    dist = height * 1.25 * cam_data.lens / cam_data.sensor_width            # the body fills ~80 % of the frame height
    cam.location = centre + d * dist
    cam.rotation_euler = (centre - cam.location).to_track_quat("-Z", "Y").to_euler()
    return cam

if mode == "render":
    meta = {"height": height, "centre": list(centre)}
    for name, yaw in CAMS.items():
        cam = place_camera(name, yaw); scene.camera = cam; bpy.context.view_layer.update()
        scene.render.filepath = os.path.join(VIEWS, name + ".png"); bpy.ops.render.render(write_still=True)
        meta[name] = {"matrix_world": [list(r) for r in cam.matrix_world], "lens": cam.data.lens, "sensor": cam.data.sensor_width}
        print("rendered", name)
    json.dump(meta, open(os.path.join(VIEWS, "cameras.json"), "w"), indent=1)

elif mode == "project":
    meta = json.load(open(os.path.join(VIEWS, "cameras.json")))
    def bake_emit(vec_socket_builder, name, slots, S):
        target = bpy.data.images.new(name, S, S, alpha=False, float_buffer=True); target.colorspace_settings.name = "Non-Color"
        for i, mt in enumerate(m.materials):
            nt = mt.node_tree; nt.nodes.clear()
            out = nt.nodes.new("ShaderNodeOutputMaterial"); em = nt.nodes.new("ShaderNodeEmission")
            nt.links.new(vec_socket_builder(nt), em.inputs[0]); nt.links.new(em.outputs[0], out.inputs[0])
            tn = nt.nodes.new("ShaderNodeTexImage"); tn.image = target if mt.name in slots else bpy.data.images.new("junk_%s_%d" % (name, i), 8, 8); nt.nodes.active = tn
        bpy.ops.object.select_all(action="DESELECT"); me.select_set(True); bpy.context.view_layer.objects.active = me
        scene.render.bake.use_selected_to_active = False; scene.cycles.samples = 1
        bpy.ops.object.bake(type="EMIT", use_clear=True, margin=2)
        return np.array(target.pixels[:], dtype=np.float32).reshape(S, S, 4)[:, :, :3]
    def pos_builder(nt):
        geo = nt.nodes.new("ShaderNodeNewGeometry"); vm = nt.nodes.new("ShaderNodeVectorMath"); vm.operation = "MULTIPLY_ADD"
        nt.links.new(geo.outputs["Position"], vm.inputs[0]); vm.inputs[1].default_value = (0.25, 0.25, 0.25); vm.inputs[2].default_value = (0.5, 0.5, 0.5)
        return vm.outputs[0]
    def nrm_builder(nt):
        geo = nt.nodes.new("ShaderNodeNewGeometry"); vm = nt.nodes.new("ShaderNodeVectorMath"); vm.operation = "MULTIPLY_ADD"
        nt.links.new(geo.outputs["Normal"], vm.inputs[0]); vm.inputs[1].default_value = (0.5, 0.5, 0.5); vm.inputs[2].default_value = (0.5, 0.5, 0.5)
        return vm.outputs[0]
    CLOTH = {"boy_hoodie", "boy_pants", "boy_socks", "boy_slides"}
    P = (bake_emit(pos_builder, "wpos_c", CLOTH, 2048) - 0.5) * 4.0; N = bake_emit(nrm_builder, "wnrm_c", CLOTH, 2048) * 2 - 1
    np.save(os.path.join(VIEWS, "wpos_cloth.npy"), P); np.save(os.path.join(VIEWS, "wnrm_cloth.npy"), N)
    P = (bake_emit(pos_builder, "wpos_s", {"boy_skin"}, 2048) - 0.5) * 4.0; N = bake_emit(nrm_builder, "wnrm_s", {"boy_skin"}, 2048) * 2 - 1
    np.save(os.path.join(VIEWS, "wpos_skin.npy"), P); np.save(os.path.join(VIEWS, "wnrm_skin.npy"), N)
    print("baked world position / normal of the cloth and skin atlases")
    scene.use_nodes = True; scene.view_layers[0].use_pass_z = True; scene.cycles.samples = 1
    tree = scene.node_tree; tree.nodes.clear(); rl = tree.nodes.new("CompositorNodeRLayers"); fo = tree.nodes.new("CompositorNodeOutputFile")
    fo.base_path = VIEWS; fo.format.file_format = "OPEN_EXR"; fo.format.color_depth = "32"
    tree.links.new(rl.outputs["Depth"], fo.inputs[0])
    for name, yaw in CAMS.items():
        cam = place_camera(name + "_d", yaw); cam.matrix_world = Matrix(meta[name]["matrix_world"]); scene.camera = cam; bpy.context.view_layer.update()
        fo.file_slots[0].path = "depth_" + name + "_"; scene.render.filepath = os.path.join(VIEWS, "junk_"); bpy.ops.render.render(write_still=False)
        exr = [f for f in os.listdir(VIEWS) if f.startswith("depth_" + name + "_") and f.endswith(".exr")][0]
        img = bpy.data.images.load(os.path.join(VIEWS, exr)); d = np.array(img.pixels[:], dtype=np.float32).reshape(RES, RES, 4)[:, :, 0]
        np.save(os.path.join(VIEWS, "depth_" + name + ".npy"), d[::-1]); print("depth", name)
