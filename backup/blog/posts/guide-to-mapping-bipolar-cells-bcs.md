---
title: "Guide to Mapping Bipolar Cells (BCs)"
summary: "Every image you see passes through a bipolar cell. Learn what these relay cells do and how to proofread one in Pyr."
author: "Amy R. Sterling"
published: 2026-11-05T03:14:15.686+00:00
updated: 2026-11-08T22:46:06.302+00:00
cover: https://javthknksdcrlhiaaptj.supabase.co/storage/v1/object/public/admin-uploads/blog/6afa305c257b45ab2518c340/07da7cda-f665-4142-ae8e-4479fca7634c.jpg
---
Every image you have ever seen passed through a bipolar cell. These small and tidy cells sit in the middle of the retina. In Eyewire II/ Pyr's retina dataset, they are some of the cells you will encounter most frequently. Here is what they do and how to proofread one.

## What bipolar cells do

Light hits the photoreceptors (the rods and cones) at the back of the retina. The photoreceptors can't talk to the brain directly. They hand their signal to bipolar cells, and the bipolar cells pass it on to both amacrine and ganglion cells. Ganglion axons form the optic nerve and send a pre-processed signal carrying information about objects and movement from the eye to the brain.

![How we see: the eye, with a close look at the retina's cells](https://connectome.quest/assets/images/blog/bipolar-cells/eye-diagram.webp)
@[phone](https://connectome.quest/assets/images/blog/bipolar-cells/eye-diagram-phone.webp)

Bipolar cells are a critical relay step, and the direct path from photoreceptor to neuron.

![How a signal flows through the retina: photoreceptors, a bipolar cell, a starburst amacrine cell and a ganglion neuron, real cells from Eyewire II at their true depths](https://connectome.quest/assets/images/blog/bipolar-cells/real-retina-cells.webp)
@[phone](https://connectome.quest/assets/images/blog/bipolar-cells/real-retina-cells-phone.webp)

@[youtube](u7TOLm2HXRk)

Bipolar cells are also part of EyeWire history. EyeWire players reconstructed bipolar cells and the starburst amacrine cells they connect to. The work showed that bipolar types with different timing connect to different parts of the starburst cell, a wiring pattern that helps the retina tell which way something is moving, which became the first ever Eyewire publication in the prestigious journal Nature back in 2014 (Kim et al., Nature).

Today, Eyewire II players are carrying that work forward, and you have already mapped more than 10,000 cells together:

@[youtube](LUYDh1yROzg)

Every bipolar cell you proofread in Pyr adds to that map. If you'd like to learn more about the science, scroll to the bottom of the post. Below find instructions on how to proofread Bipolar Cells (BCs).

## Claiming a BC

1. Head to the **Retina Dataset** (if you don't have access yet, see [this post](https://connectome.quest/blog/how-to-unlock-edit-access-in-pyr/)).
2. Open the **Cell Library**, navigate to **Available Cells**, and **Claim** one.
3. **Proofread** the cell (instructions below)
4. When you have fully proofread the BC, mark it **Complete**

## How to proofread a BC

Check the whole cell, branch by branch:

- **Dendrites:** follow each one up to its tip. Look for pieces that broke off (they need a merge) and pieces of other cells stuck on (they need a cut).
- **Axon:** follow it down to the terminals, and check that the terminals all belong to this cell.
- **Each branch end:** a bipolar cell has many small ends. Check every one.

![A real bipolar cell proofread in Eyewire II, with its dendrites, cell body, axon and axon terminals labeled](https://connectome.quest/assets/images/blog/bipolar-cells/real-bipolar-cell.webp)

## Keep track of what you checked

A bipolar cell has lots of small branch ends, and for proofreading accuracy you must mark each one as you finish it. **You may use Highlight OR Annotations**. Or both if you're crazy. Use whichever tool you like best. The only annotation that is required is "Can't Complete", which should be used to mark any spots on the branches that cannot be traced due to issues like EM image quality.

**Highlight Mode**

- Turn on Highlight Mode from its icon in the top bar.
- **Ctrl+click** two points on the cell, and the stretch between them is marked with a highlighter stroke.
- **To soma** marks the way from a point back to the cell body, and the button beside it marks every branch beyond a point.
- Pick a color, or add your own, and press **Undo** if you mark the wrong piece.

**Annotations**

- Make an annotation layer and pick the point tool.
- **Ctrl+click** to drop a point on each branch end you have checked.
- Change the layer's color and point size so your points are easy to see.
- Points are listed in the layer's panel: **right click** one to jump to it, or step through them with the arrows.

Some people like Highlight because it colors the branch itself. Others like annotation points because they can step through them one by one later. Either way, when every end is marked, you know the cell is done and you can mark it complete and claim another. If you get stuck, you can ask for help in Chat or via the Help feature in the Cell Library.

Happy proofreading, and thank you for helping map the brain!

## More Science!

Check out the cast of the retina [here](https://amyleesterling.github.io/retina/cast/).

Each bipolar cell has two ends, which is where the name comes from:

- **Dendrites** reach up to the photoreceptors and collect their signal.
- **An axon** runs down into the inner retina and ends in a spray of **axon terminals**, where it passes the signal on.

![A bipolar cell, drawn and labeled, beside a real one from Eyewire II](https://connectome.quest/assets/images/blog/bipolar-cells/bipolar-cell-diagram.webp)
@[phone](https://connectome.quest/assets/images/blog/bipolar-cells/bipolar-cell-diagram-phone.webp)

### Why they matter

Bipolar cells don't just pass the picture along. They split it up.

- **ON and OFF.** Some bipolar cells respond when light gets brighter (ON), others when it gets darker (OFF). In the mouse, types 1 to 4 are OFF, and types 5 to 9 and the rod bipolar cell are ON.
- **About 15 types.** Each type reports a different piece of the scene: fast or slow changes, light or dark, fine detail or broad strokes. The rod bipolar cell carries vision in dim light.
- **Layers.** Each type ends its axon at its own depth in the inner retina, so the signals stay sorted into separate channels, like wires in a cable.

These parallel channels are the raw material for everything the retina computes before the brain sees anything. So if you think about it, your BCs are helping to map BCs and uncovering how mammalian eyes see. Pretty cool!
