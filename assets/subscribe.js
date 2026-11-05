// Subscribe form, on the homepage and every blog page (Ames 2026-11-05).
// Signups go to the blog email list in Resend through Pyr's ewBlogMail
// function (ng-extend functions/blog-mail.js); every new blog post is then
// emailed to the list, with a one click unsubscribe. The old Google Apps
// Script sheet stopped taking signups (it answered 403, unseen behind no-cors).
(function () {
  var form = document.getElementById('subscribeForm');
  if (!form) return;
  var statusEl = document.getElementById('sub-status');
  var submitBtn = document.getElementById('sub-submit');
  var ENDPOINT = 'https://us-central1-eyewire-ii-e4d52.cloudfunctions.net/ewBlogMail';
  var value = function (id) { var el = document.getElementById(id); return el ? el.value.trim() : ''; };

  form.addEventListener('submit', function (e) {
    e.preventDefault();
    var name = value('sub-name');
    var email = value('sub-email');
    if (!name || !email) {
      statusEl.textContent = 'Please add your name and email.';
      return;
    }

    submitBtn.disabled = true;
    var label = submitBtn.textContent;
    submitBtn.textContent = 'Subscribing…';
    statusEl.textContent = '';

    fetch(ENDPOINT, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        action: 'subscribe',
        name: name,
        email: email,
        username: value('sub-username'),
        source: form.getAttribute('data-source') || 'blog',
        _honey: form._honey ? form._honey.value : ''
      })
    })
      .then(function (r) {
        return r.json().catch(function () { return {}; }).then(function (j) {
          if (!r.ok || !j.ok) throw new Error(j.error || '');
        });
      })
      .then(function () {
        form.reset();
        var success = document.getElementById('subscribeSuccess');
        if (success) {
          form.hidden = true;
          success.hidden = false;
        } else {
          statusEl.textContent = "You're on the list. Thanks for joining the quest!";
        }
      })
      .catch(function (err) {
        // The server's own words when it has them ("Please check your email address.").
        var said = err && err.message;
        statusEl.textContent = said || "We couldn't sign you up just now. Please try again in a moment.";
      })
      .finally(function () {
        submitBtn.disabled = false;
        submitBtn.textContent = label;
      });
  });
})();
