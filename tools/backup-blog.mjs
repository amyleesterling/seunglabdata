// A copy of the blog kept in this repository (Ames 2026-11-05: "make sure to
// back up the blog somewhere"). Posts are written in Pyr and live in its
// Supabase database; pictures uploaded in the editor live in its Supabase
// storage. Neither had a copy anywhere else. This writes:
//   backup/blog/posts.json            every published post, whole, as stored
//   backup/blog/posts/<slug>.md       each post's text, readable on its own
//   backup/blog/images/...            every picture a post uses from Supabase storage
// Run by .github/workflows/blog-build.yml every 15 minutes, so git keeps
// every version. Nothing is ever deleted here: an unpublished or renamed
// post keeps its last copy. Drafts are not public, so they are not included.
//   node tools/backup-blog.mjs
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const OUT = path.join(ROOT, 'backup/blog');
const API = 'https://javthknksdcrlhiaaptj.supabase.co/rest/v1/blog_posts';
const KEY = 'sb_publishable_a5r5rfbOuWNoVw0Qb_LtRg_xA4H6Jxb';   // public, read only
const STORAGE = 'https://javthknksdcrlhiaaptj.supabase.co/storage/v1/object/public/';
const SLUG_OK = /^[a-z0-9][a-z0-9-]{0,80}$/;

const res = await fetch(`${API}?select=id,slug,title,summary,body,cover_url,author_name,status,published_at,updated_at,created_at&status=eq.published&order=published_at.desc&limit=500`, { headers: { apikey: KEY } });
if (!res.ok) throw new Error(`could not read the posts (${res.status})`);
const posts = (await res.json()).filter((p) => SLUG_OK.test(String(p.slug || '')));
if (!posts.length) throw new Error('no published posts came back: refusing to write an empty backup');

let changed = 0;
function put(rel, data) {
  const file = path.join(OUT, rel);
  if (fs.existsSync(file) && Buffer.compare(fs.readFileSync(file), Buffer.from(data)) === 0) return;
  fs.mkdirSync(path.dirname(file), { recursive: true });
  fs.writeFileSync(file, data);
  changed++;
  console.log('backed up', rel);
}

// posts.json keeps posts that are no longer published, under their last copy.
const jsonFile = path.join(OUT, 'posts.json');
const kept = new Map();
if (fs.existsSync(jsonFile)) for (const p of JSON.parse(fs.readFileSync(jsonFile, 'utf8'))) kept.set(p.slug, p);
for (const p of posts) kept.set(p.slug, p);
const all = [...kept.values()].sort((a, b) => String(b.published_at).localeCompare(String(a.published_at)));
put('posts.json', JSON.stringify(all, null, 2) + '\n');

for (const p of posts) {
  const head = ['---', `title: ${JSON.stringify(p.title || '')}`, `summary: ${JSON.stringify(p.summary || '')}`,
    `author: ${JSON.stringify(p.author_name || '')}`, `published: ${p.published_at || ''}`, `updated: ${p.updated_at || ''}`,
    `cover: ${p.cover_url || ''}`, '---', ''].join('\n');
  put(`posts/${p.slug}.md`, head + (p.body || '') + '\n');
}

// Pictures from Supabase storage, saved under their storage path.
const urls = new Set();
for (const p of posts) {
  const text = `${p.body || ''}\n${p.cover_url || ''}`;
  for (const m of text.matchAll(/https:\/\/javthknksdcrlhiaaptj\.supabase\.co\/storage\/v1\/object\/public\/[^)\s"'<>]+/g)) urls.add(m[0]);
}
let failed = 0;
for (const url of urls) {
  const rel = decodeURIComponent(url.slice(STORAGE.length).split(/[?#]/)[0]);
  if (rel.split('/').some((s) => s === '..' || s === '')) continue;
  const file = path.join(OUT, 'images', rel);
  if (fs.existsSync(file)) continue;                 // uploads never change under the same name
  const r = await fetch(url);
  if (!r.ok) { failed++; console.log('could not fetch', url, r.status); continue; }
  put(path.join('images', rel), Buffer.from(await r.arrayBuffer()));
}
console.log(`${posts.length} posts, ${urls.size} stored pictures, ${changed} files written${failed ? `, ${failed} pictures failed` : ''}`);
