"""
Blender: render MEC cells as stills, one cell per image.

Doubles as the poster images for the "Meet an MEC neuron" gallery on
connectome.quest/mec, so the card a visitor sees before loading 3D is a real
render of the same cell.

Follows D:\\Meshes\\RENDERING_NEURONS.md:
  * IOR 1.04, not 1.38. Neurons are submerged; submerged tissue is not glossy.
  * Subsurface carries the softness. Emission is NOT a substitute for lighting.
  * View transform Standard, not AgX, or the colours wash out.
  * Real three-point area lights scaled to the subject, plus a world.
  * EEVEE motion blur OFF always (it has crashed this machine before).
  * Assert the subject actually landed inside the scene before rendering.

Run:
  blender --background --factory-startup --python tools/render_mec_cells.py -- \
      --cells assets/mec/cells/cells.json --out renders/mec --size 1200 \
      [--only stellate-01,pyramidal-01] [--tier detail]
"""

import argparse
import json
import math
import os
import sys

import bpy
import numpy as np
from mathutils import Vector

TARGET_SIZE = 10.0          # longest axis of the framed cell, in Blender units
SUBSURFACE_SCALE = 0.012 * TARGET_SIZE

# Solid colours, chosen to stay distinct under a 5200 W key with Standard view
# transform. These are the render colours; check them IN the render, never in a
# picker.
# Amy's house palette, taken from the CA3 page and scifi-ui rather than
# invented: accent #3E96F0, mint #67f5cb, cyan #7ee0ff, gold #E8A93A,
# orchid #e8afd8, lilac #bd9bd1, on the #07080B ground both sites use.
# Still check them IN the render, never in a picker.
TYPE_COLOUR = {
    "stellate":        (0.404, 0.961, 0.796),   # #67f5cb mint
    "pyramidal":       (0.243, 0.588, 0.941),   # #3E96F0 accent
    # The pale end of the palette blows out under this rig and rendered as
    # near-white: orchid, lilac and steel all lost their hue. Deepened here,
    # same hues, so they READ as themselves in the render rather than in the
    # picker. The UI keeps the light versions.
    "inhibitory":      (0.776, 0.318, 0.639),   # #c651a3, orchid deepened
    "microglia":       (0.910, 0.663, 0.227),   # #E8A93A gold
    "astrocyte":       (0.561, 0.373, 0.690),   # #8f5fb0, lilac deepened
    "oligodendrocyte": (0.310, 0.741, 0.902),   # #4fbde6, cyan deepened
    "bipolar":         (0.490, 0.573, 0.671),   # #7d92ab, steel deepened
}


def argv_after_ddash():
    return sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []


def clear_scene():
    bpy.ops.wm.read_factory_settings(use_empty=True)


def import_glb(path):
    before = set(bpy.data.objects)
    bpy.ops.import_scene.gltf(filepath=path)
    new = [o for o in bpy.data.objects if o not in before and o.type == "MESH"]
    if not new:
        raise RuntimeError(f"no mesh imported from {path}")
    for o in new:
        o.select_set(True)
    bpy.context.view_layer.objects.active = new[0]
    if len(new) > 1:
        bpy.ops.object.join()
    obj = bpy.context.view_layer.objects.active
    # Bake every importer transform into the vertices so nothing downstream has
    # to reason about whose rotation runs before whose location. This is the
    # class of bug section 5 of the playbook is about.
    bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
    return obj


def frame_object(obj):
    """Centre on the origin and scale so the longest axis is TARGET_SIZE."""
    bpy.context.view_layer.update()
    # Percentile bounds, not the object bounding box. These meshes routinely
    # carry a few vertices far from everything else, and a raw min/max box
    # collapses the auto-scale computed from it.
    co = np.empty(len(obj.data.vertices) * 3, dtype=np.float32)
    obj.data.vertices.foreach_get("co", co)
    pts = co.reshape(-1, 3) @ np.array(obj.matrix_world.to_3x3()).T +         np.array(obj.matrix_world.translation)
    lo = Vector(np.percentile(pts, 0.5, axis=0).tolist())
    hi = Vector(np.percentile(pts, 99.5, axis=0).tolist())
    span = hi - lo
    longest = max(span)
    if longest <= 0:
        raise RuntimeError("degenerate mesh bounds")
    scale = TARGET_SIZE / longest
    centre = (lo + hi) * 0.5

    obj.location = -centre * scale
    obj.scale = (scale, scale, scale)
    bpy.context.view_layer.update()          # matrix_world reads STALE without this

    co2 = np.empty(len(obj.data.vertices) * 3, dtype=np.float32)
    obj.data.vertices.foreach_get("co", co2)
    pts2 = co2.reshape(-1, 3) @ np.array(obj.matrix_world.to_3x3()).T +         np.array(obj.matrix_world.translation)
    reach = float(np.abs(np.percentile(pts2, [0.5, 99.5], axis=0)).max())
    # One cheap assert catches every version of the coordinate-space mistake.
    assert reach < TARGET_SIZE, f"coordinate spaces disagree: reach {reach:.2f}"
    return span * scale, span


