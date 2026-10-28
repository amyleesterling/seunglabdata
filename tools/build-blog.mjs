#!/usr/bin/env node
// Builds the blog's static pages from the published posts (Ames 2026-10-28:
// "we need real previews with post title and make sure this is SEO / indexed
// by AIs").
//
// The blog is written in Pyr (profile, Blog tab) and stored in Supabase. Its
// pages used to be filled in by JavaScript, so anything that reads a page
// without running scripts (Slack and other link previews, search engines, AI
// crawlers) saw only "Blog | Map the Brain". This writes, for every published
// post, a real page at /blog/<slug>/ with the post's own title, summary,
// picture and text in the HTML, and the share tags (Open Graph, Twitter,
// JSON-LD) that previews read. It also writes the blog list into
// /blog/index.html, and sitemap.xml, robots.txt, /blog/feed.xml and llms.txt.
//
// Run by .github/workflows/blog-build.yml every 15 minutes; run by hand with
//   node tools/build-blog.mjs
// It only reads published posts, with the public key the blog page already
// uses. Nothing is written when nothing changed.
//
// The text is drawn by the same renderBlogMarkdown the blog page and Pyr's
// editor use (assets/blog.js), so a static page and the live one match.
import fs from 'node:fs';
import path from 'node:path';
import vm from 'node:vm';
import { fileURLToPath } from 'node:url';

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const SITE = 'https://connectome.quest';
const SITE_NAME = 'Map the Brain';
const API = 'https://javthknksdcrlhiaaptj.supabase.co/rest/v1/blog_posts';
const KEY = 'sb_publishable_a5r5rfbOuWNoVw0Qb_LtRg_xA4H6Jxb';   // public, read only
const DEFAULT_IMAGE = `${SITE}/assets/images/eyewire-ii-og.jpg`;
const SLUG_OK = /^[a-z0-9]+(-[a-z0-9]+)*$/;

// ── The renderer, from assets/blog.js ─────────────────────────────────────
function loadRenderer() {
  const code = fs.readFileSync(path.join(ROOT, 'assets/blog.js'), 'utf8');
  const sandbox = {
    document: { getElementById: () => null, querySelector: () => null, documentElement: { getAttribute: () => null } },
    location: { search: '' }, URLSearchParams, fetch: () => Promise.reject(new Error('no fetch here')), console,
  };
  sandbox.globalThis = sandbox;
  vm.runInNewContext(code, sandbox, { filename: 'blog.js' });
  if (!sandbox.BlogRender) throw new Error('assets/blog.js did not expose BlogRender');
  return sandbox.BlogRender;
}

