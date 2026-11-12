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
const IMG_LINE = /^!\[([^\]]*)\]\(([^)\s]+)\)(?:\{(small|medium|large)\})?$/;
const VIDEO_LINE = /^@\[youtube\]\(([A-Za-z0-9_-]{11})\)$/;
const PHONE_LINE = /^@\[phone\]\(([^)\s]+)\)$/;
const LINK_LINE = /^@\[link\]\(([^)\s]+)\)$/;
const GALLERY_LINE = '@[gallery]';

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

/** Image lines, each optionally followed by a "^ caption" line, a "^^ longer
 *  description" line (shown when the picture is enlarged), an "@[phone](url)"
 *  line: a tall version of the same picture that phones get instead (Ames
 *  2026-11-04: wide diagrams were too small to read on a phone), and an
 *  "@[link](url)" line: where clicking the picture goes (Ames 2026-11-05).
 *  gallery: the pictures of an @[gallery], shown as a grid.
 *  editor: a picture's link is kept on the figure, not as a link. */
function figures(para, gallery, editor) {
  const figs = [];
  for (let k = 0; k < para.length; k++) {
    const m = IMG_LINE.exec(para[k]);
    if (!m || !IMG_OK.test(unamp(m[2]))) return null;
    let caption = '', phone = '', link = '', more = '';
    for (;;) {
      const next = para[k + 1];
      if (next === undefined) break;
      const p = PHONE_LINE.exec(next);
      const l = LINK_LINE.exec(next);
      if (p && IMG_OK.test(unamp(p[1]))) { phone = p[1]; k++; }
      else if (l && LINK_OK.test(unamp(l[1])) && !link) { link = l[1]; k++; }
      else if (/^\^\^/.test(next)) { if (!more) more = next.replace(/^\^\^\s?/, ''); k++; }
      else if (/^\^\s?/.test(next) && !caption) { caption = next.replace(/^\^\s?/, ''); k++; }
      else break;
    }
    const img = `<img src="${m[2]}" alt="${m[1]}" loading="lazy" />`;
    let pic = phone ? `<picture><source media="(max-width: 700px)" srcset="${phone}" />${img}</picture>` : img;
    if (link && !editor) pic = `<a class="blog-post__piclink" href="${link}"${/^https:/.test(link) ? ' target="_blank" rel="noopener noreferrer"' : ''}>${pic}</a>`;
    // A picture's size (Celia, triage #395: "loads huge and I can't adjust
    // its size"). Sizes apply to a picture on its own, not to a pair or a gallery.
    const sized = m[3] && !gallery ? m[3] : '';
    const size = sized ? ` blog-post__figure--${sized}` : '';
    figs.push(`<figure class="blog-post__figure${size}"${sized ? ` data-size="${sized}"` : ''}${link && editor ? ` data-link="${link}"` : ''}>${pic}${caption ? `<figcaption>${inline(caption)}</figcaption>` : ''}${more ? `<div class="blog-post__more">${inline(more)}</div>` : ''}</figure>`);
  }
  if (!figs.length) return null;
  if (gallery) return `<div class="blog-post__gallery">${figs.join('')}</div>`;
  return figs.length === 1 ? figs[0] : `<div class="blog-post__pair">${figs.map(f => f.replace(/ blog-post__figure--\w+"/, '"').replace(/ data-size="\w+"/, '')).join('')}</div>`;
}

