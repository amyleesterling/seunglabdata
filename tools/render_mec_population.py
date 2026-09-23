"""
Blender: the MEC block with many typed cells inside it, coloured by cell type.

Every cell sits at its TRUE position in the volume. The GLBs from
mec_meshes.py carry absolute micrometre coordinates, so the whole population is
parented to one empty and that empty is scaled and centred. Nothing is placed
by eye, and the block wireframe comes from the segmentation's own bounds.

Renders a still, or a turntable sequence for an animation. Labels are added
afterwards by label_frames.py, not burned in here.

Follows D:\\Meshes\\RENDERING_NEURONS.md, with one measured deviation: the
three point rig is off by default because on sub-micrometre neurites it changed
the lit pixel count by 6% against an HDRI alone. Pass --lights 1.0 to restore.

Run:
  blender --background --factory-startup --python tools/render_mec_population.py -- \\
      --cells assets/mec/cells/cells.json --out renders/population \\
      [--frames 240] [--types stellate,pyramidal] [--per-type 8] [--size 1600]
"""

import argparse
import json
import math
import os
import sys

import bpy
import numpy as np
from mathutils import Vector

TARGET_SIZE = 10.0
PCTL = (0.5, 99.5)

# Straight from the segmentation info file.
VOXEL_OFFSET = np.array([76728, 65192, 8])
VOLUME_SIZE = np.array([126968, 83616, 9932])
RESOLUTION_NM = np.array([16, 16, 45])
UM_PER_VOXEL = RESOLUTION_NM / 1000.0
BLOCK_LO = VOXEL_OFFSET * UM_PER_VOXEL
BLOCK_HI = (VOXEL_OFFSET + VOLUME_SIZE) * UM_PER_VOXEL

HDRI = os.path.join(bpy.utils.resource_path("LOCAL"),
                    "datafiles", "studiolights", "world", "studio.exr")
GROUND = (0.0021, 0.0024, 0.0034, 1.0)      # #07080B, linear
BLOCK_RGB = (0.06, 0.42, 0.72)              # #3E96F0 accent, dimmed for the cage

# Amy's house palette, from the CA3 page and scifi-ui.
TYPE_COLOUR = {
    "stellate":        (0.404, 0.961, 0.796),   # #67f5cb mint
    "pyramidal":       (0.243, 0.588, 0.941),   # #3E96F0 accent
    "inhibitory":      (0.910, 0.686, 0.847),   # #e8afd8 orchid
    "microglia":       (0.910, 0.663, 0.227),   # #E8A93A gold
    "astrocyte":       (0.741, 0.608, 0.820),   # #bd9bd1 lilac
    "oligodendrocyte": (0.494, 0.878, 1.000),   # #7ee0ff cyan
    "bipolar":         (0.769, 0.800, 0.847),   # #c4ccd8 steel
}
TYPE_ORDER = ["stellate", "pyramidal", "inhibitory", "astrocyte",
              "oligodendrocyte", "microglia", "bipolar"]


def argv_after_ddash():
    return sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []


def world_pts(obj):
    co = np.empty(len(obj.data.vertices) * 3, dtype=np.float32)
    obj.data.vertices.foreach_get("co", co)
    return co.reshape(-1, 3) @ np.array(obj.matrix_world.to_3x3()).T + \
        np.array(obj.matrix_world.translation)


def import_cell(path):
    before = set(bpy.data.objects)
    bpy.ops.import_scene.gltf(filepath=path)
    new = [o for o in bpy.data.objects if o not in before and o.type == "MESH"]
    if not new:
        return None
    for o in new:
        o.select_set(True)
    bpy.context.view_layer.objects.active = new[0]
    if len(new) > 1:
        bpy.ops.object.join()
    obj = bpy.context.view_layer.objects.active
    bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
    return obj


def material_for(cell_type):
    name = f"type_{cell_type}"
    if name in bpy.data.materials:
        return bpy.data.materials[name]
    rgb = TYPE_COLOUR.get(cell_type, (0.8, 0.8, 0.8))
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes["Principled BSDF"]
    bsdf.inputs["Base Color"].default_value = (*rgb, 1.0)
    bsdf.inputs["Roughness"].default_value = 0.62
    bsdf.inputs["IOR"].default_value = 1.04          # submerged tissue
    for key, value in (("Subsurface Weight", 0.30),
                       ("Subsurface Scale", 0.012 * TARGET_SIZE)):
        if key in bsdf.inputs:
            bsdf.inputs[key].default_value = value
    if "Emission Color" in bsdf.inputs:
        bsdf.inputs["Emission Color"].default_value = (*rgb, 1.0)
    if "Emission Strength" in bsdf.inputs:
        bsdf.inputs["Emission Strength"].default_value = 0.22
    return mat


