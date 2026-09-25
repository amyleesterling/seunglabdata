# Seung Lab Datasets

Catalog of Seung Lab connectomics datasets and resources for citizen scientists.

**Live:** https://connectome.quest

Static single-page site (HTML + CSS, no build step). Hosted on GitHub Pages with the
custom domain `connectome.quest` (see `CNAME`).

## Admin page (connectome.quest/admin)

A password page for Amy: her to do list plus the live status of the EyeWire II
auto dev robot (the feedback triage loop). The password is Amy's; it is not in
this repo.

- `admin/index.html`: the page. After the password it loads the live triage
  table (Supabase, public read key), robot runs (GitHub Actions) and
  `docs/TRIAGE-LOOP.md` from seung-lab/ng-extend, so those parts never go stale.
- `admin/data.enc.json`: the to do list, AES encrypted with the password.
  The readable copy is `admin/private/content.json`, which is gitignored and
  stays on Amy's PC.
- `admin/tools/seal.mjs`: re-encrypts after editing the list.

**Agent update.** Whenever the auto dev robot pipeline changes, or a to do is
finished or added, run `/agent-update` in Claude Code (skill in
`~/.claude/skills/agent-update`). It updates the doc and the list, re-seals,
and publishes. The repo is public, so the password only keeps out casual
visitors: never put keys or tokens on the page.
