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
import traceback

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


# Hue arcs the banner colours are drawn from, in degrees, with weights.
#
# Stepping the golden angle across the WHOLE wheel spreads hues evenly, which
# sounds right and looks wrong: a sixth of the wheel is yellow-green and olive,
# so a sixth of the cells came out that colour and the picture read as "too much
# green". Restricting the wheel to the arcs Amy actually wants, and stepping
# evenly WITHIN them, keeps the even spread and drops the greens entirely.
#
# Weighted to Amy's brief: blues, purples, yellow and pinks dominant, teal as an
# accent. The gold band stays NARROW in hue even though its weight is high,
# because a wide yellow band is exactly where olive lives.
HUE_ARCS = [
    (170, 196, 0.55),   # teal and turquoise, an accent now rather than a third
    (200, 255, 1.90),   # all the blues
    (258, 305, 1.70),   # purples
    (310, 350, 1.50),   # pinks and magentas
    (36,   52, 1.05),   # warm golden yellow
]
_ARC_TOTAL = sum(w for _, _, w in HUE_ARCS)


def hue_from_arcs(t):
    """Map t in [0,1) onto the allowed arcs, proportional to their weights."""
    x = (t % 1.0) * _ARC_TOTAL
    for lo, hi, w in HUE_ARCS:
        if x <= w:
            return (lo + (hi - lo) * (x / w)) / 360.0
        x -= w
    lo, hi, _ = HUE_ARCS[-1]
    return hi / 360.0


def random_colour(i, seed):
    """A distinct colour per cell, spread evenly across the allowed hues.

    Golden angle stepping rather than random hues: drawing at random clumps
    them, so several cells end up nearly the same colour while whole stretches
    go unused.

    Gold gets its saturation and value pinned high. Olive is just a dark or
    desaturated yellow, so letting those two vary freely in the yellow band is
    precisely how you produce the colour this palette exists to avoid.

    This is DECORATION. It must never be used for a figure with a legend,
    because a colour here means nothing at all.
    """
    import colorsys
    rng = random.Random(seed * 9973 + i)
    h = hue_from_arcs(seed * 0.11 + i * 0.6180339887)
    if 30 / 360.0 <= h <= 60 / 360.0:
        sat = 0.82 + rng.random() * 0.12
        val = 0.95 + rng.random() * 0.05
    else:
        sat = 0.70 + rng.random() * 0.26
        val = 0.84 + rng.random() * 0.16
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


def ease_io(t):
    """Smoothstep. Linear camera moves start and stop with a visible jerk."""
    t = max(0.0, min(1.0, float(t)))
    return t * t * (3.0 - 2.0 * t)


def solo_material(obj, rgb, level):
    """Per object material whose brightness IS the fade.

    Fading with ALPHA would make EEVEE sort several hundred overlapping
    transparent meshes, which is slow and wrong looking. Fading the colour
    towards black on a black background reads the same and needs no
    transparency at all. A cell at level 0 is hidden outright rather than drawn
    black, because a black mesh still writes depth and would punch holes in the
    cells behind it.
    """
    name = "fade_" + obj.name
    mat = bpy.data.materials.get(name)
    if mat is None:
        mat = bpy.data.materials.new(name)
        mat.use_nodes = True
        b = mat.node_tree.nodes["Principled BSDF"]
        b.inputs["Roughness"].default_value = 0.62
        b.inputs["IOR"].default_value = 1.04
        for k, v in (("Subsurface Weight", 0.30), ("Subsurface Scale", 0.012 * TARGET_SIZE)):
            if k in b.inputs:
                b.inputs[k].default_value = v
        obj.data.materials.clear()
        obj.data.materials.append(mat)
    b = mat.node_tree.nodes["Principled BSDF"]
    lit = tuple(c * level for c in rgb)
    b.inputs["Base Color"].default_value = (*lit, 1.0)
    if "Emission Color" in b.inputs:
        b.inputs["Emission Color"].default_value = (*lit, 1.0)
    if "Emission Strength" in b.inputs:
        b.inputs["Emission Strength"].default_value = 0.22 * level
    return mat


def cell_centres(loaded):
    """World-space centre of every loaded cell, and the population's bounds."""
    cs = []
    for _, o in loaded:
        p = world_pts(o)
        cs.append((np.percentile(p, 2, axis=0) + np.percentile(p, 98, axis=0)) / 2.0)
    cs = np.array(cs)
    return cs, cs.min(0), cs.max(0)


def look_at(cam, eye, target):
    cam.location = tuple(eye)
    d = Vector(tuple(target)) - Vector(tuple(eye))
    cam.rotation_euler = d.to_track_quat("-Z", "Y").to_euler()


def frames_differ(a_path, b_path):
    """Two rendered frames are not the same image. A sequence that never moves
    looks perfect in any single frame, which is how a static turntable shipped."""
    import hashlib
    try:
        with open(a_path, "rb") as fa, open(b_path, "rb") as fb:
            return hashlib.sha1(fa.read()).hexdigest() != hashlib.sha1(fb.read()).hexdigest()
    except Exception:
        return True



