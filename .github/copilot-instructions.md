# Copilot instructions — Seung Lab Datasets 🔧

Purpose
- Give a focused, actionable orientation so an AI coding agent can quickly make safe, discoverable edits to this static catalog site.

Big picture (why + structure)
- This is a lightweight static site / catalog (single-page HTML + CSS). Key files: `index.html`, `styles.css`, and images under `assets/images/`.
- No build step, no JS frameworks, and no tests or CI present. Changes are made by editing HTML/CSS and committing to the repo (likely published via GitHub Pages).

Where to make common changes
- Content/cards: edit `index.html`. Each dataset is an `<article class="card">` with the following structure:

  ```html
  <article class="card">
    <div class="card__media"> <img src="assets/images/foo.png" alt="..."/></div>
    <div class="card__top"><h2>Title</h2><p class="tag">small tag</p></div>
    <p class="card__body">Short blurb.</p>
    <div class="card__actions"> <a class="btn" href="...">Explore</a> </div>
  </article>
  ```

- Image variants: use `.card__media` for cropped hero-style images (16:9) and `.card__media--contain` for non-cropped images (sets a fixed visible height).
- Layout/responsiveness: `.grid` controls the card layout; cards are equal-height via `grid-auto-rows` and `.card__actions { margin-top: auto }` so always place actions last to keep alignment.

Styling & patterns to follow
- CSS uses a small design system (CSS variables at `:root`), BEM-like class names (`block__element` and modifiers like `--contain`). Follow naming for consistency.
- Keep hero banner as a full-bleed image inside `.hero__media` (object-fit: cover); do not change the DOM structure unless adjusting global layout.

Accessibility & link conventions
- Preserve `alt` attributes and the hero `role="img"` with `aria-label` (these are present in `index.html`). Aim for descriptive alt text (short sentence-style descriptions used here).
- External links use `target="_blank" rel="noreferrer"` — keep this pattern when opening new tabs.

Images & filenames
- Images live in `assets/images/`. Current repo contains files with spaces in names — prefer hyphenated, lowercase filenames for new assets and update references in `index.html`.

Local preview & debugging
- No build system: preview locally by opening `index.html` in a browser or running a simple server:
  - Python: `python -m http.server 8000` (serve from repo root)
  - Node: `npx http-server -p 8000`
- Use the browser DevTools to check responsiveness (breakpoints around 980px, 720px, 620px are used in `styles.css`).

Deployment & workflow notes
- Likely hosted on GitHub Pages (README contains a GitHub Pages URL). Content updates: edit, commit, push. Confirm repo branch/site settings before making CI or automation changes.
- There is no test or CI configuration to update. Avoid introducing heavy tooling without maintainer agreement.

When to open a PR
- Content edits (copy changes, new cards, image swaps)
- Visual or structural changes (CSS updates, layout adjustments)
- Anything that adds build tooling, CI, or publishing changes — escalate for review.

What not to do (observed constraints)
- Do not introduce frameworks (React/Vite/etc.) without an explicit migration plan.
- Avoid renaming many image files in bulk unless also updating `index.html` references and documenting the rename.

If something is ambiguous
- Ask for clarification from the maintainer (link to repository owner is not in repo). If unsure about publishing targets or adding automation, open an issue instead of making large changes.

---

Please review this guidance and tell me if any repository-specific workflows or hosting details should be added or clarified. ✅
