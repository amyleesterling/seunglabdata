// The blog: loads published posts from the EyeWire II database and draws them.
// Posts are written in the game (profile, Blog tab) by the listed authors.
// The key below is the PUBLIC one: it can only read published posts.
//
// renderBlogMarkdown is the same code as the editor's preview in the game
// (ng-extend src/util/blog_markdown.ts). Change both together.
(function () {
'use strict';
var API = 'https://javthknksdcrlhiaaptj.supabase.co/rest/v1/blog_posts';
var KEY = 'sb_publishable_a5r5rfbOuWNoVw0Qb_LtRg_xA4H6Jxb';

const IMG_OK = /^https:\/\/(javthknksdcrlhiaaptj\.supabase\.co\/storage\/v1\/object\/public\/|connectome\.quest\/assets\/)/;
const LINK_OK = /^(https:\/\/|\/(?!\/))/;
const IMG_LINE = /^!\[([^\]]*)\]\(([^)\s]+)\)$/;
const VIDEO_LINE = /^@\[youtube\]\(([A-Za-z0-9_-]{11})\)$/;

const esc = (s) => s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
const unamp = (s) => s.replace(/&amp;/g, '&');

function inline(s) {
  return s
    .replace(/`([^`]+)`/g, '<code>$1</code>')
    .replace(/!\[([^\]]*)\]\(([^)\s]+)\)/g, (m, alt, url) => IMG_OK.test(unamp(url)) ? `<img src="${url}" alt="${alt}" loading="lazy" />` : m)
    .replace(/\[([^\]]+)\]\(([^)\s]+)\)/g, (m, text, url) => LINK_OK.test(unamp(url)) ? `<a href="${url}"${/^https:/.test(url) ? ' target="_blank" rel="noopener noreferrer"' : ''}>${text}</a>` : m)
    .replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>')
    .replace(/(^|[^*])\*([^*\s][^*]*)\*/g, '$1<em>$2</em>');
}

/** Image lines, each optionally followed by a "^ caption" line. */
function figures(para) {
  const figs = [];
  for (let k = 0; k < para.length; k++) {
    const m = IMG_LINE.exec(para[k]);
    if (!m || !IMG_OK.test(unamp(m[2]))) return null;
    let caption = '';
    if (k + 1 < para.length && /^\^\s?/.test(para[k + 1])) caption = para[++k].replace(/^\^\s?/, '');
    figs.push(`<figure class="blog-post__figure"><img src="${m[2]}" alt="${m[1]}" loading="lazy" />${caption ? `<figcaption>${inline(caption)}</figcaption>` : ''}</figure>`);
  }
  if (!figs.length) return null;
  return figs.length === 1 ? figs[0] : `<div class="blog-post__pair">${figs.join('')}</div>`;
}

/** editor: draw a video as a still picture, so it can sit inside the editor. */
function renderBlogMarkdown(text, editor) {
  const lines = esc(String(text || '').replace(/\r\n?/g, '\n')).split('\n');
  const out = [];
  let i = 0;
  const run = (re) => { const got = []; while (i < lines.length && re.test(lines[i])) got.push(lines[i++].replace(re, '')); return got; };
  while (i < lines.length) {
    const line = lines[i];
    if (!line.trim()) { i++; continue; }
    const video = VIDEO_LINE.exec(line.trim());
    if (/^```/.test(line)) {
      i++;
      const code = [];
      while (i < lines.length && !/^```/.test(lines[i])) code.push(lines[i++]);
      i++;
      out.push(`<pre><code>${code.join('\n')}</code></pre>`);
    } else if (video) {
      i++;
      out.push(editor
        ? `<div class="blog-post__video" data-yt="${video[1]}" contenteditable="false"><img src="https://i.ytimg.com/vi/${video[1]}/hqdefault.jpg" alt="YouTube video" /></div>`
        : `<div class="blog-post__video"><iframe src="https://www.youtube-nocookie.com/embed/${video[1]}" title="YouTube video" loading="lazy" allow="accelerometer; encrypted-media; gyroscope; picture-in-picture; web-share" allowfullscreen referrerpolicy="strict-origin-when-cross-origin"></iframe></div>`);
    } else if (/^-{3,}\s*$/.test(line)) { out.push('<hr />'); i++; }
    else if (/^###\s+/.test(line)) { out.push(`<h3>${inline(line.replace(/^###\s+/, ''))}</h3>`); i++; }
    else if (/^##?\s+/.test(line)) { out.push(`<h2>${inline(line.replace(/^##?\s+/, ''))}</h2>`); i++; }
    else if (/^!&gt;\s?/.test(line)) out.push(`<aside class="blog-post__callout">${run(/^!&gt;\s?/).map(x => `<p>${inline(x)}</p>`).join('')}</aside>`);
    else if (/^[-*]\s+/.test(line)) out.push(`<ul>${run(/^[-*]\s+/).map(x => `<li>${inline(x)}</li>`).join('')}</ul>`);
    else if (/^\d+\.\s+/.test(line)) out.push(`<ol>${run(/^\d+\.\s+/).map(x => `<li>${inline(x)}</li>`).join('')}</ol>`);
    else if (/^&gt;\s?/.test(line)) out.push(`<blockquote><p>${inline(run(/^&gt;\s?/).join(' '))}</p></blockquote>`);
    else {
      const para = [];
      while (i < lines.length && lines[i].trim() && !/^(```|##?#?\s|[-*]\s|\d+\.\s|&gt;|!&gt;|-{3,}\s*$|@\[youtube\])/.test(lines[i])) para.push(lines[i++].trim());
      // A line that looks like a block but is not a valid one (a video with a
      // bad id, say) is plain text. Always move on, or this loop never ends.
      if (!para.length) para.push(lines[i++].trim());
      const figs = figures(para);
      if (figs) { out.push(figs); continue; }
      const joined = para.join(' ');
      const html = inline(joined);
      if (/^\[[^\]]+\]\([^)\s]+\)$/.test(joined) && html.startsWith('<a ')) out.push(`<p class="blog-post__cta">${html.replace('<a ', '<a class="blog-post__button" ')}</p>`);
      else out.push(`<p>${html}</p>`);
    }
  }
  return out.join('\n');
}

/** A web address for a title: "Hello, World!" becomes "hello-world". */
function blogSlug(title) {
  return String(title || '').toLowerCase().normalize('NFKD').replace(/[\u0300-\u036f]/g, '').replace(/[^a-z0-9]+/g, '-').replace(/^-+|-+$/g, '').slice(0, 80).replace(/-+$/, '');
}

function get(query) {
  return fetch(API + '?' + query, { headers: { apikey: KEY } }).then(function (r) {
    if (!r.ok) throw new Error('blog ' + r.status);
    return r.json();
  });
}
function day(iso) {
  var d = new Date(iso);
  return isNaN(d) ? '' : d.toLocaleDateString('en-US', { year: 'numeric', month: 'long', day: 'numeric' });
}
function el(tag, cls, text) {
  var e = document.createElement(tag);
  if (cls) e.className = cls;
  if (text != null) e.textContent = text;
  return e;
}
function postUrl(slug) { return '/blog/post.html?p=' + encodeURIComponent(slug); }

// ── The list (blog/index.html), with search ────────────────────────────
var list = document.getElementById('blogList');
if (list) {
  var search = document.getElementById('blogSearch');
  var count = document.getElementById('blogCount');
  var all = [];
  var draw = function () {
    var words = (search ? search.value : '').toLowerCase().split(/\s+/).filter(Boolean);
    var shown = all.filter(function (p) {
      return words.every(function (w) { return p._text.indexOf(w) !== -1; });
    });
    list.textContent = '';
    shown.forEach(function (p) {
      var item = el('article', 'blog-item');
      if (p.cover_url && IMG_OK.test(p.cover_url)) {
        item.className += ' blog-item--cover';
        var pic = el('a', 'blog-item__cover');
        pic.href = postUrl(p.slug);
        pic.setAttribute('tabindex', '-1');
        pic.setAttribute('aria-hidden', 'true');
        var img = el('img');
        img.src = p.cover_url;
        img.alt = '';
        img.loading = 'lazy';
        pic.appendChild(img);
        item.appendChild(pic);
      }
      var text = el('div', 'blog-item__text');
      var date = el('p', 'blog-item__date');
      var time = el('time', '', day(p.published_at));
      time.setAttribute('datetime', String(p.published_at || '').slice(0, 10));
      date.appendChild(time);
      if (p.author_name) date.appendChild(document.createTextNode(' · ' + p.author_name));
      var h = el('h2');
      var a = el('a', '', p.title);
      a.href = postUrl(p.slug);
      h.appendChild(a);
      text.appendChild(date);
      text.appendChild(h);
      if (p.summary) text.appendChild(el('p', '', p.summary));
      var more = el('a', 'blog-item__more', 'Read the post');
      more.href = postUrl(p.slug);
      text.appendChild(more);
      item.appendChild(text);
      list.appendChild(item);
    });
    if (!shown.length) list.appendChild(el('p', 'blog-empty', 'No posts match that search.'));
    if (count) count.textContent = words.length ? shown.length + (shown.length === 1 ? ' post' : ' posts') + ' found' : '';
  };
  get('select=slug,title,summary,body,cover_url,author_name,published_at&status=eq.published&order=published_at.desc&limit=100')
    .then(function (posts) {
      if (!posts.length) return;               // keep whatever the page shipped with
      all = posts.map(function (p) {
        p._text = [p.title, p.summary, p.author_name, p.body].join(' ').toLowerCase();
        return p;
      });
      var box = document.getElementById('blogSearchBox');
      if (box) box.hidden = false;
      if (search) {
        search.addEventListener('input', draw);
        var q = new URLSearchParams(location.search).get('q');
        if (q) search.value = q;
      }
      draw();
    })
    .catch(function () { /* the page keeps its built in list */ });
}

// ── One post (blog/post.html?p=slug) ───────────────────────────────────
var post = document.getElementById('blogPost');
if (post) {
  var slug = new URLSearchParams(location.search).get('p') || '';
  var missing = function (text) {
    document.getElementById('blogTitle').textContent = 'Post not found';
    document.getElementById('blogBody').textContent = '';
    document.getElementById('blogBody').appendChild(el('p', '', text));
  };
  if (!/^[a-z0-9]+(-[a-z0-9]+)*$/.test(slug)) missing('That link does not point to a post.');
  else get('select=slug,title,summary,body,cover_url,author_name,published_at&status=eq.published&slug=eq.' + slug + '&limit=1')
    .then(function (rows) {
      var p = rows[0];
      if (!p) { missing('This post is not published, or the link is wrong.'); return; }
      document.title = p.title + ' | Map the Brain';
      var desc = document.querySelector('meta[name="description"]');
      if (desc && p.summary) desc.setAttribute('content', p.summary);
      document.getElementById('blogTitle').textContent = p.title;
      var meta = document.getElementById('blogMeta');
      meta.textContent = '';
      var time = el('time', '', day(p.published_at));
      time.setAttribute('datetime', String(p.published_at || '').slice(0, 10));
      meta.appendChild(time);
      if (p.author_name) meta.appendChild(document.createTextNode(' · ' + p.author_name));
      var body = document.getElementById('blogBody');
      body.innerHTML = renderBlogMarkdown(p.body);   // escaped, then a short list of tags
      if (p.cover_url && IMG_OK.test(p.cover_url)) {
        var fig = el('figure', 'blog-post__figure blog-post__figure--cover');
        var img = el('img');
        img.src = p.cover_url;
        img.alt = '';
        fig.appendChild(img);
        body.insertBefore(fig, body.firstChild);
      }
    })
    .catch(function () { missing('The blog could not be loaded just now. Please try again in a moment.'); });
}

// ── The first post's old address forwards to its new one once it exists ─
var legacy = document.documentElement.getAttribute('data-blog-legacy');
if (legacy) {
  get('select=slug&status=eq.published&slug=eq.' + legacy + '&limit=1')
    .then(function (rows) { if (rows[0]) location.replace(postUrl(legacy)); })
    .catch(function () {});
}
})();
