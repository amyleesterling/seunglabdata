# Connectome Quest — Handoff

Hand this to a new chat to continue work on **connectome.quest** (the "Citizen Neuroscience" site). It captures the current state, where everything lives, and the conventions to follow.

## What it is
A public site for the Seung Lab's connectomics datasets and citizen science. Visitors learn about the brain, watch neuron videos, and find out how to start proofreading (mapping) real neurons.

## Repos, hosting, deploy
- **Main site**: `C:\Users\amyle\seunglabdata` → GitHub `amyleesterling/seunglabdata` → live at **https://connectome.quest**. Static HTML/CSS/JS, no build step. **Deploy = commit + push to `main`** (GitHub Pages).
  - Domain: Porkbun, **connectome.quest** (NOT connectomics.quest). Apex A records 185.199.108–111.153 + AAAA 2606:50c0:8000–8003::153; `CNAME` file = connectome.quest.
  - **HTTPS is on and enforced.** It had to be kicked off manually via the Pages API: cert state was `None`, so I re-registered the custom domain (`gh api -X PUT repos/amyleesterling/seunglabdata/pages -f cname=connectome.quest`) which provisioned a Let's Encrypt cert, then set `https_enforced=true`. If HTTPS ever breaks, check `gh api repos/amyleesterling/seunglabdata/pages` (cname + https_certificate.state).
- **Inner Cosmos** (separate project, embedded on the Learn page): `C:\Users\amyle\hidden-worlds` → GitHub `amyleesterling/inner_cosmos` → **https://amyleesterling.github.io/inner_cosmos/**. Vite + React + TS + Tailwind + Three.js. **Deploy = commit + push to `main`** (GitHub Actions `deploy.yml`; run `npm run build` first to verify). `C:\Users\amyle\inner_cosmos` is a STALE clone of the same repo — always edit `hidden-worlds`.

## Pages (all in seunglabdata; nav = Neuro 101 · Videos · Help · Forum · Access · Connectome 101, single row on mobile)
- `index.html` — **Map the Brain homepage**. Text-led opening, uncropped neuron banner, "We need your help" (EyeWire II + FlyWire BANC highlight cards), "More datasets" grid (FlyWire, EyeWire, MICrONS, Pyr), Citizen Science stats, "Resources for Citizen Scientists", footer with a tiny cat mascot. Each dataset card has a stats footer (Location + Approx. neurons/cells) and a right-aligned **Twitter-bird follow icon**.
- `learn.html` — **Neuro 101**. Full-viewport iframe of the Inner Cosmos **/explore** guided zoom, then a "Why we map the brain" section + "Get involved" button. Share/Fullscreen controls are top-left (so they don't collide with the Inner Cosmos nav).
- `videos.html` — **Videos**. Channels first (FlyWire Princeton, EyeWire, Pyr, with real channel-avatar icons), then Neuron Animations playlist, then Mammalian and Fly neuron galleries (thumbnail tiles → individual YouTube videos, each with a one-line description).
- `help.html` — **Help**. Contact form (Formsubmit → support@eyewire.org, ACTIVATED + WORKING), forum link, getting started, "Learn to use the software" tutorial playlists. Trailblaze mascot top-right, Nurro at bottom.
- `access.html` — **Access**. The Neuroglancer **prototype tutorial embed is at the top** (id `learn-to-map`), then the 4-step get-access flow (sandbox → 10 example edits → submit via prefilled email → invitation), then resources, two sandboxes (mouse retina + fly; fly needs a Google login). Rika mascot top, Nurro midway. The submit/email links build the support address at runtime.
- `atlas/` — **Connectome 101**. The interactive Connectome Atlas, including its citations and macro-connectomics subpages. It is a BUILT copy of `amyleesterling/whatisabrain` `apps/connectome` (canonical source, mirrored to `amyleesterling/connectome` hourly) with a **quest-only overlay patched into the bundle**: `/connectome/` paths rewritten to `/atlas/`, the vocabulary section, the human-brain section (05), the "YOUR TURN / Ready to map a brain?" CTA (08, links to `/play/` and `/access.html`), the daf-apis sign-in note, and both overlay sections added to the progress rail so every section eyebrow number matches the rail count. When re-syncing from canonical, re-apply this overlay (the inline `<style>` block in `atlas/index.html` carries its styles; keep `atlas/credits/index.html` and `atlas/macro/index.html` as plain entry copies without that block, updating only the hashed asset names). Amy also wants a **custom graphic** for the Collaborative Layer "One map, many kinds of attention" panel if that content returns (noted in the canonical CODEX_MEMORY).
- `credits.html` — Project, research community, educational experience, data, imagery, and source credits. Every standard-page footer links here.

## Conventions / preferences (IMPORTANT)
- **NO DASHES** in copy. No em-dashes (—) or en-dashes (–). Use commas/periods/colons. (Hyphens in compound words are fine.)
- **Theme**: blue `#42d5ec` for links/eyebrows/flags/structure, yellow `#e6c760` for primary CTA buttons and the "help!" accent. No gradient text (Amy finds it "too AI").
- Background is a subtle deep-indigo top glow; keep it dark and understated.
- Mascots displayed **small**; source art is huge, so resize (PIL/ImageMagick) into `assets/images/` before use. On the repo: `rika-welcome.png`, `nurro-experiment.png`, `trailblaze.png`, `footer-tiny.png` (cat), `favicon-pyr.png`; Inner Cosmos hero at `hidden-worlds/public/hero-rika-nurro.png`.
- **Favicon** = the Pyr logo (`assets/images/favicon-pyr.png`), linked on every page.
- The Princeton crest in the top navigation links to the Princeton Neuroscience Institute at `https://pni.princeton.edu/`.
- Support/contact email is assembled at runtime in JS (not a plain-text literal) to avoid scrapers.

## Dataset facts (approx counts, confirmed by Amy)
EyeWire II (mouse retina) ~100,000 · FlyWire (fly brain) 140,000 · MICrONS (mouse V1) **>200,000 cells** (523M synapses) · FlyWire BANC (fly brain + nerve cord) **~188,000** · EyeWire (mouse retina) >10,000 · Pyr / CA3 (mouse hippocampus) in progress.

## Social (Twitter-bird follow icons on dataset cards, right-aligned)
EyeWire II & EyeWire → https://x.com/eye_wire · FlyWire & BANC → https://x.com/FlyWireNews · Pyr → https://x.com/pyrgame

## Inner Cosmos `/explore` (hidden-worlds/src/pages/Explore.tsx)
10-stage guided WebGL zoom (human brain → … → activity → **"Become a hero of neuroscience"** final step using the Rika+Nurro hero art, with a "Get involved" button → connectome.quest/access.html via `target="_top"`). Stages are hand-tuned in the 3D scene, so adding stages is delicate: `isActivityStage = stage === STAGES.length - 2`, `isCtaStage = stage === last`. The NavBar was trimmed to just "Meet a Neuron" + "Activity" (brand + Explorer removed).

## Status: everything requested is done and deployed
HTTPS enforced · contact form working · mascots placed · video galleries with descriptions · Twitter-bird follow icons · Pyr favicon · dataset counts corrected · interactive tutorial embed on both Datasets (below the EyeWire II slide deck) and the top of Access · both sandboxes on Access (fly needs Google login) · Inner Cosmos hero finale.

## Open / nice-to-have
- The prototype tutorial's "Submit your proofreading test" flow currently routes to email/the Access steps; swap in a real production-access form URL if one becomes available.
- Some approximate counts (Pyr "in progress") can be firmed up later.