def shade(obj, rgb):
    mat = bpy.data.materials.new("neuron")
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes["Principled BSDF"]
    bsdf.inputs["Base Color"].default_value = (*rgb, 1.0)
    bsdf.inputs["Roughness"].default_value = 0.62
    bsdf.inputs["IOR"].default_value = 1.04          # tissue in water, NOT 1.38
    for name, value in (("Subsurface Weight", 0.35),
                        ("Subsurface Radius", (SUBSURFACE_SCALE,) * 3),
                        ("Subsurface Scale", SUBSURFACE_SCALE)):
        if name in bsdf.inputs:
            bsdf.inputs[name].default_value = value
    if "Emission Color" in bsdf.inputs:
        bsdf.inputs["Emission Color"].default_value = (*rgb, 1.0)
    if "Emission Strength" in bsdf.inputs:
        # Neurites here are under a micrometre across, so at card size they
        # catch almost no light. This is a lift so they read, NOT a
        # replacement for the light rig, which is still doing the work.
        bsdf.inputs["Emission Strength"].default_value = 0.16
    obj.data.materials.clear()
    obj.data.materials.append(mat)
    for poly in obj.data.polygons:
        poly.use_smooth = True


HDRI = os.path.join(bpy.utils.resource_path("LOCAL"),
                    "datafiles", "studiolights", "world", "studio.exr")
# #07080B as LINEAR values. The compositor works in linear, so pasting the
# sRGB hex straight in renders it several times too light: this background
# came out navy instead of near black the first time.
GROUND = (0.0021, 0.0024, 0.0034, 1.0)   # #07080B, the ground both of Amy's sites use


def light_the_scene(hdri=True, hdri_strength=1.10, light_scale=0.0):
    """Three-point area lights scaled to the subject, PLUS a world HDRI.

    The playbook's baseline is a three point rig PLUS an HDRI. For THIS subject
    the rig does not earn its keep and the default is HDRI only, which was
    measured, not assumed: against HDRI 0.30 with the full rig, HDRI 1.10 with
    no rig changed the lit pixel count by 6% and the mean lit colour by 4%.
    Sub-micrometre neurites have almost no surface facing any one direction, so
    a key/fill/rim has little to grip and the omnidirectional HDRI does the
    work. Pass --lights 1.0 to bring the rig back for a chunkier subject.

    The visible background is handled by film transparency plus a composite, so
    the card sits on exactly #07080B rather than on whatever colour the
    environment happens to be.
    """
    world = bpy.data.worlds.new("world")
    world.use_nodes = True
    nt = world.node_tree
    bg = nt.nodes["Background"]
    if hdri and os.path.exists(HDRI):
        env = nt.nodes.new("ShaderNodeTexEnvironment")
        env.image = bpy.data.images.load(HDRI, check_existing=True)
        env.location = (-320, 0)
        nt.links.new(env.outputs["Color"], bg.inputs["Color"])
        # Enough to fill the shadow side, not enough to wash the hue out.
        # At 0.55 the mint read as pale cyan.
        bg.inputs[1].default_value = hdri_strength
    else:
        print("    WARNING: studio HDRI not found, falling back to a flat world")
        bg.inputs[0].default_value = GROUND
        bg.inputs[1].default_value = 0.40
    bpy.context.scene.world = world

    rig = [("key", (9, -11, 7), 5200, 12),
           ("fill", (-11, -6, 2), 1700, 16),
           ("rim", (-3, 10, 8), 2600, 10)]
    if light_scale <= 0:
        return
    for name, loc, power, size in rig:
        power *= light_scale
        data = bpy.data.lights.new(name, type="AREA")
        data.energy = power
        data.size = size
        obj = bpy.data.objects.new(name, data)
        obj.location = loc
        direction = Vector((0, 0, 0)) - Vector(loc)
        obj.rotation_euler = direction.to_track_quat("-Z", "Y").to_euler()
        bpy.context.collection.objects.link(obj)


