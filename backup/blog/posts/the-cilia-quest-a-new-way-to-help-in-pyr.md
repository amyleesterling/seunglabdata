---
title: "The Cilia Quest: a new way to help in Pyr"
summary: "Quests are a new kind of task in Pyr. Your challenge, should you choose to accept it, is to find and tag the primary cilium on starburst cells in the retina, without ever having to proofread the cell."
author: "Amy R. Sterling"
published: 2026-10-13T20:45:54.387+00:00
updated: 2026-11-06T16:56:49.68+00:00
cover: https://javthknksdcrlhiaaptj.supabase.co/storage/v1/object/public/admin-uploads/blog/6afa305c257b45ab2518c340/a3637476-317f-4c15-8980-2c70a66ee2bc.png
---
Calling all Pyr players! there's a new **Quest** on the horizon, and we need your help!

> We're on the hunt for **primary cilia**, important cellular appendages that receive and process environmental signals. Cilia serve as “antennas” that cells use to sense the chemistry of their environment. Each cell only has one primary cilium, will you be the one to find it?

## How to Hunt for Cilia

1. Open the **Cell Library** and click **Quests**. If you are on another dataset, press **Switch to Retina**.
2. Press **Claim** on an available cell. The cell and it's annotation layers will open on screen. Each cell in a Cilia Quest is retinal neuron. Somewhere on its cell body there may be a cilium, a thin appendage that projects from. This is what we quest for.
3. Find the cilium (if there is one). At its base sits the basal body, and close by is a second structure, the daughter centriole. Mark all 3 structures, if present.
4. Put the crosshairs inside the cell and press **Submit**.
5. Choose a cilium status from the list. Don't know which to choose? Select your guess to see help text below. Or [check out this post](https://connectome.quest/blog/cilia-status-guide/) for a full explanation of all statuses with examples!
6. Select whether the cilium was "split" - part of all of the cilium was not attached, or "merged" - cilium was fully visible in the original segmentation. If no cilium was present, make no selection.
7. Add a note if needed, and press the 2nd Submit button!

You can hold three cells at a time. **Release** sends a cell back for someone else.

![](https://javthknksdcrlhiaaptj.supabase.co/storage/v1/object/public/admin-uploads/blog/69930a0febedc717a52b10fd/1e17ed53-6add-43dc-99af-c617744e3a95.png)

About each structure:

- **Cilium** - a columnar structure that projects from the cell's soma. Microtubules should be visible inside (greyish lines).
- **Basal body** - a centriole at the base of cilium. It's always inside to the soma membrane. When no cilium is present, there may still be a basal body.

- **Daughter centriole** - A second centriole. It is often found near, but not attached to the basal body. In some cases it can be very far from the BB -- keep scrolling!

***Important note!*** Some cells have no visible cilium, but often you will still be able to locate the two centrioles inside the soma.

## annotating the structures

To annotate a cilium, you'll need to use the 3 annotation layers. Click a layer to select it.

- **Polyline annotation** - use this to annotate the **cilium centerline**. Once selected, Ctrl and click along the cilium, then press Enter. Backspace removes the last point and Esc cancels the line.
- **Point annotation** - use this to annotate the **basal body (BB)** and **daughter centriole (DC)**. CTRL + click to place it. Always double check your layer when placing!

## Putting it all together

[Here's an example](https://eyewire-ii-community-dot-brain-wire-dot-seung-lab.ue.r.appspot.com/#!middleauth+https://global.brain-wire-test.org/nglstate/api/v1/5973814101934080) of a cell with a cilium that's been fully annotated and is ready to complete!

![Cell with cilium annotated](https://javthknksdcrlhiaaptj.supabase.co/storage/v1/object/public/admin-uploads/blog/6afa305c257b45ab2518c340/1d7519ca-1702-4af7-8fbb-daa063bb91d4.png){medium}
^ Cell with cilium annotated

## Dive Deeper

- [The lab's scientific guide to cilia with tips on how to locate them.](https://unitc-my.sharepoint.com/:p:/g/personal/ojxjl01_cloud_uni-tuebingen_de/IQDBsH6sbIjZRY5Gc3Flt5iaAUvXSDf4QLsyamGQ72f8rOo?rtime=Ky2GsGU730g)

- A [training video](https://www.youtube.com/watch?v=-l2-R-9vX6o&t=1525s).

A quick guide to each cilia status type you may encounter. Click each one to see an example. Happy Hunting!

- **[Cilium Annotated](https://eyewire-ii-community-dot-brain-wire-dot-seung-lab.ue.r.appspot.com/#!middleauth+https://global.brain-wire-test.org/nglstate/api/v1/6134465776582656)** - Cilium emerges from the cell, both centrioles and cilium centerline are annotated.
- **[Cilium Annotated (fixation artifact)](https://eyewire-ii-community-dot-brain-wire-dot-seung-lab.ue.r.appspot.com/#!middleauth+https://global.brain-wire-test.org/nglstate/api/v1/6224937215852544)** - Cilium structure is visible near the surface of the cell, but appears attached/internal to the soma. This is caused by membranes fusing during data collection.
- **Need Help** - You can't find any cilium or centrioles, or there's another issue that stops you from annotating the cell. Good to leave clarifying notes in most cases!
- **[Need Help: One centriole missing](https://eyewire-ii-community-dot-brain-wire-dot-seung-lab.ue.r.appspot.com/#!middleauth+https://global.brain-wire-test.org/nglstate/api/v1/6697415730003968)** - You found one centriole, but the other is MIA
- **No cilium** - Nothing found. This should only be used after review (use Need Help if you are the first annotator)
- **[No cilium (BB & DC clear)](https://eyewire-ii-community-dot-brain-wire-dot-seung-lab.ue.r.appspot.com/#!middleauth+https://global.brain-wire-test.org/nglstate/api/v1/5742473875816448)** - No cilium, but centrioles are visible and clearly differentiated (basal body closer to the surface).
- **[No cilium (BB & DC unclear)](https://eyewire-ii-community-dot-brain-wire-dot-seung-lab.ue.r.appspot.com/#!middleauth+https://global.brain-wire-test.org/nglstate/api/v1/5185996505219072)** - No cilium, centriole positions make it unclear which is the basal body and which is the daughter
- **[Skipped (low quality)](https://eyewire-ii-community-dot-brain-wire-dot-seung-lab.ue.r.appspot.com/#!middleauth+https://global.brain-wire-test.org/nglstate/api/v1/6280972446203904)** - Extensive data artifacting, missing slides, no soma etc, make it too difficult to ID cilium or centrioles

Where your answer goes

When you submit, your status, your notes and a link to your view go to the lab, with your name and the date. Pyr celebrates with you and tells you how many annotations you placed on that cell and how many Quests you have completed. Your profile keeps the count.

## Tell us how it goes

The Cilia Quest is our very first Quest! If something is unclear or could work better, ask in chat or send a report with the feedback button.