/** editor: draw a video as a still picture, so it can sit inside the editor. */
function renderBlogMarkdown(text, editor) {
  const lines = esc(String(text || '').replace(/\r\n?/g, '\n')).split('\n');
  const out = [];
  // Each heading gets an address of its own, from its words, so a link can
  // point at it: /blog/<post>/#how-to-proofread-a-bc (Ames 2026-11-08).
  // On the page a small # beside it is that link. Not in the editor, where
  // the # would be saved as part of the heading.
  const ids = new Set();
  const heading = (tag, html) => {
    const words = html.replace(/<[^>]*>/g, '').replace(/&quot;/g, '"').replace(/&#39;/g, "'").replace(/&lt;/g, '<').replace(/&gt;/g, '>').replace(/&amp;/g, '&');
    let id = blogSlug(words) || 'section';
    for (let n = 2; ids.has(id); n++) id = `${blogSlug(words) || 'section'}-${n}`;
    ids.add(id);
    return editor ? `<${tag}>${html}</${tag}>`
      : `<${tag} id="${id}">${html}<a class="blog-anchor" href="#${id}" aria-label="Link to this section" title="Link to this section">#</a></${tag}>`;
  };
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
    else if (/^###\s+/.test(line)) { out.push(heading('h3', inline(line.replace(/^###\s+/, '')))); i++; }
    else if (/^##?\s+/.test(line)) { out.push(heading('h2', inline(line.replace(/^##?\s+/, '')))); i++; }
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
      const figs = para[0] === GALLERY_LINE ? figures(para.slice(1), true, editor) : figures(para, false, editor);
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

globalThis.BlogRender = { renderBlogMarkdown: renderBlogMarkdown, blogSlug: blogSlug };

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
// Every post has its own page at /blog/<slug>/ (built by tools/build-blog.mjs),
// which is what link previews and search engines read. A post published in
// the last few minutes may not have its page yet: the 404 page then sends
// the reader on to post.html, which draws it here.
function postUrl(slug) { return '/blog/' + encodeURIComponent(slug) + '/'; }

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
      // "What's new in Pyr" weeks live in the side feed, not this list.
      all = posts.filter(function (p) { return !/^whats-new-in-pyr-/.test(p.slug); }).map(function (p) {
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
      goToHeading();
    })
    .catch(function () { missing('The blog could not be loaded just now. Please try again in a moment.'); });
}

// ── A post's own page (blog/<slug>/) shows the post as it is now ──────────
// Those pages are built from the published posts every 15 minutes
// (tools/build-blog.mjs), so a change published a moment ago was not there
// yet (Celia, triage #395: "publishing doesn't save my edits"). The page
// shows what it was built with straight away, then asks for the post as it
// is now and, if it changed since, draws the new version in its place.
var livePost = document.querySelector('[data-blog-live]');
if (livePost) {
  var liveSlug = livePost.getAttribute('data-blog-live') || '';
  var builtAt = livePost.getAttribute('data-updated') || '';
  if (/^[a-z0-9]+(-[a-z0-9]+)*$/.test(liveSlug)) get('select=slug,title,summary,body,cover_url,author_name,published_at,updated_at&status=eq.published&slug=eq.' + liveSlug + '&limit=1')
    .then(function (rows) {
      var p = rows[0];
      if (!p || !p.updated_at || Date.parse(p.updated_at) === Date.parse(builtAt)) return;
      var h = livePost.querySelector('[data-blog-title]');
      if (h) h.textContent = p.title;
      document.title = p.title + ' | Map the Brain';
      var body = livePost.querySelector('[data-blog-body]');
      if (!body) return;
      body.innerHTML = renderBlogMarkdown(p.body);   // escaped, then a short list of tags
      if (p.cover_url && IMG_OK.test(p.cover_url)) {
        var fig = el('figure', 'blog-post__figure blog-post__figure--cover');
        var img = el('img');
        img.src = p.cover_url;
        img.alt = '';
        fig.appendChild(img);
        body.insertBefore(fig, body.firstChild);
      }
      livePost.setAttribute('data-updated', p.updated_at);
      goToHeading();
    })
    .catch(function () { /* the built page stays as it is */ });
}

// ── Links to a heading (Ames 2026-11-08) ─────────────────────────────────
// The # beside a heading puts its address in the bar and copies it, so it
// can be pasted anywhere: connectome.quest/blog/<post>/#<heading>.
// (The page builder runs this file without a browser: no click handler there.)
if (typeof document.addEventListener === 'function') document.addEventListener('click', function (e) {
  var a = e.target && e.target.closest ? e.target.closest('.blog-anchor') : null;
  if (!a) return;
  e.preventDefault();
  var hash = a.getAttribute('href') || '';
  var target = document.getElementById(decodeURIComponent(hash.slice(1)));
  try { history.replaceState(null, '', hash); } catch (err) { location.hash = hash; }
  if (target) target.scrollIntoView({ behavior: 'smooth', block: 'start' });
  var url = location.origin + location.pathname + hash;
  var done = function () { a.classList.add('blog-anchor--copied'); setTimeout(function () { a.classList.remove('blog-anchor--copied'); }, 1600); };
  if (navigator.clipboard && navigator.clipboard.writeText) navigator.clipboard.writeText(url).then(done, function () {});
});
/** After a page draws a post's text itself, go to the heading in the address. */
function goToHeading() {
  if (!location.hash) return;
  var t = document.getElementById(decodeURIComponent(location.hash.slice(1)));
  if (t) t.scrollIntoView({ block: 'start' });
}

// ── The first post's old address forwards to its new one once it exists ─
var legacy = document.documentElement.getAttribute('data-blog-legacy');
if (legacy) {
  get('select=slug&status=eq.published&slug=eq.' + legacy + '&limit=1')
    .then(function (rows) { if (rows[0]) location.replace(postUrl(legacy)); })
    .catch(function () {});
}
// ── Click a picture to see it larger (Ames 2026-11-05) ─────────────────────
// A picture with a link (@[link]) is drawn inside that link, so a click on
// it goes there instead. In a gallery the arrows, the arrow keys and a swipe
// step through its pictures, and each picture's longer description (its ^^
// line, hidden on the page) shows under its caption here.
if (document.addEventListener) {
  var lb = null, lbList = [], lbAt = 0, lbBack = null, lbX = null;
  var lbPart = function (cls, tag) { var n = document.createElement(tag || 'div'); n.className = cls; return n; };
  var lbBuild = function () {
    lb = lbPart('blog-lightbox');
    lb.setAttribute('role', 'dialog');
    lb.setAttribute('aria-modal', 'true');
    lb.setAttribute('aria-label', 'Picture');
    lb.hidden = true;
    lb.innerHTML = '<button type="button" class="blog-lightbox__close" aria-label="Close">\u2715</button>'
      + '<button type="button" class="blog-lightbox__step blog-lightbox__step--prev" aria-label="Previous picture">\u2039</button>'
      + '<figure class="blog-lightbox__figure"><img class="blog-lightbox__img" alt="" /><figcaption class="blog-lightbox__text">'
      + '<span class="blog-lightbox__count"></span><span class="blog-lightbox__caption"></span><span class="blog-lightbox__more"></span></figcaption></figure>'
      + '<button type="button" class="blog-lightbox__step blog-lightbox__step--next" aria-label="Next picture">\u203a</button>';
    document.body.appendChild(lb);
    lb.addEventListener('click', function (e) {
      var t = e.target;
      if (t.closest('.blog-lightbox__close') || t === lb) lbClose();
      else if (t.closest('.blog-lightbox__step--prev')) lbStep(-1);
      else if (t.closest('.blog-lightbox__step--next')) lbStep(1);
    });
    lb.addEventListener('touchstart', function (e) { lbX = e.touches[0].clientX; }, { passive: true });
    lb.addEventListener('touchend', function (e) {
      if (lbX === null) return;
      var dx = e.changedTouches[0].clientX - lbX;
      lbX = null;
      if (Math.abs(dx) > 40) lbStep(dx < 0 ? 1 : -1);
    });
  };
  var lbDraw = function () {
    var fig = lbList[lbAt];
    var img = fig.querySelector('img');
    var big = lb.querySelector('.blog-lightbox__img');
    big.src = img.currentSrc || img.src;
    big.alt = img.alt || '';
    var cap = fig.querySelector('figcaption'), more = fig.querySelector('.blog-post__more');
    // both were written by renderBlogMarkdown: escaped, then a short list of tags
    lb.querySelector('.blog-lightbox__caption').innerHTML = cap ? cap.innerHTML : '';
    lb.querySelector('.blog-lightbox__more').innerHTML = more ? more.innerHTML : '';
    lb.querySelector('.blog-lightbox__count').textContent = lbList.length > 1 ? (lbAt + 1) + ' of ' + lbList.length : '';
    lb.querySelector('.blog-lightbox__text').hidden = !(cap || more || lbList.length > 1);
    lb.classList.toggle('blog-lightbox--many', lbList.length > 1);
  };
  var lbStep = function (d) { if (lbList.length < 2) return; lbAt = (lbAt + d + lbList.length) % lbList.length; lbDraw(); };
  var lbOpen = function (fig) {
    if (!lb) lbBuild();
    var g = fig.closest('.blog-post__gallery');
    lbList = g ? Array.prototype.slice.call(g.querySelectorAll('figure')) : [fig];
    lbAt = Math.max(0, lbList.indexOf(fig));
    lbBack = document.activeElement;
    lbDraw();
    lb.hidden = false;
    document.documentElement.classList.add('blog-lightbox-open');
    lb.querySelector('.blog-lightbox__close').focus();
  };
  var lbClose = function () {
    lb.hidden = true;
    document.documentElement.classList.remove('blog-lightbox-open');
    if (lbBack && lbBack.focus) lbBack.focus();
  };
  document.addEventListener('click', function (e) {
    var t = e.target;
    if (!t.closest || t.tagName !== 'IMG' || t.closest('a') || t.closest('.nge-blog')) return;
    var fig = t.closest('figure');
    if (!fig || !t.closest('[data-blog-body], #blogBody')) return;
    e.preventDefault();
    lbOpen(fig);
  });
  document.addEventListener('keydown', function (e) {
    if (!lb || lb.hidden) return;
    if (e.key === 'Escape') lbClose();
    else if (e.key === 'ArrowLeft') lbStep(-1);
    else if (e.key === 'ArrowRight') lbStep(1);
  });
}
})();