def add_camera(distance, azimuth_deg=38.0, elevation_deg=22.0, shift_y=0.0, shift_x=0.0):
    data = bpy.data.cameras.new("cam")
    data.lens = 62
    cam = bpy.data.objects.new("cam", data)
    a, e = math.radians(azimuth_deg), math.radians(elevation_deg)
    cam.location = (distance * math.cos(e) * math.cos(a),
                    distance * math.cos(e) * math.sin(a),
                    distance * math.sin(e))
    cam.rotation_euler = (Vector((0, 0, 0)) - Vector(cam.location)).to_track_quat("-Z", "Y").to_euler()
    # An elevated camera does not project a bounding-box centre to the frame
    # centre, and these arbors are dense at the top and sparse below, so the
    # content sat high with a 20x margin imbalance. Solved by measuring the
    # render, not by eye. shift_y is a fraction of the sensor's LARGER side.
    data.shift_y = shift_y
    data.shift_x = shift_x
    bpy.context.collection.objects.link(cam)
    bpy.context.scene.camera = cam
    return cam


def composite_ground(scene):
    """Put a solid ground colour behind the transparent render."""
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


def configure_render(size, samples=96):
    scene = bpy.context.scene
    scene.render.engine = "BLENDER_EEVEE_NEXT"
    scene.render.resolution_x = size
    scene.render.resolution_y = size
    scene.render.resolution_percentage = 100
    # The HDRI lights the cell but must not be what the camera sees, or the card
    # background stops matching the page. Render the world out and put the exact
    # ground colour back in the compositor.
    scene.render.film_transparent = True
    scene.view_settings.view_transform = "Standard"     # NOT AgX
    composite_ground(scene)
    ee = scene.eevee
    # Motion blur has crashed EEVEE on this machine. Off, always.
    if hasattr(ee, "use_motion_blur"):
        ee.use_motion_blur = False
    for attr, value in (("taa_render_samples", samples),
                        ("use_gtao", True),
                        ("use_bloom", False)):
        if hasattr(ee, attr):
            setattr(ee, attr, value)


PROBE_SIZE = 260
TARGET_FILL = 0.80          # 100% means clipped; leave real margin
# Measured response: a shift of +0.198 moved the content centre by +0.157 of
# the frame, so the correction gain is 1/0.79. A gain of 1.9 overshot past
# centre and clipped.
SHIFT_GAIN = 1.25


def measure_render(path):
    """Lit bounding box of a rendered still, as fractions of the frame.

    The background is not black (the world has a colour), so the threshold is
    taken FROM the corners of this very image rather than assumed. Assuming a
    black background reported every frame as 100% full and hid a real clip.
    """
    img = bpy.data.images.load(path)
    try:
        w, h = img.size
        px = np.array(img.pixels[:], dtype=np.float32).reshape(h, w, 4)
        lum = px[:, :, :3].max(axis=2)
        lum = lum[::-1]                                   # Blender pixels are bottom-up
        corners = [lum[1, 1], lum[1, -2], lum[-2, 1], lum[-2, -2]]
        thr = float(np.median(corners)) + 0.10
        lit = lum > thr
        rows = np.where(lit.any(axis=1))[0]
        cols = np.where(lit.any(axis=0))[0]
        if not len(rows):
            return None
        return {
            "fill": max((rows[-1] - rows[0]) / h, (cols[-1] - cols[0]) / w),
            "cy": (rows[0] + rows[-1]) / 2.0 / h - 0.5,   # + means content sits low
            "cx": (cols[0] + cols[-1]) / 2.0 / w - 0.5,   # + means content sits right
            "clipped": bool(rows[0] <= 1 or rows[-1] >= h - 2 or cols[0] <= 1 or cols[-1] >= w - 2),
        }
    finally:
        bpy.data.images.remove(img)


def solve_framing(probe_path, dist_mult):
    """Render a small probe, measure it, and return framing that fits.

    Arbors here are dense at the top and sparse below, so a bounding-box centre
    does not project to the frame centre and the subject sits high and to one
    side. Signs were established empirically: raising shift_y moves content
    DOWN in frame, lowering shift_x moves it RIGHT.
    """
    configure_render(PROBE_SIZE, 8)
    bpy.context.scene.render.filepath = probe_path
    bpy.ops.render.render(write_still=True)
    m = measure_render(probe_path)
    if not m:
        return dist_mult, 0.0, 0.0, None
    shift_y = -m["cy"] * SHIFT_GAIN
    shift_x = m["cx"] * SHIFT_GAIN
    new_dist = dist_mult * (m["fill"] / TARGET_FILL)
    new_dist = max(1.15, min(new_dist, 3.2))
    return new_dist, shift_y, shift_x, m


