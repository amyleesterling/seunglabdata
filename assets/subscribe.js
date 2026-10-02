// Subscribe form (blog pages). Same form and endpoint as the homepage, index.html.
(function () {
  var form = document.getElementById('subscribeForm');
  if (!form) return;
  var statusEl = document.getElementById('sub-status');
  var submitBtn = document.getElementById('sub-submit');

  // Google Apps Script web app (subscribe-to-sheet.gs) that appends each
  // signup as a row in the Connectome.Quest Subscribe sheet.
  var ENDPOINT = 'https://script.google.com/macros/s/AKfycbxB4zbbzrivwkpgAMtdto2zPc95lamxTlw8KnZPi5MkjHftWKq5RJhAlvjP_zragwdtCg/exec';

  form.addEventListener('submit', function (e) {
    e.preventDefault();
    var name = document.getElementById('sub-name').value.trim();
    var email = document.getElementById('sub-email').value.trim();
    var country = document.getElementById('sub-country').value.trim();
    var username = document.getElementById('sub-username').value.trim();
    if (form._honey && form._honey.value) return; // bot trap
    if (!name || !email || !country) {
      statusEl.textContent = 'Please add your name, email, and country.';
      return;
    }
    if (ENDPOINT.indexOf('http') !== 0) {
      statusEl.textContent = 'Signup is not connected yet. Please check back soon.';
      return;
    }

    submitBtn.disabled = true;
    var label = submitBtn.textContent;
    submitBtn.textContent = 'Subscribing…';
    statusEl.textContent = '';

    // URLSearchParams keeps this a simple CORS request (no preflight);
    // no-cors lets the Apps Script append the row without a CORS response header.
    fetch(ENDPOINT, {
      method: 'POST',
      mode: 'no-cors',
      body: new URLSearchParams({
        name: name,
        email: email,
        country: country,
        eyewire_username: username || ''
      })
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
      .catch(function () {
        statusEl.innerHTML = "We couldn't sign you up just now. Please try again, or reach us on the <a href='https://discuss.flywire.ai/' target='_blank' rel='noreferrer'>community forum</a>.";
      })
      .finally(function () {
        submitBtn.disabled = false;
        submitBtn.textContent = label;
      });
  });
})();
