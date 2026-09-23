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
import random
import sys

import bpy
import mathutils
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
# The cage is context, not subject. At full accent blue with emission 0.9 it
# was the brightest thing in frame and pulled the eye off the cells. Dark
# slate: present when you look for it, invisible when you are not.
BLOCK_RGB = (0.055, 0.085, 0.125)           # dark blue grey

# The palette lives in ONE file, tools/mec_palette.json, so the render and the
# legend cannot drift. They did: the legend kept the old pale lilac while the
# cells rendered hot pink.
#
# The hexes are sRGB. Blender colour sockets are LINEAR, so they MUST go
# through srgb_to_linear on the way in. Pasting sRGB straight into Base Color
# cost half the saturation on every cell type.
_PAL_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                         "mec_palette.json")
with open(_PAL_PATH, encoding="utf-8") as _fh:
    _PAL = json.load(_fh)
TYPE_HEX = {k: v["hex"] for k, v in _PAL["types"].items()}
TYPE_ORDER = _PAL["order"]


def srgb_to_linear(c):
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def hex_rgb(h):
    """sRGB hex -> LINEAR rgb triple, which is what Blender sockets expect."""
    s = h.lstrip("#")
    return tuple(srgb_to_linear(int(s[i:i + 2], 16) / 255.0) for i in (0, 2, 4))


TYPE_COLOUR = {k: hex_rgb(v) for k, v in TYPE_HEX.items()}



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


def random_colour(i, seed):
    """A distinct colour per cell, spread evenly round the hue wheel.

    Golden angle stepping rather than random hues: drawing hues at random
    clumps them, so a few cells end up nearly the same colour while whole
    sectors of the wheel go unused. Saturation and value stay in the range the
    rest of the palette lives in, so the banner still looks like this project
    and not like a test card.

    This is DECORATION. It must never be used for a figure with a legend,
    because a colour here means nothing at all.
    """
    import colorsys
    rng = random.Random(seed * 9973 + i)
    h = ((seed * 0.11 + i * 0.6180339887) % 1.0)
    sat = 0.72 + rng.random() * 0.22
    val = 0.86 + rng.random() * 0.14
    r, g, b = colorsys.hsv_to_rgb(h, sat, val)
    return tuple(srgb_to_linear(c) for c in (r, g, b))



def material_for(cell_type, rgb=None, key=None):
    name = key or f"type_{cell_type}"
    if name in bpy.data.materials:
        return bpy.data.materials[name]
    rgb = rgb if rgb is not None else TYPE_COLOUR.get(cell_type, (0.8, 0.8, 0.8))
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


def block_cage(parent, axis_map):
    """Wireframe of the imaged block, from its own bounds.

    The cells go through the glTF importer, which converts the file's Y-up
    frame to Blender's Z-up and bakes it into the vertices. A cage built
    straight from the micrometre bounds does NOT, so it lands somewhere else
    entirely. axis_map is measured from a real imported cell rather than
    assumed, so this stays correct if the exporter ever changes.
    """
    lo, hi = axis_map(BLOCK_LO), axis_map(BLOCK_HI)
    lo, hi = np.minimum(lo, hi), np.maximum(lo, hi)
    verts = [(x, y, z) for x in (lo[0], hi[0]) for y in (lo[1], hi[1]) for z in (lo[2], hi[2])]
    # FACES, not edges. The Wireframe modifier builds tubes from face edges and
    # produces nothing at all from a mesh that has only edges, which is why the
    # cage was invisible the first two times.
    faces = [(0, 1, 3, 2), (4, 6, 7, 5), (0, 4, 5, 1),
             (2, 3, 7, 6), (0, 2, 6, 4), (1, 5, 7, 3)]
    mesh = bpy.data.meshes.new("block")
    mesh.from_pydata(verts, [], faces)
    obj = bpy.data.objects.new("block", mesh)
    bpy.context.collection.objects.link(obj)
    # Wireframe so the cage renders as tubes rather than vanishing: EEVEE will
    # not draw bare edges.
    mod = obj.modifiers.new("wire", "WIREFRAME")
    # Thickness is in the cage's OWN units, which are micrometres, and the whole
    # assembly is then scaled by about 1/200 to fit TARGET_SIZE. A 2.2 um bar
    # became 0.01 scene units and was invisible. Size it from the block instead.
    mod.thickness = float(max(BLOCK_HI - BLOCK_LO)) * 0.003
    mod.use_replace = True      # keep only the tubes, not the solid box
    mat = bpy.data.materials.new("cage")
    mat.use_nodes = True
    b = mat.node_tree.nodes["Principled BSDF"]
    b.inputs["Base Color"].default_value = (*BLOCK_RGB, 1.0)
    if "Emission Color" in b.inputs:
        b.inputs["Emission Color"].default_value = (*BLOCK_RGB, 1.0)
        b.inputs["Emission Strength"].default_value = 0.22
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


