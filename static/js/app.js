// ── Outils de champ texte : dictée vocale + reformulation IA ──
// Utilisés par le partiel « partials/_ai_text_tools.html », montable sur
// n'importe quel <input>/<textarea> en lui passant son id.

function hsDictate(btn, targetId) {
  var SR = window.SpeechRecognition || window.webkitSpeechRecognition;
  var field = document.getElementById(targetId);
  if (!field) return;
  if (!SR) { alert(btn.dataset.unsupported || 'Reconnaissance vocale non supportée par ce navigateur.'); return; }
  var rec = new SR();
  rec.lang = btn.dataset.lang || navigator.language || 'fr-FR';
  rec.interimResults = false;
  rec.onstart = function () { btn.classList.add('is-recording'); };
  rec.onend = function () { btn.classList.remove('is-recording'); };
  rec.onerror = function () { btn.classList.remove('is-recording'); };
  rec.onresult = function (e) {
    var text = e.results[0][0].transcript;
    field.value = field.value ? field.value.trim() + ' ' + text : text;
    field.dispatchEvent(new Event('input', { bubbles: true }));  // garde Alpine synchronisé
    field.focus();
  };
  rec.start();
}

function hsRewrite(btn, targetId, url, contexte) {
  var field = document.getElementById(targetId);
  if (!field) return;
  var text = (field.value || '').trim();
  if (!text) return;

  var icon = btn.querySelector('.material-icons-round');
  var token = (btn.closest('form') || document).querySelector('[name=csrfmiddlewaretoken]');
  btn.disabled = true;
  if (icon) icon.textContent = 'hourglass_empty';

  var body = new FormData();
  body.append('text', text);
  body.append('contexte', contexte || '');

  fetch(url, {
    method: 'POST',
    headers: token ? { 'X-CSRFToken': token.value } : {},
    credentials: 'same-origin',
    body: body,
  })
    .then(function (r) { return r.json(); })
    .then(function (d) {
      if (d && d.text) {
        field.value = d.text;
        field.dispatchEvent(new Event('input', { bubbles: true }));
        field.focus();
      } else if (d && d.error) {
        alert(d.error);
      }
    })
    .catch(function () {})
    .finally(function () {
      btn.disabled = false;
      if (icon) icon.textContent = 'auto_fix_high';
    });
}

// ── Recherche d'adresse (Google Places côté serveur, repli Base Adresse Nationale) ──
// Le champ de recherche remplit les champs « <prefixe>-numero/type-voie/voie/cp/ville/pays ».

function hsAddressSearch(input, prefixe, urls) {
  var boite = document.getElementById(prefixe + '-adresse-suggestions');
  if (!boite) return;

  var remplir = function (adresse) {
    var champs = {
      'numero-voie': adresse.numero_voie, 'type-voie': adresse.type_voie, 'voie': adresse.voie,
      'cp': adresse.code_postal, 'ville': adresse.ville, 'pays': adresse.pays,
    };
    Object.keys(champs).forEach(function (cle) {
      var champ = document.getElementById(prefixe + '-' + cle);
      if (!champ || !champs[cle]) return;
      champ.value = champs[cle];
      champ.dispatchEvent(new Event('input', { bubbles: true }));  // garde Alpine synchronisé
    });
    boite.innerHTML = '';
    boite.classList.add('hidden');
  };

  var choisir = function (suggestion) {
    if (suggestion.adresse) { remplir(suggestion.adresse); return; }
    fetch(urls.details + '?id=' + encodeURIComponent(suggestion.id), { credentials: 'same-origin' })
      .then(function (r) { return r.json(); })
      .then(function (d) { if (d && d.adresse) remplir(d.adresse); })
      .catch(function () {});
  };

  clearTimeout(input._hsTimer);
  var q = (input.value || '').trim();
  if (q.length < 3) { boite.innerHTML = ''; boite.classList.add('hidden'); return; }

  input._hsTimer = setTimeout(function () {
    fetch(urls.suggestions + '?q=' + encodeURIComponent(q), { credentials: 'same-origin' })
      .then(function (r) { return r.json(); })
      .then(function (d) {
        boite.innerHTML = '';
        var resultats = (d && d.results) || [];
        if (!resultats.length) { boite.classList.add('hidden'); return; }
        resultats.forEach(function (suggestion) {
          var ligne = document.createElement('button');
          ligne.type = 'button';
          ligne.className = 'hs-suggestion';
          ligne.textContent = suggestion.label;
          ligne.addEventListener('click', function () { choisir(suggestion); });
          boite.appendChild(ligne);
        });
        boite.classList.remove('hidden');
      })
      .catch(function () { boite.classList.add('hidden'); });
  }, 250);
}

// Enregistrement du service worker (PWA offline-first).
if ('serviceWorker' in navigator) {
  window.addEventListener('load', () => {
    navigator.serviceWorker.register('/sw.js', { scope: '/' }).catch(() => {});
  });
}