def catmull(pts, t):
    """Position along a Catmull-Rom spline through pts, t in [0, 1].

    Straight segments between stops would give the camera a visible corner at
    every soma. A spline through the same points keeps the move continuous.
    """
    n = len(pts)
    if n == 1:
        return np.array(pts[0], dtype=float)
    x = max(0.0, min(1.0, float(t))) * (n - 1)
    i = min(int(x), n - 2)
    u = x - i
    p = [np.array(pts[max(0, min(n - 1, i + k))], dtype=float) for k in (-1, 0, 1, 2)]
    u2, u3 = u * u, u * u * u
    return 0.5 * ((2 * p[1])
                  + (-p[0] + p[2]) * u
                  + (2 * p[0] - 5 * p[1] + 4 * p[2] - p[3]) * u2
                  + (-p[0] + 3 * p[1] - 3 * p[2] + p[3]) * u3)


def fibonacci_sphere(n):
    """n points spread evenly over a sphere, in order from one pole to the other.

    Ordered, which is the point: hand it cells sorted by type and each type
    lands on its own band of latitude, so the sphere reads as stripes and the
    width of a stripe is how many cells of that type there are.
    """
    i = np.arange(n, dtype=float) + 0.5
    z = 1.0 - 2.0 * i / n
    r = np.sqrt(np.maximum(0.0, 1.0 - z * z))
    phi = np.pi * (1.0 + 5.0 ** 0.5) * i
    return np.stack([r * np.cos(phi), r * np.sin(phi), z], axis=1)



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
    ap.add_argument("--buildup", type=int, default=0, metavar="FRAMES",
                    help="cells arrive one after another, then all hold, with a "
                         "slow push in and a few degrees of drift")
    ap.add_argument("--headlamp", type=float, default=2600.0,
                    help="energy of a light carried by the camera; it is what "
                         "gives the interior depth, since a world HDRI alone "
                         "lights everything equally")
    ap.add_argument("--near-fade", type=float, default=0.12, dest="near_fade",
                    help="cells fade out within this FRACTION of TARGET_SIZE of the "
                         "lens, so they neither occlude nor crowd. 0.55 was a "
                         "1100 um band, half the block, and dimmed the whole "
                         "scene")
    ap.add_argument("--explode", type=int, default=0, metavar="FRAMES",
                    help="cells leave their true positions for a sphere where "
                         "each type holds its own band of latitude, hold, then "
                         "go home. The census and the geography in one move")
    ap.add_argument("--ladder", type=int, default=0, metavar="FRAMES",
                    help="one continuous zoom from the whole block down to a "
                         "single dendritic spine, no cuts")
    ap.add_argument("--ladder-cell", default="", dest="ladder_cell",
                    help="id of the cell the ladder ends on; default is the "
                         "stellate with the most detailed mesh available")
    ap.add_argument("--soma-tour", type=int, default=0, metavar="FRAMES",
                    dest="soma_tour",
                    help="drift slowly from one soma to the next with a real "
                         "lens: the focus racks onto each cell in turn and "
                         "everything else goes soft")
    ap.add_argument("--tour-stops", type=int, default=10, dest="tour_stops",
                    help="how many somata the tour visits")
    ap.add_argument("--tour-cast", type=int, default=6, dest="tour_cast",
                    help="how many neighbours are drawn around the cell in "
                         "focus. This, not the near fade, is what decides "
                         "whether the frame reads: the tissue is opaque at "
                         "every distance, so the only way to see one cell is "
                         "to draw few")
    ap.add_argument("--fstop", type=float, default=2.0,
                    help="aperture. Smaller is shallower; below about 1.4 at "
                         "this scale the soma itself stops being sharp front "
                         "to back")
    ap.add_argument("--flythrough", type=int, default=0, metavar="FRAMES",
                    help="camera travels through the block lighting cells as it "
                         "passes, then pulls back to reveal the whole volume")
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
    loaded, counts, missing = [], {}, []
    for c in cells:
        # LOD by build time, not per frame: a cell the camera passes close to
        # carries a "close" tier, and it is preferred wherever it exists. Card
        # density is right for a population figure and visibly faceted at arm's
        # length, which is what the first flythrough showed on every near
        # branch.
        # Preference order, then FALL BACK rather than drop the cell. The close
        # tier is 485 MB and is a local render input, not a web asset, so it is
        # not in the repo: a fresh clone has the manifest entries without the
        # files. Skipping on a missing file would quietly render a smaller
        # population and still look entirely plausible.
        want = [c["tiers"].get("close")] if args.tier == "card" else []
        want += [c["tiers"].get(args.tier)] + list(c["tiers"].values())
        path = tier = None
        for t in want:
            if not t:
                continue
            p = os.path.join(mesh_dir, t["file"])
            if os.path.exists(p):
                tier, path = t, p
                break
        if path is None:
            print(f"  no mesh on disk for {c['id']}, skipping")
            missing.append(c["id"])
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
    if missing:
        # Loud, because a figure is a claim about a population and quietly
        # rendering a different one is the failure that looks like success.
        print(f"WARNING: {len(missing)} of {len(cells)} cells have no mesh on "
              f"disk and are NOT in this render: {', '.join(missing[:8])}"
              + (" ..." if len(missing) > 8 else ""))

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

    if args.buildup:
        # Cells arrive one after another and stay, over a slow push in and a
        # few degrees of drift. The camera MOVES, so unlike the type cycle this
        # cannot be composited from layers: every frame is its own render.
        n = len(loaded)
        order = list(range(n))
        random.Random(5).shuffle(order)          # scattered, not a wipe
        rgbs = [TYPE_COLOUR.get(c["cell_type"], (0.8, 0.8, 0.8)) for c, _ in loaded]

        SOLO = max(1, int(args.buildup * 0.26))  # one cell at a time
        BUILD = max(1, int(args.buildup * 0.46)) # they accumulate
        HOLD = args.buildup - SOLO - BUILD       # everything, held

        os.makedirs(args.out, exist_ok=True)
        solo_pick = [order[int(i * n / SOLO)] for i in range(SOLO)]
        for _, o in loaded:
            o.hide_render = True

        for i in range(args.buildup):
            out = os.path.join(args.out, "frame_%04d.png" % i)
            if os.path.exists(out):
                continue
            t = i / max(1, args.buildup - 1)
            place(args.az - 4.0 + 8.0 * ease_io(t))
            cam.data.lens = 50.0 / (1.0 + 0.20 * ease_io(t))   # slow push in

            if i < SOLO:
                want = {solo_pick[i]}
            elif i < SOLO + BUILD:
                k = (i - SOLO + 1) / BUILD
                want = set(order[:max(1, int(round(k * n)))])
            else:
                want = set(range(n))

            for j, (_, o) in enumerate(loaded):
                on = j in want
                o.hide_render = not on
                if on:
                    solo_material(o, rgbs[j], 1.0)

            scene.render.filepath = out
            bpy.ops.render.render(write_still=True)
            if i % 30 == 0:
                print("  frame %d/%d, %d cells up" % (i, args.buildup, len(want)))

        meta["frames"] = args.buildup
        meta["mode"] = "buildup"
        with open(os.path.join(args.out, "scene.json"), "w") as fh:
            json.dump(meta, fh, indent=1)
        a = os.path.join(args.out, "frame_0000.png")
        b = os.path.join(args.out, "frame_%04d.png" % (args.buildup // 2))
        print("frames differ:", frames_differ(a, b))
        print("wrote %d frames to %s" % (args.buildup, args.out))
        return

    if args.explode:
        # THE CENSUS AND THE GEOGRAPHY IN ONE MOVE. Cells leave their true
        # positions for a sphere on which each type holds a band of latitude,
        # hold there long enough to be counted, then go home. A still of the
        # sphere says what is in the block; a still of the end says where.
        n = len(loaded)
        centres, clo, chi = cell_centres(loaded)
        mid = (chi + clo) / 2.0
        rgbs = [TYPE_COLOUR.get(c["cell_type"], (0.8, 0.8, 0.8)) for c, _ in loaded]

        # Sorted by type, then by depth inside the type, so a band is coherent
        # rather than speckled.
        depth_axis = int(np.argmin(chi - clo))
        order = sorted(range(n), key=lambda j: (
            TYPE_ORDER.index(loaded[j][0]["cell_type"])
            if loaded[j][0]["cell_type"] in TYPE_ORDER else 99,
            centres[j][depth_axis]))
        RAD = TARGET_SIZE * 0.92
        pts = fibonacci_sphere(n) * RAD
        target = np.zeros((n, 3))
        for slot, j in enumerate(order):
            target[j] = pts[slot]
        # The object's own coordinates are absolute, so the move is a delta.
        delta = target - (centres - mid)

        OUT_F = max(1, int(args.explode * 0.30))
        HOLD_F = max(1, int(args.explode * 0.26))
        BACK_F = max(1, int(args.explode * 0.30))
        os.makedirs(args.out, exist_ok=True)
        home = [np.array(o.location) for _, o in loaded]

        for i in range(args.explode):
            out = os.path.join(args.out, "frame_%04d.png" % i)
            if i < OUT_F:
                k = ease_io(i / max(1, OUT_F - 1))
            elif i < OUT_F + HOLD_F:
                k = 1.0
            elif i < OUT_F + HOLD_F + BACK_F:
                k = 1.0 - ease_io((i - OUT_F - HOLD_F) / max(1, BACK_F - 1))
            else:
                k = 0.0
            # One slow revolution across the whole shot, so the sphere is read
            # as a sphere and not as a disc.
            place(args.az + 360.0 * (i / max(1, args.explode - 1)))
            if os.path.exists(out):
                continue
            for j, (_, o) in enumerate(loaded):
                o.location = tuple(home[j] + delta[j] * k)
            bpy.context.view_layer.update()
            scene.render.filepath = out
            bpy.ops.render.render(write_still=True)
            if i % 40 == 0:
                print("  frame %d/%d  out %.2f" % (i, args.explode, k))

        meta["frames"] = args.explode
        meta["mode"] = "explode"
        with open(os.path.join(args.out, "scene.json"), "w") as fh:
            json.dump(meta, fh, indent=1)
        a = os.path.join(args.out, "frame_0000.png")
        b = os.path.join(args.out, "frame_%04d.png" % (args.explode // 2))
        print("frames differ:", frames_differ(a, b))
        print("wrote %d frames to %s" % (args.explode, args.out))
        return

    if args.ladder:
        # ONE CONTINUOUS ZOOM, block to spine. The range is about four orders
        # of magnitude, so the approach is EXPONENTIAL: a linear one spends
        # most of its length crossing empty space and then arrives too fast to
        # read. Constant relative zoom rate means every decade gets equal time.
        n = len(loaded)
        centres, clo, chi = cell_centres(loaded)
        mid = (chi + clo) / 2.0
        rgbs = [TYPE_COLOUR.get(c["cell_type"], (0.8, 0.8, 0.8)) for c, _ in loaded]

        pick = None
        if args.ladder_cell:
            for j, (c, _) in enumerate(loaded):
                if c["id"] == args.ladder_cell:
                    pick = j
        if pick is None:
            # Whoever has the most faces per micrometre is who holds up at the
            # bottom of the ladder. A card tier cell is faceted long before a
            # spine is in frame.
            best = -1.0
            for j, (c, _) in enumerate(loaded):
                t = c["tiers"].get("close") or c["tiers"].get("detail")
                if not t or c["cell_type"] not in ("stellate", "pyramidal"):
                    continue
                d = t.get("density_per_um2", 0)
                if d > best:
                    best, pick = d, j
        if pick is None:
            sys.exit("no cell with a close or detail mesh to end the ladder on")
        print("ladder ends on %s (%s)" % (loaded[pick][0]["id"],
                                          loaded[pick][0]["cell_type"]))

        # The end point: a piece of surface well away from the soma, which is
        # where spines are. The soma is smooth and makes a dull last frame.
        wp = world_pts(loaded[pick][1])
        soma_pt = np.array(list(root.matrix_world
                                @ Vector(tuple(axis_map(loaded[pick][0]["nucleus_um"])))))
        far = np.linalg.norm(wp - soma_pt, axis=1)
        cand = wp[(far > np.percentile(far, 55)) & (far < np.percentile(far, 80))]
        endp = cand[len(cand) // 2] if len(cand) else wp[len(wp) // 2]
        print("ladder target %s, %.2f units from its soma"
              % (np.round(endp, 3), float(np.linalg.norm(endp - soma_pt))))

        D0 = TARGET_SIZE * max(args.dist, 1.25)      # the whole block in frame
        D1 = TARGET_SIZE * 0.0022                    # about 45 nanometres away
        eye_dir = None
        os.makedirs(args.out, exist_ok=True)

        for i in range(args.ladder):
            out = os.path.join(args.out, "frame_%04d.png" % i)
            t = i / max(1, args.ladder - 1)
            # Equal time per decade.
            dist = D0 * (D1 / D0) ** ease_io(t)
            if eye_dir is None:
                e, a = math.radians(args.elev), math.radians(args.az)
                eye_dir = np.array([math.cos(e) * math.cos(a),
                                    math.cos(e) * math.sin(a), math.sin(e)])
            # Aim drifts from the middle of the block to the target, finishing
            # the move early so the last third is a pure approach.
            aim = mid * (1.0 - ease_io(min(1.0, t / 0.55))) \
                + endp * ease_io(min(1.0, t / 0.55))
            eye = aim + eye_dir * dist
            if not os.path.exists(out):
                look_at(cam, eye, aim)
            cam.data.lens = 42.0

            # Everything that is not the target cell fades out as the frame
            # narrows, or the last two decades are spent inside an opaque wall.
            # The band is tied to the camera distance, so it is the same rule
            # at every scale rather than a hand tuned curve.
            keep = dist * 9.0
            if os.path.exists(out):
                continue
            for j, (_, o) in enumerate(loaded):
                if j == pick:
                    o.hide_render = False
                    solo_material(o, rgbs[j], 1.0)
                    continue
                d = float(np.linalg.norm(centres[j] - aim))
                lvl = ease_io(1.0 - (d / max(1e-6, keep)))
                if lvl <= 0.02:
                    o.hide_render = True
                else:
                    o.hide_render = False
                    solo_material(o, rgbs[j], lvl * 0.7)

            scene.render.filepath = out
            bpy.ops.render.render(write_still=True)
            if i % 40 == 0:
                print("  frame %d/%d  dist %.4f units (%.1f um)  visible %d"
                      % (i, args.ladder, dist, dist / scale,
                         sum(1 for _, o in loaded if not o.hide_render)))

        meta["frames"] = args.ladder
        meta["mode"] = "ladder"
        meta["ladder_cell"] = loaded[pick][0]["id"]
        with open(os.path.join(args.out, "scene.json"), "w") as fh:
            json.dump(meta, fh, indent=1)
        a = os.path.join(args.out, "frame_0000.png")
        b = os.path.join(args.out, "frame_%04d.png" % (args.ladder // 2))
        print("frames differ:", frames_differ(a, b))
        print("wrote %d frames to %s" % (args.ladder, args.out))
        return

    if args.soma_tour:
        # A lens, not a diagram. The camera drifts from one cell body to the
        # next and the focus racks with it, so exactly one cell is sharp at a
        # time and the rest of the tissue is the soft field it sits in. The
        # near fade and the carried light are the same as in the flythrough:
        # without them the interior is a flat wall with no depth to defocus.
        n = len(loaded)
        FR = args.soma_tour
        rgbs = [TYPE_COLOUR.get(c["cell_type"], (0.8, 0.8, 0.8)) for c, _ in loaded]

        # Soma positions, carried through the SAME transform as the meshes.
        # The nucleus is given in micrometres in the volume's own frame, so it
        # has to go through the importer's axis map and then the root object's
        # matrix, or it lands somewhere the cell is not.
        M = root.matrix_world
        somas = np.array([list(M @ Vector(tuple(axis_map(c["nucleus_um"]))))
                          for c, _ in loaded])
        # Check rather than trust: each mapped soma should sit inside its own
        # cell. A silent axis error here would aim the camera at empty space.
        off = []
        for j, (_, o) in enumerate(loaded):
            wp = world_pts(o)
            off.append(float(np.min(np.linalg.norm(wp[::37] - somas[j], axis=1))))
        off = np.array(off)
        print("soma mapping: median %.3f, worst %.3f units from own surface"
              % (np.median(off), off.max()))
        assert np.median(off) < TARGET_SIZE * 0.02, "soma positions do not land on the cells"

        # Who is worth stopping at: a neuron with a close tier mesh, because
        # the card tier is visibly faceted at the distance this shot works at.
        NEURON = {"stellate", "pyramidal", "inhibitory", "bipolar"}
        ok = [j for j, (c, _) in enumerate(loaded)
              if c["cell_type"] in NEURON and "close" in c.get("tiers", {})
              and off[j] < TARGET_SIZE * 0.03]
        if len(ok) < args.tour_stops:
            ok = [j for j, (c, _) in enumerate(loaded) if c["cell_type"] in NEURON]
        centres, clo, chi = cell_centres(loaded)
        span = chi - clo

        # NEIGHBOUR TO NEIGHBOUR, not spread across the block. Farthest point
        # sampling is the right way to cover a volume and the wrong way to plan
        # a camera move: stops a millimetre apart have to be crossed inside one
        # leg, which is a whip pan through tissue, not the slow drift this shot
        # is. Each hop is far enough to be a different cell and near enough to
        # stay inside the same neighbourhood the whole way.
        MINHOP = TARGET_SIZE * 0.025          # about 50 um
        MAXHOP = TARGET_SIZE * 0.115          # about 235 um
        start = ok[int(np.argmin(np.linalg.norm(
            somas[ok] - np.median(somas[ok], axis=0), axis=1)))]
        pick, left = [start], [j for j in ok if j != start]
        while len(pick) < args.tour_stops and left:
            d = np.linalg.norm(somas[left] - somas[pick[-1]], axis=1)
            near = [i for i in np.argsort(d) if MINHOP <= d[i] <= MAXHOP]
            if not near:
                near = [int(np.argmin(np.where(d >= MINHOP, d, np.inf)))]
            j = left.pop(int(near[0]))
            pick.append(j)
        hops = [float(np.linalg.norm(somas[pick[k + 1]] - somas[pick[k]]))
                for k in range(len(pick) - 1)]
        print("tour of %d somata: %s" % (len(pick),
              ", ".join(loaded[j][0]["id"] for j in pick)))
        print("hops, units: %s" % np.round(hops, 3).tolist())

        # Vantage points. The camera stands off each soma by VIEW, from a
        # direction that turns a little at every stop, so the move arcs through
        # the tissue instead of sliding along one line.
        # 0.085 put the lens 173 um from the soma, which frames 114 um: inside
        # the arbor rather than in front of the cell. A stellate dendritic
        # field is about 300 um across, so stand far enough back to hold one.
        VIEW = TARGET_SIZE * 0.19
        vantage = []
        for k, j in enumerate(pick):
            a = 2.0 * math.pi * (k / max(1, len(pick))) * 1.35 + 0.6
            e = math.radians(12.0 * math.sin(k * 1.1))
            d = np.array([math.cos(e) * math.cos(a),
                          math.cos(e) * math.sin(a), math.sin(e)])
            vantage.append(somas[j] + d * VIEW)

        samp_pts, samp_idx = [], []
        for j, (_, o) in enumerate(loaded):
            wp = world_pts(o)
            step = max(1, len(wp) // 140)
            samp_pts.append(wp[::step])
            samp_idx.append(np.full(len(wp[::step]), j))
        samp_pts = np.concatenate(samp_pts)
        samp_idx = np.concatenate(samp_idx)
        # The band has to reach PAST the stand-off, not stop short of it. Its
        # whole job is to clear the tissue between the lens and the cell being
        # looked at, and in a block this dense that tissue is continuous: end
        # the band inside the stand-off and the subject is buried behind a wall
        # of defocused foreground, which is what the first full run rendered.
        # The subject itself is exempt below, so widening this does not dim it.
        # With the cast small, this no longer has to open up the frame. All it
        # does now is keep a branch from sitting on the lens.
        NEAR0 = VIEW * 0.10
        NEAR1 = VIEW * 0.55

        lamp_data = bpy.data.lights.new("headlamp", type="POINT")
        lamp_data.energy = args.headlamp * 0.30   # dimmer: few cells, and near
        lamp_data.shadow_soft_size = TARGET_SIZE * 0.08
        lamp = bpy.data.objects.new("headlamp", lamp_data)
        bpy.context.collection.objects.link(lamp)

        cam.data.lens = 55.0
        cam.data.dof.use_dof = True
        cam.data.dof.aperture_fstop = args.fstop
        cam.data.dof.aperture_blades = 7          # a round bokeh, not a square

        # Time: each stop gets a hold, each leg a move. Holding is what makes
        # the rack readable; a continuous glide never settles on anything.
        K = len(pick)
        legs = K - 1
        HOLD = max(1, int(FR * 0.52 / K))
        MOVE = max(1, int((FR - HOLD * K) / max(1, legs)))
        marks = []
        for k in range(K):
            for _ in range(HOLD):
                marks.append((k, 0.0))
            if k < legs:
                for t in range(MOVE):
                    marks.append((k, (t + 1) / MOVE))
        while len(marks) < FR:
            marks.append(marks[-1])
        marks = marks[:FR]

        FADE = 20.0
        # Each cell carries its own brightness, eased toward whether it is in
        # the cast this frame. No priming needed: the opening cast starts at
        # its target, so frame 0 is already standing.
        cur = np.zeros(n)
        os.makedirs(args.out, exist_ok=True)
        for _, o in loaded:
            o.hide_render = True

        for i in range(FR):
            out = os.path.join(args.out, "frame_%04d.png" % i)
            k, frac = marks[i]
            u = (k + ease_io(frac)) / max(1, legs)
            eye = catmull(vantage, u)
            # Aim: the soma being visited, easing across to the next one only
            # while the camera is actually travelling.
            j_now, j_next = pick[k], pick[min(K - 1, k + 1)]
            aim = somas[j_now] * (1 - ease_io(frac)) + somas[j_next] * ease_io(frac)
            focus_on = j_now if frac < 0.5 else j_next

            if not os.path.exists(out):
                look_at(cam, eye, aim)
            # The focus distance is measured to the soma itself, every frame,
            # so the rack is a consequence of the geometry rather than a curve
            # that has to be kept in step with the camera by hand.
            cam.data.dof.focus_distance = float(np.linalg.norm(
                somas[focus_on] - np.array(eye)))

            # THE CAST: the cell in focus and its nearest neighbours by soma
            # position. Everything else is not drawn at all.
            near_rank = np.argsort(np.linalg.norm(somas - somas[focus_on], axis=1))
            cast = set(int(x) for x in near_rank[:args.tour_cast + 1])
            cast.add(int(focus_on))
            want = np.zeros(n)
            for j in cast:
                want[j] = 1.0
            if i == 0:
                cur[:] = want            # open already standing, not fading up
            else:
                cur += np.clip(want - cur, -1.0 / FADE, 1.0 / FADE)

            if os.path.exists(out):
                continue
            eye_now = np.array(cam.location)
            dmin = np.full(n, 1e9)
            np.minimum.at(dmin, samp_idx,
                          np.linalg.norm(samp_pts - eye_now, axis=1))
            for j, (_, o) in enumerate(loaded):
                lvl = ease_io(float(cur[j]))
                if j == focus_on:
                    lvl = min(1.0, lvl * 1.15 + 0.10)
                else:
                    lvl = min(lvl, ease_io((dmin[j] - NEAR0)
                                           / max(1e-6, NEAR1 - NEAR0))) * 0.35
                if lvl <= 0.02:
                    o.hide_render = True
                else:
                    o.hide_render = False
                    solo_material(o, rgbs[j], lvl)

            cm = cam.matrix_world
            lamp.location = (Vector(cam.location)
                             + cm.to_quaternion() @ Vector((TARGET_SIZE * 0.06,
                                                            TARGET_SIZE * 0.09,
                                                            TARGET_SIZE * 0.03)))
            scene.render.filepath = out
            bpy.ops.render.render(write_still=True)
            if i % 40 == 0:
                print("  frame %d/%d  stop %d/%d  focus %s at %.3f  cast %d  visible %d"
                      % (i, FR, k + 1, K, loaded[focus_on][0]["id"],
                         cam.data.dof.focus_distance, len(cast),
                         sum(1 for _, o in loaded if not o.hide_render)))

        meta["frames"] = FR
        meta["mode"] = "soma_tour"
        meta["tour"] = [loaded[j][0]["id"] for j in pick]
        with open(os.path.join(args.out, "scene.json"), "w") as fh:
            json.dump(meta, fh, indent=1)
        a = os.path.join(args.out, "frame_0000.png")
        b = os.path.join(args.out, "frame_%04d.png" % (FR // 2))
        print("frames differ:", frames_differ(a, b))
        print("wrote %d frames to %s" % (FR, args.out))
        return

    if args.flythrough:
        # A path down the long axis of the block. Cells light up as the camera
        # comes near them and stay lit, so a trail builds up behind it, then the
        # camera pulls back and the whole population is there.
        n = len(loaded)
        centres, clo, chi = cell_centres(loaded)
        rgbs = [TYPE_COLOUR.get(c["cell_type"], (0.8, 0.8, 0.8)) for c, _ in loaded]
        # Sampled surface points per cell, for the near cull.
        #
        # The cull cannot use the cell's bounding RADIUS. An arbor is hundreds
        # of micrometres across but almost entirely empty space, so in the
        # dense middle the camera is inside nearly every cell's sphere at once
        # and culling on that blanked whole frames. What matters is whether
        # actual geometry is at the lens, so sample each cell's surface and
        # measure the nearest sampled point.
        samp_pts, samp_idx = [], []
        for j, (_, o) in enumerate(loaded):
            wp = world_pts(o)
            step = max(1, len(wp) // 140)
            sub = wp[::step]
            samp_pts.append(sub)
            samp_idx.append(np.full(len(sub), j))
        samp_pts = np.concatenate(samp_pts)
        samp_idx = np.concatenate(samp_idx)
        # A hard cull pops. Fade instead, over a band: fully gone at NEAR0,
        # fully present by NEAR1. Coverage in the first cut ran 96 to 99% of
        # the frame, a solid wall of tissue with no black in it and therefore
        # no depth; letting the nearest cells go transparent opens that up.
        NEAR0 = TARGET_SIZE * 0.014
        NEAR1 = TARGET_SIZE * args.near_fade
        print(f"near fade over {len(samp_pts)} sampled points, "
              f"{NEAR0:.3f} to {NEAR1:.3f} units")

        # A light the camera carries. The world HDRI lights every surface the
        # same wherever it is, which is why the interior read as flat spaghetti.
        # A local light falls off with distance, so near structure is modelled
        # and far structure drops away: that IS the depth cue.
        lamp_data = bpy.data.lights.new("headlamp", type="POINT")
        lamp_data.energy = args.headlamp
        lamp_data.shadow_soft_size = TARGET_SIZE * 0.08
        lamp = bpy.data.objects.new("headlamp", lamp_data)
        bpy.context.collection.objects.link(lamp)
        span = chi - clo
        axis = int(np.argmax(span))                     # travel along the longest
        mid = (chi + clo) / 2.0
        half = span[axis] / 2.0
        REACH = float(np.linalg.norm(span) * 0.16)      # how near counts as near
        LOOK = REACH * 3.4                              # how far ahead cells wake up
        FADE = 24.0                                     # frames a cell takes to arrive

        FLY = max(1, int(args.flythrough * 0.68))
        OUT = args.flythrough - FLY
        lit_at = [None] * n                             # frame each cell was reached

        def path_point(u):
            """u in [-1, 1] along the travel axis, with a gentle weave."""
            p = mid.copy()
            # 1.05, not 1.55. Overshooting the block by half its length again
            # put the camera outside the tissue looking away from it for a
            # third of the shot: 634 cells visible, none culled, frame black.
            p[axis] = mid[axis] + u * half * 1.05
            o1 = (axis + 1) % 3
            o2 = (axis + 2) % 3
            p[o1] += math.sin(u * math.pi * 1.1) * span[o1] * 0.22
            p[o2] += math.cos(u * math.pi * 0.7) * span[o2] * 0.16
            return p

        # PRIME THE OPENING. Everything the camera can already see at u = -1 is
        # dated FADE frames in the past, so it is fully up on frame 0.
        eye0 = path_point(-1.0)
        tgt0 = path_point(-1.0 + 0.22) * 0.62 + mid * 0.38
        rel0 = centres - eye0
        d0 = np.linalg.norm(rel0, axis=1)
        f0 = np.array(tgt0) - np.array(eye0)
        f0 = f0 / max(1e-9, np.linalg.norm(f0))
        al0 = rel0 @ f0
        lat0 = np.sqrt(np.maximum(d0 ** 2 - al0 ** 2, 0.0))
        seed = (d0 < REACH) | ((al0 > 0) & (al0 < LOOK * 1.6) & (lat0 < REACH * 1.6))
        for j in np.flatnonzero(seed):
            lit_at[int(j)] = -int(FADE)
        print("opening primed with %d cells already up" % int(seed.sum()))


        wide_dir = None
        os.makedirs(args.out, exist_ok=True)
        for _, o in loaded:
            o.hide_render = True

        for i in range(args.flythrough):
            out = os.path.join(args.out, "frame_%04d.png" % i)
            if i < FLY:
                # Constant speed down the path. Easing it made the camera
                # loiter at the ends, which are the emptiest part, and race
                # through the middle, which is the part worth seeing.
                u = -1.0 + 2.0 * (i / max(1, FLY - 1))
                eye = path_point(u)
                # Aim ahead, but biased back toward the middle of the block, so
                # the view always contains tissue rather than the way out.
                tgt = path_point(min(1.0, u + 0.22)) * 0.62 + mid * 0.38
                cam.data.lens = 34.0                    # wide, so it feels close
                if not os.path.exists(out):
                    look_at(cam, eye, tgt)
                # Light what is AHEAD, not only what has been reached. Lighting
                # on arrival alone left the first seconds black, because the
                # camera starts outside the block with nothing within reach.
                rel = centres - eye
                d = np.linalg.norm(rel, axis=1)
                fwd = (np.array(tgt) - np.array(eye))
                fwd = fwd / max(1e-9, np.linalg.norm(fwd))
                along = rel @ fwd
                lateral = np.sqrt(np.maximum(d ** 2 - along ** 2, 0.0))
                ahead = (along > 0) & (along < LOOK) & (lateral < REACH * 1.3)
                for j in range(n):
                    if lit_at[j] is None and (d[j] < REACH or ahead[j]):
                        lit_at[j] = i
            else:
                k = ease_io((i - FLY) / max(1, OUT - 1))
                if wide_dir is None:
                    e = math.radians(args.elev)
                    a = math.radians(args.az)
                    wide_dir = np.array([math.cos(e) * math.cos(a),
                                         math.cos(e) * math.sin(a), math.sin(e)])
                far = wide_dir * (TARGET_SIZE * args.dist)
                eye = path_point(1.0) * (1.0 - k) + far * k
                tgt = mid * (1.0 - k) + np.zeros(3) * k
                cam.data.lens = 34.0 + 16.0 * k
                if not os.path.exists(out):
                    look_at(cam, eye, tgt)
                for j in range(n):
                    if lit_at[j] is None:
                        lit_at[j] = i               # anything missed arrives now

            if os.path.exists(out):
                continue
            eye_now = np.array(cam.location)
            dmin = np.full(n, 1e9)
            np.minimum.at(dmin, samp_idx,
                          np.linalg.norm(samp_pts - eye_now, axis=1))
            for j, (_, o) in enumerate(loaded):
                if lit_at[j] is None:
                    o.hide_render = True
                    continue
                # NEAR CULL, on real geometry: drop a cell only while some of
                # its surface is at the lens. Its fade state is kept, so it
                # returns lit rather than starting over once the camera clears.
                # Two independent fades, and the dimmer wins: how long since
                # the cell woke up, and how close it now is to the lens.
                lvl = min(1.0, (i - lit_at[j]) / FADE)
                near = (dmin[j] - NEAR0) / max(1e-6, NEAR1 - NEAR0)
                lvl = min(ease_io(lvl), ease_io(near))
                if lvl <= 0.02:
                    o.hide_render = True
                else:
                    o.hide_render = False
                    solo_material(o, rgbs[j], lvl)

            # Off the lens axis, or it lights everything head on and flattens
            # exactly what it was added to model.
            cm = cam.matrix_world
            lamp.location = (Vector(cam.location)
                             + cm.to_quaternion() @ Vector((TARGET_SIZE * 0.10,
                                                            TARGET_SIZE * 0.13,
                                                            TARGET_SIZE * 0.04)))

            scene.render.filepath = out
            bpy.ops.render.render(write_still=True)
            if i % 40 == 0:
                vis = sum(1 for _, o in loaded if not o.hide_render)
                culled = int((dmin < NEAR0).sum())
                print("  frame %d/%d  lit %d  visible %d  nearculled %d  eye %s"
                      % (i, args.flythrough, sum(x is not None for x in lit_at),
                         vis, culled, np.round(eye_now, 2)))

        meta["frames"] = args.flythrough
        meta["mode"] = "flythrough"
        with open(os.path.join(args.out, "scene.json"), "w") as fh:
            json.dump(meta, fh, indent=1)
        a = os.path.join(args.out, "frame_0000.png")
        b = os.path.join(args.out, "frame_%04d.png" % (args.flythrough // 2))
        print("frames differ:", frames_differ(a, b))
        print("wrote %d frames to %s" % (args.flythrough, args.out))
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
    # BLENDER EXITS 0 EVEN WHEN THE SCRIPT RAISES. A chained render script then
    # reads success and moves on: the flythrough leg once raised on its first
    # line, rendered nothing, and the chain log said "flythrough done". So
    # convert a traceback into a non-zero exit, and print a sentinel on success
    # that a caller can grep for instead of trusting the exit code alone.
    try:
        main()
    except SystemExit:
        raise
    except Exception:
        traceback.print_exc()
        sys.stdout.flush()
        sys.stderr.flush()
        sys.exit(1)
    print("RENDER_OK")
    sys.stdout.flush()