def block_cage(parent):
    """Wireframe of the imaged block, from its own bounds."""
    lo, hi = BLOCK_LO, BLOCK_HI
    verts = [(x, y, z) for x in (lo[0], hi[0]) for y in (lo[1], hi[1]) for z in (lo[2], hi[2])]
    edges = [(0, 1), (2, 3), (4, 5), (6, 7),
             (0, 2), (1, 3), (4, 6), (5, 7),
             (0, 4), (1, 5), (2, 6), (3, 7)]
    mesh = bpy.data.meshes.new("block")
    mesh.from_pydata(verts, edges, [])
    obj = bpy.data.objects.new("block", mesh)
    bpy.context.collection.objects.link(obj)
    # Wireframe so the cage renders as tubes rather than vanishing: EEVEE will
    # not draw bare edges.
    mod = obj.modifiers.new("wire", "WIREFRAME")
    mod.thickness = 2.2
    mat = bpy.data.materials.new("cage")
    mat.use_nodes = True
    b = mat.node_tree.nodes["Principled BSDF"]
    b.inputs["Base Color"].default_value = (*BLOCK_RGB, 1.0)
    if "Emission Color" in b.inputs:
        b.inputs["Emission Color"].default_value = (*BLOCK_RGB, 1.0)
        b.inputs["Emission Strength"].default_value = 0.9
    obj.data.materials.append(mat)
    obj.parent = parent
    return obj


def light_the_scene(hdri_strength=1.10, light_scale=0.0):
    world = bpy.data.worlds.new("world")
    world.use_nodes = True
    nt = world.node_tree
    bg = nt.nodes["Background"]
    if os.path.exists(HDRI):
        env = nt.nodes.new("ShaderNodeTexEnvironment")
        env.image = bpy.data.images.load(HDRI, check_existing=True)
        nt.links.new(env.outputs["Color"], bg.inputs["Color"])
        bg.inputs[1].default_value = hdri_strength
    else:
        print("    WARNING: studio HDRI not found")
        bg.inputs[0].default_value = GROUND
    bpy.context.scene.world = world
    if light_scale <= 0:
        return
    for name, loc, power, size in (("key", (9, -11, 7), 5200, 12),
                                   ("fill", (-11, -6, 2), 1700, 16),
                                   ("rim", (-3, 10, 8), 2600, 10)):
        data = bpy.data.lights.new(name, type="AREA")
        data.energy = power * light_scale
        data.size = size
        o = bpy.data.objects.new(name, data)
        o.location = loc
        o.rotation_euler = (Vector((0, 0, 0)) - Vector(loc)).to_track_quat("-Z", "Y").to_euler()
        bpy.context.collection.objects.link(o)


def composite_ground(scene):
    scene.use_nodes = True
    nt = scene.node_tree
    nt.nodes.clear()
    rl = nt.nodes.new("CompositorNodeRLayers")
    rgb = nt.nodes.new("CompositorNodeRGB")
    rgb.outputs[0].default_value = GROUND
    over = nt.nodes.new("CompositorNodeAlphaOver")
    out = nt.nodes.new("CompositorNodeComposite")
    for i, n in enumerate((rl, rgb, over, out)):
        n.location = (i * 220, 0)
    nt.links.new(rgb.outputs[0], over.inputs[1])
    nt.links.new(rl.outputs["Image"], over.inputs[2])
    nt.links.new(over.outputs[0], out.inputs[0])


