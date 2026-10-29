// Edit and Write buttons on the blog (Ames 2026-10-28: "a normal blog editor
// in the blog page", with an Edit button on each post).
//
// The editor is Pyr's own (ng-extend components/BlogEditor.vue), packaged as
// /assets/blog-editor.js by ng-extend scripts/build-blog-site-editor.cjs. It
// is loaded only when someone presses a button. Signing in is the same
// Google sign in as Pyr, in a small window; the server decides who may write.
//
// Buttons:
//   [data-blog-edit="<slug>"]   edit that post (post.html fills in its slug)
//   [data-blog-edit=""]         write a new post
// A button marked data-blog-author-only shows only in a browser where a blog
// author has signed in before; the rest always show.
(function () {
  'use strict';
  var VERSION = '2';
  var author = false;
  try { author = localStorage.getItem('pyr-blog-author') === '1'; } catch (e) { /* storage blocked */ }

  var buttons = document.querySelectorAll('[data-blog-edit]');
  Array.prototype.forEach.call(buttons, function (b) {
    if (b.hasAttribute('data-blog-author-only') && !author) return;
    b.hidden = false;
    b.addEventListener('click', function (e) { e.preventDefault(); start(b); });
  });

  var loading = null;
  function load() {
    if (loading) return loading;
    loading = new Promise(function (resolve, reject) {
      var css = document.createElement('link');
      css.rel = 'stylesheet';
      css.href = '/assets/blog-editor.css?v=' + VERSION;
      document.head.appendChild(css);
      var s = document.createElement('script');
      s.src = '/assets/blog-editor.js?v=' + VERSION;
      s.onload = function () { window.PyrBlogEditor ? resolve(window.PyrBlogEditor) : reject(new Error('The editor did not load.')); };
      s.onerror = function () { reject(new Error('The editor could not be loaded. Check the connection and try again.')); };
      document.head.appendChild(s);
    });
    loading.catch(function () { loading = null; });
    return loading;
  }

  function say(button, text) {
    var note = button.parentNode.querySelector('.blog-edit__note');
    if (!note) {
      note = document.createElement('p');
      note.className = 'blog-edit__note';
      note.setAttribute('role', 'status');
      button.parentNode.insertBefore(note, button.nextSibling);
    }
    note.textContent = text;
  }

  function start(button) {
    var slug = button.getAttribute('data-blog-edit') || '';
    if (slug === '?p') slug = new URLSearchParams(location.search).get('p') || '';
    var main = document.querySelector('main');
    if (!main) return;
    button.disabled = true;
    say(button, 'Opening the editor. A sign in window may open.');
    load().then(function (editor) {
      var host = document.getElementById('blogEditorHost');
      if (!host) {
        host = document.createElement('section');
        host.id = 'blogEditorHost';
        host.className = 'wrap blog-edit__host';
        main.parentNode.insertBefore(host, main);
      }
      return editor.open(host, slug, function () {
        // Closed: back to the page, freshly loaded so it shows what was saved.
        location.reload();
      }).then(function () {
        main.hidden = true;
        host.hidden = false;
        window.scrollTo(0, 0);
      });
    }).catch(function (err) {
      say(button, (err && err.message) || 'The editor could not be opened.');
    }).then(function () {
      button.disabled = false;
      var note = button.parentNode.querySelector('.blog-edit__note');
      if (note && /^Opening/.test(note.textContent)) note.remove();
    });
  }
})();