def composite_ground(scene, on=True):
    """Put the background colour behind a film-transparent render.

    Turned OFF for cycle layers, which have to keep their alpha so the post
    pass can fade each cell type in and out over a single shared plate.
    """
    scene.use_nodes = bool(on)
    if not on:
        return
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


def configure_render(size, samples, aspect=(16, 9)):
    scene = bpy.context.scene
    scene.render.engine = "BLENDER_EEVEE_NEXT"
    scene.render.resolution_x = size
    scene.render.resolution_y = int(round(size * aspect[1] / aspect[0]))
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
    ap.add_argument("--group-glia", action="store_true",
                    help="colour astrocyte, oligodendrocyte and microglia as "
                         "one 'glia' class")
    ap.add_argument("--frames", type=int, default=0, help="0 = one still")
    ap.add_argument("--elev", type=float, default=8.0)
    ap.add_argument("--az", type=float, default=74.0,
                    help=("start azimuth. The thin 447 um axis is Blender Y, so "
                          "looking along it, near 90 degrees, shows the wide "
                          "2031 x 1338 um face. Near 0 shows the narrow end."))
    ap.add_argument("--dist", type=float, default=0.0,
                    help="0 = fit the cage automatically")
    ap.add_argument("--hdri", type=float, default=1.10)
    ap.add_argument("--lights", type=float, default=0.0)
    # NOT "--cycle": Blender's own argument parser sees the Cycles addon's
    # --cycles-device and --cycles-print-stats and rejects the abbreviation
    # as ambiguous, before the script ever runs.
    ap.add_argument("--depth-bins", type=int, default=14)
    ap.add_argument("--random-colours", type=int, default=0, metavar="SEED",
                    help="give every cell its own colour instead of a type "
                         "colour; for a decorative banner ONLY, never for a "
                         "figure that carries a legend")
    ap.add_argument("--no-cage", action="store_true",
                    help="drop the wireframe block; for a feature image where "
                         "the cells are the subject and a box would only box "
                         "them in")
    ap.add_argument("--aspect", default="16:9",
                    help="frame aspect as W:H, e.g. 4:3 or 5:4 for a banner")
    ap.add_argument("--fill", type=float, default=1.0,
                    help="<1 crops in on the subject, >1 pads it out")
    ap.add_argument("--group-by", default="type", choices=("type", "layer", "depth"),
                    help="what each rendered alpha layer contains")
    ap.add_argument("--type-cycle", action="store_true", dest="type_cycle",
                    help="render one alpha layer per cell type plus a bare "
                         "plate, for the post pass to fade between")
    args = ap.parse_args(argv_after_ddash())

    with open(args.cells) as fh:
        manifest = json.load(fh)
    cells = manifest["cells"]

    # The three glial names come from a nucleus-size prediction that an expert
    # has contradicted: the cell this project called an oligodendrocyte was an
    # astrocyte, and the one it called a microglia was an oligodendrocyte. The
    # glia here sit across six clusters with no consistent mapping, so the
    # figure can honestly say "glia" and cannot honestly say which kind.
    if args.group_glia:
        members = set(_PAL.get("glia_members", []))
        n = 0
        for c in cells:
            if c["cell_type"] in members:
                c["cell_type"] = "glia"
                n += 1
        print(f"grouped {n} cells into one glia class")
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
        if args.random_colours:
            obj.data.materials.append(material_for(
                c["cell_type"], rgb=random_colour(len(loaded), args.random_colours),
                key=f"rand_{len(loaded)}"))
        else:
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

    # MEASURE the importer's axis convention from a cell whose micrometre bounds
    # we already know, instead of hardcoding one. Section 5 of the playbook is
    # about exactly this class of bug.
    probe_cell, probe_obj = loaded[0]
    tier0 = probe_cell["tiers"].get(args.tier) or next(iter(probe_cell["tiers"].values()))
    known_lo = np.array(tier0["bbox_min_um"])
    known_hi = np.array(tier0["bbox_max_um"])
    got = world_pts(probe_obj)
    got_lo, got_hi = got.min(0), got.max(0)
    perm, sign = [], []
    for k in range(3):
        # which micrometre axis has the same extent as Blender axis k
        j = int(np.argmin(np.abs((known_hi - known_lo) - (got_hi[k] - got_lo[k]))))
        perm.append(j)
        sign.append(1.0 if abs(got_lo[k] - known_lo[j]) < abs(got_lo[k] + known_hi[j]) else -1.0)
    perm = np.array(perm); sign = np.array(sign)
    print(f"importer axis map: Blender xyz <- um axes {perm.tolist()} signs {sign.tolist()}")

    def axis_map(p):
        return np.asarray(p)[perm] * sign

    # A feature image has no cage: the cells are the subject, and a wireframe
    # box around them only says "this is a sample of a volume", which is the
    # job of the figures further down the page, not of a banner.
    cage = None if args.no_cage else block_cage(root, axis_map)

    # Scale and centre on the BLOCK, not on the cells, so the figure is a
    # statement about the volume and the cells sit where they sit inside it.
    blo, bhi = axis_map(BLOCK_LO), axis_map(BLOCK_HI)
    blo, bhi = np.minimum(blo, bhi), np.maximum(blo, bhi)
    span = bhi - blo
    scale = TARGET_SIZE / float(span.max())
    centre = (bhi + blo) / 2.0
    # STANDING UP, not lying flat. After the importer's conversion the thin
    # 447 um axis is Blender Y, which points away from the camera, so the block
    # reads as a window you look into: 2031 um across, 1338 um tall, 447 um
    # deep. Laying it flat like a table hid the layers, which are the thing the
    # figure is about.
    root.scale = (scale, scale, scale)
    root.rotation_euler = (0.0, 0.0, 0.0)
    # An object's matrix is T * R * S, so LOCATION IS APPLIED AFTER ROTATION.
    # Handing it a centre measured in unrotated space shifts the assembly by an
    # unrotated vector in rotated space and throws it clear of the origin: the
    # assert below caught exactly that, at reach 12.42 on a 10 unit block.
    rot = mathutils.Euler(root.rotation_euler).to_matrix()
    root.location = tuple(-(rot @ Vector(tuple(centre * scale))))
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
    aspect = tuple(int(x) for x in args.aspect.split(":"))
    configure_render(args.size, args.samples, aspect)
    os.makedirs(args.out, exist_ok=True)

    # Fit the camera from its ACTUAL field of view, not a fudge factor. The
    # first attempt used invented constants and put the camera inside the box.
    #
    # Blender's default sensor fit is AUTO, which fits the LARGER frame
    # dimension, so on a 16:9 render the horizontal angle comes from the
    # 36 mm sensor and the vertical is that scaled by 9/16. The tighter of the
    # two is what has to contain the subject.
    sensor_w = data.sensor_width
    sensor_h = sensor_w * scene.render.resolution_y / scene.render.resolution_x
    tan_h = (sensor_w / 2.0) / data.lens
    tan_v = (sensor_h / 2.0) / data.lens
    # With no cage there is nothing to frame against, so frame against the
    # cells themselves. Percentile bounds, not the raw extremes: a single axon
    # running 1.3 mm out of the field would otherwise set the camera distance
    # for everything and leave the population a speck in the middle.
    if cage is None:
        # Re-centre on the CELLS. The root was centred on the block, which is
        # right when the block is drawn, because then the figure is a statement
        # about the volume. With no cage there is no block on screen, and the
        # cells fill only its upper part, so aiming at the block's centre put
        # the population up and to the left with a third of the frame empty.
        pts0 = np.concatenate([world_pts(o) for _, o in loaded])
        mid = (np.percentile(pts0, 1.5, axis=0)
               + np.percentile(pts0, 98.5, axis=0)) / 2.0
        root.location = tuple(np.array(root.location) - mid)
        bpy.context.view_layer.update()
        print(f"no cage: re-centred on the cells, moved {np.round(-mid, 3)}")

    if cage is not None:
        cage_pts = world_pts(cage)
    else:
        pts = np.concatenate([world_pts(o) for _, o in loaded])
        lo = np.percentile(pts, 1.5, axis=0)
        hi = np.percentile(pts, 98.5, axis=0)
        cage_pts = np.array([[x, y, z] for x in (lo[0], hi[0])
                             for y in (lo[1], hi[1]) for z in (lo[2], hi[2])])
        print(f"no cage: framing on the cells, "
              f"{np.round(hi - lo, 2)} across at 1.5 to 98.5 percentile")

    def cam_dir(az_deg):
        e, a = math.radians(args.elev), math.radians(az_deg)
        return np.array([math.cos(e) * math.cos(a), math.cos(e) * math.sin(a), math.sin(e)])

    def fits(d, u):
        """Does every cage corner land inside the frame at this distance?"""
        eye = u * d
        fwd = -u / np.linalg.norm(u)
        up0 = np.array([0.0, 0.0, 1.0])
        right = np.cross(fwd, up0)
        right /= np.linalg.norm(right)
        up = np.cross(right, fwd)
        rel = cage_pts - eye
        z = rel @ fwd
        if (z <= 0).any():
            return False
        return bool((np.abs(rel @ right) / z <= tan_h * 0.93).all()
                    and (np.abs(rel @ up) / z <= tan_v * 0.93).all())

    # A bounding sphere badly over-pads a flat slab seen near face on, which
    # left the block small in a mostly empty frame. Solve the real projection
    # instead, and for a turntable solve the WORST azimuth in the turn so the
    # box never clips part way round.
    azimuths = ([args.az] if args.frames <= 0
                else [args.az + 360.0 * i / 24 for i in range(24)])
    radius = float(np.linalg.norm(cage_pts, axis=1).max())
    need = 0.0
    for azd in azimuths:
        u = cam_dir(azd)
        lo_d, hi_d = 0.05 * radius, 12.0 * radius
        for _ in range(40):
            mid = (lo_d + hi_d) / 2.0
            if fits(mid, u):
                hi_d = mid
            else:
                lo_d = mid
        need = max(need, hi_d)
    auto_dist = need / TARGET_SIZE * args.fill
    if args.dist <= 0:
        args.dist = auto_dist
    print(f"cage radius {radius:.2f}, solved over {len(azimuths)} azimuth(s) "
          f"-> dist {auto_dist:.2f}, using {args.dist:.2f}")

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

    if args.type_cycle:
        # One camera, one cage, one render per type. EVERY cell stays loaded
        # and unwanted ones are only hidden from the render, because the
        # camera fit and the axis probe both read the loaded scene: filtering
        # the cells instead would have moved the camera between layers and the
        # fades would not line up.
        place(args.az)
        scene.render.image_settings.color_mode = "RGBA"

        # Grouping by LAYER renders one alpha layer per cortical layer while
        # every cell keeps its own type colour, which is what makes the
        # laminar reveal read as anatomy rather than as a legend.
        if args.group_by == "depth":
            # Bin by the soma's position through the THIN axis of the slab, the
            # 447 um sectioning depth. A sweep along it shows what the turntable
            # cannot: how little tissue there is front to back compared with the
            # two millimetres across.
            zs = [c["nucleus_um"][2] for c, _ in loaded if c.get("nucleus_um")]
            z0, z1 = min(zs), max(zs)
            nb = max(2, args.depth_bins)

            def bin_of(c):
                z = (c.get("nucleus_um") or [0, 0, z0])[2]
                return min(nb - 1, int((z - z0) / max(1e-6, z1 - z0) * nb))

            key_of = lambda c: f"z{bin_of(c):02d}"
            present = sorted({key_of(c) for c, _ in loaded})
            group_counts = {k: sum(1 for c, _ in loaded if key_of(c) == k)
                            for k in present}
            meta["depth_range_um"] = [round(z0, 1), round(z1, 1)]
            print(f"depth bins over z {z0:.0f}..{z1:.0f} um: "
                  + ", ".join(f"{k}={group_counts[k]}" for k in present))
        elif args.group_by == "layer":
            key_of = lambda c: c.get("layer") or "?"
            present = [L for L in ("I", "II", "III", "IV", "V", "VI", "?")
                       if any(key_of(c) == L for c, _ in loaded)]
            group_counts = {L: sum(1 for c, _ in loaded if key_of(c) == L)
                            for L in present}
        else:
            key_of = lambda c: c["cell_type"]
            present = [t for t in TYPE_ORDER if t in counts]
            group_counts = {t: counts[t] for t in present}

        composite_ground(scene, True)
        for _, obj in loaded:
            obj.hide_render = True
        scene.render.filepath = os.path.join(args.out, "plate.png")
        bpy.ops.render.render(write_still=True)
        print("wrote plate.png (cage and background, no cells)")

        composite_ground(scene, False)      # keep alpha on the cell layers
        for t in present:
            for c, obj in loaded:
                obj.hide_render = key_of(c) != t
            scene.render.filepath = os.path.join(args.out, f"layer_{t}.png")
            bpy.ops.render.render(write_still=True)
            print(f"wrote layer_{t}.png  ({group_counts[t]} cells)")

        meta["cycle_types"] = present
        meta["cycle_group_by"] = args.group_by
        meta["cycle_counts"] = group_counts
        with open(os.path.join(args.out, "scene.json"), "w") as fh:
            json.dump(meta, fh, indent=1)
        print(f"cycle layers done: {len(present)} types + plate")
        return

    if args.frames <= 0:
        place(args.az)
        scene.render.filepath = os.path.join(args.out, "still.png")
        bpy.ops.render.render(write_still=True)
        print("wrote", scene.render.filepath)
        return

    # One continuous move, not four. A full turn, resumable frame by frame.
    for i in range(args.frames):
        out = os.path.join(args.out, f"frame_{i:04d}.png")
        if os.path.exists(out):
            continue
        place(args.az + 360.0 * i / args.frames)
        scene.render.filepath = out
        bpy.ops.render.render(write_still=True)
        if i % 20 == 0:
            print(f"  frame {i}/{args.frames}")
    print(f"wrote {args.frames} frames to {args.out}")


if __name__ == "__main__":
    main()