def render_cell(cell, glb_path, out_path, size, samples, dist_mult=1.85,
                shift_y=0.0, shift_x=0.0, autoframe=True,
                hdri_strength=1.10, light_scale=0.0):
    clear_scene()
    obj = import_glb(glb_path)
    scaled_span, raw_span = frame_object(obj)
    shade(obj, TYPE_COLOUR.get(cell.get("cell_type", ""), (0.8, 0.8, 0.8)))
    light_the_scene(hdri_strength=hdri_strength, light_scale=light_scale)
    cam = add_camera(distance=TARGET_SIZE * dist_mult, shift_y=shift_y, shift_x=shift_x)
    measured = None
    if autoframe:
        probe = os.path.join(os.path.dirname(out_path) or ".", "_probe.png")
        dist_mult, shift_y, shift_x, measured = solve_framing(probe, dist_mult)
        bpy.data.objects.remove(cam, do_unlink=True)
        add_camera(distance=TARGET_SIZE * dist_mult, shift_y=shift_y, shift_x=shift_x)
        if os.path.exists(probe):
            os.remove(probe)
    configure_render(size, samples)
    bpy.context.scene.render.filepath = out_path
    bpy.ops.render.render(write_still=True)
    final = measure_render(out_path)
    # A clipped card is a broken card. Keep backing off and re-centring until
    # it fits, rather than shipping a cropped cell. One retry was not enough:
    # an oligodendrocyte stayed clipped after a single 1.14x step, because the
    # first pass had also left it off centre.
    tries = 0
    while autoframe and final and final["clipped"] and tries < 5:
        tries += 1
        dist_mult *= 1.16
        shift_y += -final["cy"] * SHIFT_GAIN
        shift_x += final["cx"] * SHIFT_GAIN
        print(f"    clipped, retry {tries}: dist {dist_mult:.2f} shift ({shift_x:+.3f},{shift_y:+.3f})")
        for o in [o for o in bpy.data.objects if o.type == "CAMERA"]:
            bpy.data.objects.remove(o, do_unlink=True)
        add_camera(distance=TARGET_SIZE * dist_mult, shift_y=shift_y, shift_x=shift_x)
        bpy.ops.render.render(write_still=True)
        final = measure_render(out_path)
    if final and final["clipped"]:
        print("    STILL CLIPPED after retries; this card is not usable as is")
    return raw_span, dist_mult, shift_y, shift_x, measured, final


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cells", required=True, help="cells.json from mec_meshes.py")
    ap.add_argument("--out", required=True)
    ap.add_argument("--size", type=int, default=1200)
    ap.add_argument("--samples", type=int, default=96)
    ap.add_argument("--tier", default="detail")
    ap.add_argument("--only", default="", help="comma separated cell ids")
    ap.add_argument("--dist", type=float, default=1.85,
                    help="camera distance as a multiple of TARGET_SIZE")
    ap.add_argument("--shifty", type=float, default=0.0)
    ap.add_argument("--shiftx", type=float, default=0.0)
    ap.add_argument("--no-autoframe", action="store_true")
    ap.add_argument("--hdri", type=float, default=1.10)
    ap.add_argument("--lights", type=float, default=0.0,
                    help="scale on the three point rig; 0 disables it")
    args = ap.parse_args(argv_after_ddash())

    with open(args.cells) as fh:
        manifest = json.load(fh)
    cells = manifest["cells"]
    if args.only:
        wanted = {c.strip() for c in args.only.split(",") if c.strip()}
        cells = [c for c in cells if c["id"] in wanted]
    os.makedirs(args.out, exist_ok=True)
    mesh_dir = os.path.dirname(os.path.abspath(args.cells))

    print(f"rendering {len(cells)} cells at {args.size}px, tier {args.tier}")
    for i, cell in enumerate(cells, 1):
        tier = cell["tiers"].get(args.tier) or next(iter(cell["tiers"].values()))
        glb = os.path.join(mesh_dir, tier["file"])
        out = os.path.join(args.out, f"{cell['id']}.png")
        print(f"[{i}/{len(cells)}] {cell['id']} ({cell.get('cell_type')}) "
              f"{tier.get('faces','?')} faces -> {out}")
        span, d, sy, sx, probe, final = render_cell(
            cell, glb, out, args.size, args.samples, args.dist, args.shifty,
            args.shiftx, autoframe=not args.no_autoframe,
            hdri_strength=args.hdri, light_scale=args.lights)
        print(f"    span {tuple(round(v, 1) for v in span)} um")
        if probe:
            print(f"    probe fill {probe['fill']:.3f} off ({probe['cx']:+.3f},{probe['cy']:+.3f})"
                  f" -> dist {d:.2f} shift ({sx:+.3f},{sy:+.3f})")
        if final:
            flag = "  CLIPPED" if final["clipped"] else ""
            print(f"    final fill {final['fill']:.3f} off "
                  f"({final['cx']:+.3f},{final['cy']:+.3f}){flag}")
        print(f"    wrote {out}")


if __name__ == "__main__":
    main()
