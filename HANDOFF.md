# Connectome Quest — Handoff

Hand this to a new chat to continue work on **connectome.quest** (the "Citizen Neuroscience" site).

## What it is
A public site for the Seung Lab's connectomics datasets and citizen science. Visitors learn about the brain, watch neuron videos, and find out how to start proofreading (mapping) real neurons.

## Repos, hosting, deploy
- **Main site**: `C:\Users\amyle\seunglabdata` → GitHub `amyleesterling/seunglabdata` → live at **https://connectome.quest** (GitHub Pages, HTTPS enforced, Let's Encrypt cert). Static HTML/CSS/JS, no build step. **Deploy = commit + push to `main`.**
  - Domain is Porkbun (`connectome.quest`, NOT connectomics.quest). Apex A records 185.199.108–111.153 + AAAA 2606:50c0:8000–8003::153. `CNAME` file = connectome.quest.
  - HTTPS was fixed via the GitHub Pages API (remove/re-add domain to provision the cert, then `https_enforced=true`).
- **Inner Cosmos** (separate project, embedded on the Learn page): `C:\Users\amyle\hidden-worlds` → GitHub `amyleesterling/inner_cosmos` → live at **https://amyleesterling.github.io/inner_cosmos/**. Vite + React + TS + Tailwind + Three.js. **Deploy = commit + push to `main`** (GitHub Actions `deploy.yml`; run `npm run build` to verify first). Note: `C:\Users\amyle\inner_cosmos` is a stale clone of the same repo — edit `hidden-worlds`.

## Pages (all in seunglabdata)
- `index.html` — **Datasets**. Hero, "We need your help" (EyeWire II + FlyWire BANC highlight cards), "More datasets" grid (FlyWire, EyeWire, MICrONS, Pyr), "Learn how to map the brain" (embedded Neuroglancer tutorial), citizen science stats, "Resources for Citizen Scientists", footer with tiny cat mascot.
- `learn.html` — **Learn**. Full-viewport iframe of the Inner Cosmos `/explore` guided zoom, then a "Why we map the brain" section + "Get involved" button. Share/Fullscreen controls are top-left (so they don't collide with the Inner Cosmos nav).
- `videos.html` — **Videos**. Channels first (FlyWire Princeton, EyeWire, Pyr), then Neuron Animations playlist, then Mammalian and Fly neuron galleries (thumbnail tiles → individual YouTube videos, each with a one-line description).
- `help.html` — **Help**. Contact form (Formsubmit → support@eyewire.org, WORKING), forum link, getting started, "Learn to use the software" tutorial playlists. Trailblaze mascot top-right, Nurro at bottom.
- `access.html` — **Access**. 4-step get-access flow (sandbox → 10 example edits → submit via email → invitation), resources, two sandboxes (mouse retina + fly, fly needs Google login). Rika mascot top, Nurro midway.

## Conventions / preferences (IMPORTANT)
- **NO DASHES** in copy. No em-dashes (—) or en-dashes (–). Use commas/periods/colons. (Hyphens in compound words are fine.)
- **Theme**: blue `#42d5ec` for links/eyebrows/flags/structure, yellow `#e6c760` for primary CTA buttons and the "help!" accent. No gradient text (Amy finds it "too AI").
- Mascots displayed **small**; source art is huge, so resize (PIL/ImageMagick) into `assets/images/` before use. Existing: `rika-welcome.png`, `nurro-experiment.png`, `trailblaze.png`, `footer-tiny.png` (cat); Inner Cosmos hero `hidden-worlds/public/hero-rika-nurro.png`.
- Contact/support email is assembled at runtime in JS (not a plain-text literal) to avoid scrapers.

## Dataset facts (approx neuron counts, confirmed by Amy)
- EyeWire II (mouse retina) ~100,000 · FlyWire (fly brain) ~140,000 · MICrONS (mouse V1) ~120,000 (200,000 cells / 523M synapses) · FlyWire BANC (fly brain + nerve cord) ~160,000 · EyeWire (mouse retina) >10,000 · Pyr / CA3 (mouse hippocampus) in progress.

## Social (X follow icons on dataset cards)
EyeWire II & EyeWire → https://x.com/eye_wire · FlyWire & BANC → https://x.com/FlyWireNews · Pyr → https://x.com/pyrgame

## Inner Cosmos `/explore` (hidden-worlds/src/pages/Explore.tsx)
10-stage guided WebGL zoom (human brain → … → activity → **"Become a hero of neuroscience"** final step using the Rika+Nurro hero art, with a "Get involved" button → connectome.quest/access.html via `target="_top"`). Stages are hand-tuned in the 3D scene, so adding stages is delicate: `isActivityStage = stage === STAGES.length - 2`, `isCtaStage = stage === last`. NavBar was trimmed to just "Meet a Neuron" + "Activity".

## Known open items
- FlyWire sandbox link is in; a Google login is required (noted on the page).
- Everything else from the build (HTTPS, contact form, mascots, galleries, X icons, BANC count) is done and deployed.