// ── Small helpers ─────────────────────────────────────────────────────────
const esc = (s) => String(s ?? '').replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
const xml = esc;
const postPath = (slug) => `/blog/${slug}/`;
const day = (iso) => {
  const d = new Date(iso);
  return isNaN(d) ? '' : d.toLocaleDateString('en-US', { year: 'numeric', month: 'long', day: 'numeric', timeZone: 'UTC' });
};
/** Plain words from the post's text, for a description when there is no summary. */
const plainText = (md) => String(md || '')
  .replace(/```[\s\S]*?```/g, ' ')
  .replace(/!\[[^\]]*\]\([^)]*\)/g, ' ')
  .replace(/@\[youtube\]\([^)]*\)/g, ' ')
  .replace(/\[([^\]]+)\]\([^)]*\)/g, '$1')
  .replace(/^[#>!^\-*\d.\s]+/gm, '')
  .replace(/[*_`]/g, '')
  .replace(/\s+/g, ' ').trim();
const clip = (s, n) => (s.length > n ? s.slice(0, n - 1).replace(/\s+\S*$/, '') + '…' : s);
const describe = (p) => clip(String(p.summary || '').trim() || plainText(p.body), 300);
const imageOf = (p) => (p.cover_url && /^https:\/\//.test(p.cover_url) ? p.cover_url : DEFAULT_IMAGE);

/** Write a file only when its text changed. Returns true if it was written. */
let changed = 0;
function put(rel, text) {
  const file = path.join(ROOT, rel);
  if (fs.existsSync(file) && fs.readFileSync(file, 'utf8') === text) return false;
  fs.mkdirSync(path.dirname(file), { recursive: true });
  fs.writeFileSync(file, text);
  changed++;
  console.log('wrote', rel);
  return true;
}

// ── The shared page frame, taken from blog/post.html so the two stay alike ─
function frame() {
  const html = fs.readFileSync(path.join(ROOT, 'blog/post.html'), 'utf8');
  const nav = html.slice(html.indexOf('<nav class="topnav">'), html.indexOf('</nav>') + '</nav>'.length);
  const sub = html.slice(html.indexOf('<section class="subscribe"'), html.indexOf('</section>', html.indexOf('<section class="subscribe"')) + '</section>'.length);
  const foot = html.slice(html.indexOf('<footer class="footer">'), html.indexOf('</footer>') + '</footer>'.length);
  if (!nav || !sub || !foot) throw new Error('blog/post.html no longer has the nav, subscribe and footer this copies');
  return { nav, sub, foot };
}

function postPage(p, R, f) {
  const url = SITE + postPath(p.slug);
  const title = String(p.title || '').trim();
  const desc = describe(p);
  const img = imageOf(p);
  const published = p.published_at || p.created_at;
  const modified = p.updated_at || published;
  const author = String(p.author_name || 'The Pyr team').trim();
  const ld = {
    '@context': 'https://schema.org',
    '@type': 'BlogPosting',
    headline: title,
    description: desc,
    image: [img],
    datePublished: published,
    dateModified: modified,
    author: [{ '@type': 'Person', name: author }],
    publisher: { '@type': 'Organization', name: 'Seung Lab, Princeton University', url: SITE + '/', logo: { '@type': 'ImageObject', url: SITE + '/assets/images/favicon-pyr.png' } },
    mainEntityOfPage: { '@type': 'WebPage', '@id': url },
    url,
    isPartOf: { '@type': 'Blog', name: SITE_NAME + ' blog', url: SITE + '/blog/' },
  };
  const cover = p.cover_url && /^https:\/\//.test(p.cover_url)
    ? `\n      <figure class="blog-post__figure blog-post__figure--cover"><img src="${esc(p.cover_url)}" alt="" /></figure>` : '';
  return `<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>${esc(title)} | ${SITE_NAME}</title>
  <meta name="description" content="${esc(desc)}" />
  <link rel="canonical" href="${esc(url)}" />
  <meta name="author" content="${esc(author)}" />
  <meta name="robots" content="index, follow, max-image-preview:large" />
  <meta property="og:type" content="article" />
  <meta property="og:site_name" content="${SITE_NAME}" />
  <meta property="og:title" content="${esc(title)}" />
  <meta property="og:description" content="${esc(desc)}" />
  <meta property="og:url" content="${esc(url)}" />
  <meta property="og:image" content="${esc(img)}" />
  <meta property="og:image:alt" content="${esc(title)}" />
  <meta property="article:published_time" content="${esc(published)}" />
  <meta property="article:modified_time" content="${esc(modified)}" />
  <meta property="article:author" content="${esc(author)}" />
  <meta name="twitter:card" content="summary_large_image" />
  <meta name="twitter:title" content="${esc(title)}" />
  <meta name="twitter:description" content="${esc(desc)}" />
  <meta name="twitter:image" content="${esc(img)}" />
  <link rel="alternate" type="application/rss+xml" title="${SITE_NAME} blog" href="${SITE}/blog/feed.xml" />
  <script type="application/ld+json">${JSON.stringify(ld).replace(/</g, '\\u003c')}</script>
  <link rel="icon" type="image/png" href="/assets/images/favicon-pyr.png" />
  <link rel="apple-touch-icon" href="/assets/images/favicon-pyr.png" />
  <link rel="preconnect" href="https://fonts.googleapis.com" />
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin />
  <link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Orbitron:wght@500;600;700&display=swap" />
  <link rel="stylesheet" href="/styles.css?v=blogedit1" />
</head>
<body class="blog-light">
  <!-- Built by tools/build-blog.mjs from the published post. Edit the post in Pyr, not here. -->
  ${f.nav}

  <main class="wrap blog-page">
    <article class="blog-post">
      <header class="pagehead">
        <p class="hero__eyebrow"><a href="/blog/">Blog</a></p>
        <h1>${esc(title)}</h1>
        <p class="blog-post__meta"><time datetime="${esc(String(published || '').slice(0, 10))}">${esc(day(published))}</time>${p.author_name ? ' · ' + esc(p.author_name) : ''}</p>
        <p class="blog-edit"><button type="button" class="blog-edit__btn" data-blog-edit="${esc(p.slug)}" data-blog-author-only hidden>Edit</button></p>
      </header>
      <div>${cover}
${R.renderBlogMarkdown(p.body)}
      </div>
      <p class="blog-post__back"><a href="/blog/">All posts</a><button type="button" class="blog-edit__quiet" data-blog-edit="${esc(p.slug)}" hidden>Edit this post</button></p>
    </article>

    ${f.sub}
  </main>

  ${f.foot}
  <script src="/assets/subscribe.js?v=2"></script>
  <script src="/assets/blog-edit.js?v=1"></script>
</body>
</html>
`;
}

/** The posts listed in blog/index.html, between its two markers. */
function listItems(posts) {
  return posts.map((p) => {
    const href = postPath(p.slug);
    const coverOk = p.cover_url && /^https:\/\//.test(p.cover_url);
    return `      <article class="blog-item${coverOk ? ' blog-item--cover' : ''}">${coverOk ? `
        <a class="blog-item__cover" href="${href}" tabindex="-1" aria-hidden="true"><img src="${esc(p.cover_url)}" alt="" loading="lazy" /></a>` : ''}
        <div class="blog-item__text">
          <p class="blog-item__date"><time datetime="${esc(String(p.published_at || '').slice(0, 10))}">${esc(day(p.published_at))}</time>${p.author_name ? ' · ' + esc(p.author_name) : ''}</p>
          <h2><a href="${href}">${esc(p.title)}</a></h2>${p.summary ? `
          <p>${esc(p.summary)}</p>` : ''}
          <a class="blog-item__more" href="${href}">Read the post</a>
        </div>
      </article>`;
  }).join('\n');
}

function rssFeed(posts, R) {
  const items = posts.slice(0, 50).map((p) => `    <item>
      <title>${xml(p.title)}</title>
      <link>${SITE}${postPath(p.slug)}</link>
      <guid isPermaLink="true">${SITE}${postPath(p.slug)}</guid>
      <pubDate>${new Date(p.published_at).toUTCString()}</pubDate>${p.author_name ? `
      <dc:creator>${xml(p.author_name)}</dc:creator>` : ''}
      <description>${xml(describe(p))}</description>
      <content:encoded><![CDATA[${R.renderBlogMarkdown(p.body).replace(/]]>/g, ']]]]><![CDATA[>')}]]></content:encoded>
    </item>`).join('\n');
  const newest = posts[0] ? new Date(posts[0].published_at).toUTCString() : new Date(0).toUTCString();
  return `<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" xmlns:atom="http://www.w3.org/2005/Atom" xmlns:content="http://purl.org/rss/1.0/modules/content/" xmlns:dc="http://purl.org/dc/elements/1.1/">
  <channel>
    <title>${SITE_NAME} blog</title>
    <link>${SITE}/blog/</link>
    <atom:link href="${SITE}/blog/feed.xml" rel="self" type="application/rss+xml" />
    <description>What is new in Pyr and the other brain mapping projects of the Seung Lab, Princeton University.</description>
    <language>en</language>
    <lastBuildDate>${newest}</lastBuildDate>
${items}
  </channel>
</rss>
`;
}

/** The site's own pages, for the sitemap: every page except the ones kept out of search. */
function sitePages() {
  const skip = new Set(['404.html', 'admin', 'tools', 'node_modules', '.git', '.github', 'assets', 'blog']);
  const out = [];
  for (const name of fs.readdirSync(ROOT)) {
    if (skip.has(name)) continue;
    const full = path.join(ROOT, name);
    if (name.endsWith('.html')) {
      const text = fs.readFileSync(full, 'utf8');
      if (/<meta\s+name="robots"\s+content="[^"]*noindex/i.test(text)) continue;
      out.push(name === 'index.html' ? '/' : '/' + name);
    } else if (fs.statSync(full).isDirectory() && fs.existsSync(path.join(full, 'index.html'))) {
      const text = fs.readFileSync(path.join(full, 'index.html'), 'utf8');
      if (/<meta\s+name="robots"\s+content="[^"]*noindex/i.test(text)) continue;
      out.push('/' + name + '/');
    }
  }
  return out.sort();
}

function sitemap(posts) {
  const pages = sitePages().map((p) => `  <url><loc>${SITE}${p}</loc></url>`);
  const blog = [`  <url><loc>${SITE}/blog/</loc>${posts[0] ? `<lastmod>${String(posts[0].updated_at || posts[0].published_at).slice(0, 10)}</lastmod>` : ''}</url>`];
  const each = posts.map((p) => `  <url><loc>${SITE}${postPath(p.slug)}</loc><lastmod>${String(p.updated_at || p.published_at).slice(0, 10)}</lastmod></url>`);
  return `<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
${[...pages, ...blog, ...each].join('\n')}
</urlset>
`;
}

// Search engines and AI assistants are all welcome: the point of the site is
// to be found. Named so it is plain that the AI crawlers are allowed too.
const ROBOTS = `# Everyone may read this site, search engines and AI crawlers included.
User-agent: *
Allow: /
Disallow: /admin/

User-agent: GPTBot
Allow: /
User-agent: OAI-SearchBot
Allow: /
User-agent: ChatGPT-User
Allow: /
User-agent: ClaudeBot
Allow: /
User-agent: Claude-SearchBot
Allow: /
User-agent: Claude-User
Allow: /
User-agent: PerplexityBot
Allow: /
User-agent: Google-Extended
Allow: /
User-agent: Applebot-Extended
Allow: /
User-agent: CCBot
Allow: /

Sitemap: ${SITE}/sitemap.xml
`;

function llmsTxt(posts) {
  const lines = posts.map((p) => `- [${p.title}](${SITE}${postPath(p.slug)}): ${describe(p).replace(/\s+/g, ' ')}`);
  return `# ${SITE_NAME}

> The citizen science home of connectomics, from the Seung Lab at Princeton University. Volunteers map neurons in brain images in Pyr, the lab's brain mapping game (formerly EyeWire II), and help build connectomes: complete wiring diagrams of brains.

## Start here
- [Home](${SITE}/): the projects that need help, and how to join
- [Connectome 101](${SITE}/atlas/): what a connectome is
- [Neuro 101](${SITE}/learn.html): neuroscience for beginners
- [Help](${SITE}/help.html): how to play and get help
- [Access](${SITE}/access.html): ask for access to edit

## Blog
- [All posts](${SITE}/blog/) ([RSS](${SITE}/blog/feed.xml))
${lines.join('\n')}
`;
}

// ── Build ─────────────────────────────────────────────────────────────────
const res = await fetch(`${API}?select=slug,title,summary,body,cover_url,author_name,published_at,updated_at,created_at&status=eq.published&order=published_at.desc&limit=500`, { headers: { apikey: KEY } });
if (!res.ok) throw new Error(`could not read the posts (${res.status})`);
const posts = (await res.json()).filter((p) => SLUG_OK.test(String(p.slug || '')) && String(p.title || '').trim() && p.published_at);
if (!posts.length) throw new Error('no published posts came back: refusing to write an empty blog');
const R = loadRenderer();
const f = frame();

for (const p of posts) put(`blog/${p.slug}/index.html`, postPage(p, R, f));

// A post that was unpublished or renamed: its page goes, and the address
// falls through to the 404 page, which sends people to the blog.
const live = new Set(posts.map((p) => p.slug));
for (const name of fs.readdirSync(path.join(ROOT, 'blog'))) {
  const dir = path.join(ROOT, 'blog', name);
  if (!fs.statSync(dir).isDirectory() || live.has(name)) continue;
  const page = path.join(dir, 'index.html');
  if (fs.existsSync(page) && fs.readFileSync(page, 'utf8').includes('Built by tools/build-blog.mjs')) {
    fs.rmSync(dir, { recursive: true });
    changed++;
    console.log('removed', `blog/${name}/`);
  }
}

const indexFile = path.join(ROOT, 'blog/index.html');
const index = fs.readFileSync(indexFile, 'utf8');
const START = '<!-- POSTS:START (written by tools/build-blog.mjs) -->', END = '<!-- POSTS:END -->';
const a = index.indexOf(START), b = index.indexOf(END);
if (a < 0 || b < a) throw new Error('blog/index.html has lost its POSTS markers');
put('blog/index.html', index.slice(0, a + START.length) + '\n' + listItems(posts) + '\n      ' + index.slice(b));

put('blog/feed.xml', rssFeed(posts, R));
put('sitemap.xml', sitemap(posts));
put('robots.txt', ROBOTS);
put('llms.txt', llmsTxt(posts));
console.log(changed ? `${changed} file(s) changed, ${posts.length} posts` : `nothing changed, ${posts.length} posts`);
