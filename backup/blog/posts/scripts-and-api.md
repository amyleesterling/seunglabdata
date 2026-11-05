---
title: "Write your own scripts for EyeWire II"
summary: "EyeWire II now has a small set of tools for player scripts, plus a guide to get you started with Tampermonkey. Also this week: split screen replaces the 4 panel view, your view saves itself, and the fly nerve cord joins the dataset list."
author: "Amy and the EyeWire team"
published: 2026-10-02T16:00:00+00:00
updated: 2026-10-03T14:49:40.877209+00:00
cover: 
---
Players of the original EyeWire built some of its best features themselves. Bigger annotation dots, extra statistics, faster ways to get around: many of them started as a script one player wrote for their own browser and then shared.

EyeWire II now supports that properly. There is a guide for getting started, and a small set of tools made for scripts to use.

## What a script is

A script is a small piece of code that changes the game on your computer only. It runs through Tampermonkey, a free browser extension. Nobody else sees your script, and you do not need permission to write one.

## What scripts can use

Until now a script had to reach into the inner workings of the game, which change with almost every update. So scripts broke often. The new tools are the parts we promise to keep working:

- **Your cells and your view.** The cells you have selected, the cell under the crosshairs, your claims, and where you are looking.
- **Events.** Run your code when you claim, release or complete a cell, when your selection changes, or when you switch datasets.
- **A button and a panel.** Add your own button to the top bar and your own side panel.
- **Annotation layers.** Make a layer of your own and add points and lines to it.
- **Settings.** Save your script's settings in your browser.

Everything else is still open. Scripts can reach the viewer directly for anything the tools do not cover.

[Open the scripts guide](https://eyewire-ii-community-dot-brain-wire-dot-seung-lab.ue.r.appspot.com/scripts.html)

The guide has setup steps, the full list of tools, and six example scripts you can copy.

## A word on safety

A script runs as you. It can do anything you can do in the game, including editing cells with your sign in. Scripts you write yourself are fine. Before you install a script from someone else, read it, or ask in chat whether others use it. Scripts are made by players and are not reviewed by the EyeWire team.

## Tell us what is missing

We asked the script writers on the forum what they need, and the answer was that scripts grow out of whatever rough edge someone notices that week. So the list of tools starts small on purpose. If your script needs something that is not there, [ask on the forum](https://forum.eyewire.org/t/pyr-eyewire-ii-api-requests/2246/4) and we will add it.

## Also new this week

- **Split screen replaces the 4 panel view.** Press Space to flip between split screen and the single panel under your mouse. Nothing lands you in 4 panel any more.
- **Your view saves itself.** Annotations, layers and position are saved to your account as you work. Open the game on any computer and it offers to pick up where you left off.
- **Save view on a claim.** In the Cell Library, the cell you are working on has a Save view button, so your annotations stay with the cell.
- **The fly brain and nerve cord.** BANC is now in the dataset switcher, and the three MICrONS versions share one card.
- **Claim several cells at once.** The Cell Library can fill your claims from the Available list in one click.
- **A faster Cell Library.** Your own cells load first, and long lists draw 200 rows at a time.