def configure_render(size, samples):
    scene = bpy.context.scene
    scene.render.engine = "BLENDER_EEVEE_NEXT"
    scene.render.resolution_x = size
    scene.render.resolution_y = int(size * 9 / 16)
    scene.render.resolution_percentage = 100
    scene.render.film_transparent = True
    scene.view_settings.view_transform = "Standard"
    ee = scene.eevee
    if hasattr(ee, "use_motion_blur"):
        ee.use_motion_blur = False          # has crashed EEVEE on this machine
    for attr, value in (("taa_render_samples", samples), ("use_gtao", True)):
        if hasattr(ee, attr):
            setattr(ee, attr, value)
    composite_ground(scene)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cells", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--size", type=int, default=1600)
    ap.add_argument("--samples", type=int, default=96)
    ap.add_argument("--tier", default="card")
    ap.add_argument("--per-type", type=int, default=0, help="cap cells per type")
    ap.add_argument("--types", default="", help="comma separated; default all")
    ap.add_argument("--frames", type=int, default=0, help="0 = one still")
    ap.add_argument("--elev", type=float, default=20.0)
    ap.add_argument("--dist", type=float, default=2.25)
    ap.add_argument("--hdri", type=float, default=1.10)
    ap.add_argument("--lights", type=float, default=0.0)
    args = ap.parse_args(argv_after_ddash())

    with open(args.cells) as fh:
        manifest = json.load(fh)
    cells = manifest["cells"]
    if args.types:
        want = {t.strip() for t in args.types.split(",") if t.strip()}
        cells = [c for c in cells if c["cell_type"] in want]
    if args.per_type:
        seen = {}
        kept = []
        for c in cells:
            n = seen.get(c["cell_type"], 0)
            if n < args.per_type:
                kept.append(c)
                seen[c["cell_type"]] = n + 1
        cells = kept

    bpy.ops.wm.read_factory_settings(use_empty=True)
    root = bpy.data.objects.new("root", None)
    bpy.context.collection.objects.link(root)

    mesh_dir = os.path.dirname(os.path.abspath(args.cells))
    loaded, counts = [], {}
    for c in cells:
        tier = c["tiers"].get(args.tier) or next(iter(c["tiers"].values()))
        path = os.path.join(mesh_dir, tier["file"])
        if not os.path.exists(path):
            print(f"  missing {path}, skipping")
            continue
        obj = import_cell(path)
        if obj is None:
            continue
        obj.data.materials.clear()
        obj.data.materials.append(material_for(c["cell_type"]))
        for poly in obj.data.polygons:
            poly.use_smooth = True
        obj.parent = root
        loaded.append((c, obj))
        counts[c["cell_type"]] = counts.get(c["cell_type"], 0) + 1
    if not loaded:
        sys.exit("no cells loaded")
    print(f"loaded {len(loaded)} cells: " +
          ", ".join(f"{t} {counts[t]}" for t in TYPE_ORDER if t in counts))

    cage = block_cage(root)

    # Scale and centre on the BLOCK, not on the cells, so the figure is a
    # statement about the volume and the cells sit where they sit inside it.
    span = BLOCK_HI - BLOCK_LO
    scale = TARGET_SIZE / float(span.max())
    centre = (BLOCK_HI + BLOCK_LO) / 2.0
    root.scale = (scale, scale, scale)
    root.location = tuple(-centre * scale)
    # Data z is the thin axis; lay the slab flat, same convention as the web view.
    root.rotation_euler = (-math.pi / 2, 0, 0)
    bpy.context.view_layer.update()

    pts = np.vstack([world_pts(o) for _, o in loaded])
    lo = np.percentile(pts, PCTL[0], axis=0)
    hi = np.percentile(pts, PCTL[1], axis=0)
    reach = float(np.abs(np.concatenate([lo, hi])).max())
    assert reach < TARGET_SIZE * 1.2, f"coordinate spaces disagree: reach {reach:.2f}"
    print(f"population extent in scene units: {np.round(hi - lo, 2)}")

    light_the_scene(args.hdri, args.lights)
    scene = bpy.context.scene
    data = bpy.data.cameras.new("cam")
    data.lens = 52
    cam = bpy.data.objects.new("cam", data)
    bpy.context.collection.objects.link(cam)
    scene.camera = cam
    configure_render(args.size, args.samples)
    os.makedirs(args.out, exist_ok=True)

    def place(az_deg):
        e = math.radians(args.elev)
        a = math.radians(az_deg)
        d = TARGET_SIZE * args.dist
        cam.location = (d * math.cos(e) * math.cos(a),
                        d * math.cos(e) * math.sin(a),
                        d * math.sin(e))
        cam.rotation_euler = (Vector((0, 0, 0)) - Vector(cam.location)).to_track_quat("-Z", "Y").to_euler()

    meta = {"cells": [{"id": c["id"], "cell_type": c["cell_type"],
                       "root_id": c.get("root_id", "")} for c, _ in loaded],
            "counts": counts, "frames": args.frames,
            "block_um": (BLOCK_HI - BLOCK_LO).round(2).tolist()}
    with open(os.path.join(args.out, "scene.json"), "w") as fh:
        json.dump(meta, fh, indent=1)

    if args.frames <= 0:
        place(38.0)
        scene.render.filepath = os.path.join(args.out, "still.png")
        bpy.ops.render.render(write_still=True)
        print("wrote", scene.render.filepath)
        return

    # One continuous move, not four. A full turn, resumable frame by frame.
    for i in range(args.frames):
        out = os.path.join(args.out, f"frame_{i:04d}.png")
        if os.path.exists(out):
            continue
        place(38.0 + 360.0 * i / args.frames)
        scene.render.filepath = out
        bpy.ops.render.render(write_still=True)
        if i % 20 == 0:
            print(f"  frame {i}/{args.frames}")
    print(f"wrote {args.frames} frames to {args.out}")


if __name__ == "__main__":
    main()
