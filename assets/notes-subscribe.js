// "What's new in Pyr" by email (Ames 2026-11-11): the box on each weekly
// release notes page. Ticking it signs you up with your Pyr email: you sign in
// with the same Google sign in as Pyr (a small window, as for the blog editor),
// and the server reads your email from that sign in, so nothing is typed.
// The list lives in Resend; ng-extend functions/blog-mail.js (action "notes")
// does the signing up, and sends each finished week the Monday after.
(function () {
  'use strict';
  var ENDPOINT = 'https://us-central1-eyewire-ii-e4d52.cloudfunctions.net/ewBlogMail';
  var AUTH_URL = 'https://global.daf-apis.com/sticky_auth';
  var TOKEN_KEY = 'auth_token_v2_' + AUTH_URL;   // the same key Pyr and the blog editor use

  var wrap = document.querySelector('[data-notes-sub]');
  if (!wrap) return;
  var box = wrap.querySelector('[data-notes-box]');
  var status = wrap.querySelector('[data-notes-status]');
  wrap.hidden = false;

  function token() {
    try { var raw = localStorage.getItem(TOKEN_KEY); return raw ? (JSON.parse(raw).accessToken || null) : null; }
    catch (e) { return null; }
  }
  function forget() { try { localStorage.removeItem(TOKEN_KEY); } catch (e) { /* storage blocked */ } }
  function say(text) { status.textContent = text; }

  /** Sign in through the Pyr (CAVE) window, if this browser is not signed in yet. */
  function signIn() {
    if (token()) return Promise.resolve();
    return new Promise(function (resolve, reject) {
      var w = 420, h = 680;
      var popup = window.open(AUTH_URL + '/api/v1/authorize', 'pyr-sign-in',
        'toolbar=no,menubar=no,width=' + w + ',height=' + h + ',left=' + Math.max(0, (screen.width - w) / 2) + ',top=' + Math.max(0, (screen.height - h) / 2));
      if (!popup) { reject(new Error('The sign in window was blocked. Allow pop ups for connectome.quest and try again.')); return; }
      var closed = setInterval(function () {
        if (popup.closed) { cleanup(); reject(new Error('The sign in window was closed before you signed in.')); }
      }, 800);
      function cleanup() { clearInterval(closed); window.removeEventListener('message', onMessage); }
      function onMessage(ev) {
        if (ev.source !== popup) return;
        var data = ev.data || {};
        if (typeof data.token !== 'string' || !data.token) return;
        cleanup();
        try { popup.close(); } catch (e) { /* already closed */ }
        try {
          localStorage.setItem(TOKEN_KEY, JSON.stringify({ tokenType: 'Bearer', accessToken: data.token, url: AUTH_URL, appUrls: Array.isArray(data.app_urls) ? data.app_urls : [] }));
        } catch (e) { /* storage blocked: this visit only */ }
        resolve(data.token);
      }
      window.addEventListener('message', onMessage);
    });
  }

  function ask(body) {
    return fetch(ENDPOINT, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) })
      .then(function (r) {
        return r.json().catch(function () { return {}; }).then(function (j) {
          if (r.status === 401) { forget(); var e = new Error('signin'); e.signin = true; throw e; }
          if (!r.ok) throw new Error(j.error || 'That did not go through. Please try again in a moment.');
          return j;
        });
      });
  }

  function shown(state) {
    box.checked = !!state.on;
    say(state.on ? 'You\'re on the list. It goes to ' + state.email + '.' : '');
  }

  // Already signed in here: show whether this person is on the list.
  if (token()) {
    ask({ action: 'notes', token: token() }).then(shown).catch(function () { /* the box still works */ });
  }

  var busy = false;
  box.addEventListener('change', function () {
    if (busy) return;
    var want = box.checked;
    busy = true;
    box.disabled = true;
    say(want ? (token() ? 'Signing you up.' : 'Sign in with your Pyr account in the small window.') : 'Taking you off the list.');
    var go = function () { return signIn().then(function () { return ask({ action: 'notes', token: token(), on: want }); }); };
    go().catch(function (e) {
      // The sign in had run out: sign in once more, then try again.
      if (e && e.signin) { say('Sign in with your Pyr account in the small window.'); return go(); }
      throw e;
    }).then(function (state) {
      shown(state);
      if (!state.on) say('You\'re off the list. Tick the box any time to get it again.');
    }).catch(function (e) {
      box.checked = !want;
      say(e && e.signin ? 'We couldn\'t sign you in. Please try again.' : (e && e.message) || 'That did not go through. Please try again in a moment.');
    }).then(function () { busy = false; box.disabled = false; });
  });
})();
