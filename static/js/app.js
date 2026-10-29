/* Nyota: core UI behaviour */
(function () {
  'use strict';
  var N = window.Nyota = window.Nyota || {};
  var $ = function (s, r) { return (r || document).querySelector(s); };
  var $$ = function (s, r) { return Array.prototype.slice.call((r || document).querySelectorAll(s)); };
  N.$ = $; N.$$ = $$;

  function cookie(n) { var m = document.cookie.match('(^|;)\\s*' + n + '=([^;]+)'); return m ? decodeURIComponent(m[2]) : ''; }
  N.csrf = function () { return cookie('csrftoken'); };
  N.post = function (url, body, json) {
    var h = { 'X-CSRFToken': N.csrf(), 'X-Requested-With': 'XMLHttpRequest' }, opts = { method: 'POST', headers: h, credentials: 'same-origin' };
    if (json) { h['Content-Type'] = 'application/json'; opts.body = JSON.stringify(body || {}); }
    else { opts.body = body instanceof FormData ? body : new URLSearchParams(body || {}); }
    return fetch(url, opts).then(function (r) { return r.json().catch(function () { return {}; }).then(function (d) { d._status = r.status; if (r.status === 401 && d.login) { location.href = d.login; } return d; }); });
  };
  function ls(k, v) { try { if (v === undefined) return localStorage.getItem(k); localStorage.setItem(k, v); } catch (e) { } return null; }

  /* ---------- toasts */
  N.toast = function (msg, kind) {
    var box = $('#toasts'); if (!box) { box = document.createElement('div'); box.id = 'toasts'; box.className = 'ny-toasts'; document.body.appendChild(box); }
    var t = document.createElement('div'); t.className = 'ny-toast ' + (kind || 'info');
    t.setAttribute('role', 'status'); t.textContent = msg; box.appendChild(t);
    setTimeout(function () { t.style.opacity = 0; t.style.transform = 'translateX(30px)'; setTimeout(function () { t.remove(); }, 400); }, 4200);
  };
  $$('[data-toast]').forEach(function (el) { N.toast(el.getAttribute('data-toast'), el.getAttribute('data-kind')); el.remove(); });

  /* ---------- themes and accents */
  var root = document.documentElement;
  var DARK = (window.NYOTA_DARK || {});
  N.applyTheme = function (theme, accent, save) {
    if (theme) { ls('ny_theme', theme); root.setAttribute('data-pref', theme); }
    if (accent) { ls('ny_accent', accent); root.setAttribute('data-accent', accent); }
    var pref = root.getAttribute('data-pref') || 'auto';
    var r = window.NYOTA_RESOLVE ? window.NYOTA_RESOLVE(pref) : pref, k = DARK[r] === false ? 'light' : 'dark';
    root.setAttribute('data-theme', r); root.setAttribute('data-bs-theme', k); root.setAttribute('data-ui', k);
    $$('[data-set-theme]').forEach(function (e) { e.classList.toggle('on', e.getAttribute('data-set-theme') === pref); });
    $$('[data-set-accent]').forEach(function (e) { e.classList.toggle('on', e.getAttribute('data-set-accent') === root.getAttribute('data-accent')); });
    if (save !== false && (theme || accent) && root.hasAttribute('data-authed')) N.post('/api/theme/', { theme: theme, accent: accent }, true);
  };
  document.addEventListener('click', function (e) {
    var t = e.target.closest('[data-set-theme]'), a = e.target.closest('[data-set-accent]');
    if (t) N.applyTheme(t.getAttribute('data-set-theme'), null);
    if (a) N.applyTheme(null, a.getAttribute('data-set-accent'));
  });
  N.applyTheme(null, null, false);
  try {   /* follow the device live while the choice is "auto" */
    var mq = matchMedia('(prefers-color-scheme: dark)'), onMq = function () { if ((root.getAttribute('data-pref') || 'auto') === 'auto') N.applyTheme(null, null, false); };
    if (mq.addEventListener) mq.addEventListener('change', onMq); else if (mq.addListener) mq.addListener(onMq);
  } catch (e) { }

  /* ---------- reveal on scroll, counters, tilt */
  if ('IntersectionObserver' in window) {
    var io = new IntersectionObserver(function (es) {
      es.forEach(function (e) {
        if (!e.isIntersecting) return; e.target.classList.add('in'); io.unobserve(e.target);
        var c = e.target.getAttribute('data-count'); if (c) countUp(e.target, +c);
      });
    }, { threshold: .12 });
    $$('.reveal, [data-count]').forEach(function (el) { io.observe(el); });
  } else { $$('.reveal').forEach(function (el) { el.classList.add('in'); }); }
  function countUp(el, to) {
    var t0 = performance.now(), d = 1400, pre = el.getAttribute('data-prefix') || '', suf = el.getAttribute('data-suffix') || '';
    (function s(t) { var p = Math.min(1, (t - t0) / d), v = Math.round(to * (1 - Math.pow(1 - p, 3))); el.textContent = pre + v.toLocaleString() + suf; if (p < 1) requestAnimationFrame(s); })(t0);
  }
  if (matchMedia('(hover:hover)').matches && !matchMedia('(prefers-reduced-motion: reduce)').matches) {
    document.addEventListener('mousemove', function (e) {
      var c = e.target.closest && e.target.closest('.pcard'); if (!c) return;
      var r = c.getBoundingClientRect(); c.style.setProperty('--ry', ((e.clientX - r.left) / r.width - .5) * 8 + 'deg'); c.style.setProperty('--rx', (-((e.clientY - r.top) / r.height - .5)) * 8 + 'deg');
    });
    document.addEventListener('mouseout', function (e) { var c = e.target.closest && e.target.closest('.pcard'); if (c && !c.contains(e.relatedTarget)) { c.style.setProperty('--rx', '0deg'); c.style.setProperty('--ry', '0deg'); } });
  }

  /* ---------- hero carousel */
  $$('.hero').forEach(function (hero) {
    var slides = $$('.hero-slide', hero), dots = $$('.hero-dot', hero), i = 0, timer, dur = 6500;
    if (!slides.length) return;
    hero.style.setProperty('--dur', dur + 'ms');
    function go(n) {
      i = (n + slides.length) % slides.length;
      slides.forEach(function (s, k) { s.classList.toggle('on', k === i); });
      dots.forEach(function (d, k) { d.classList.remove('on'); d.classList.toggle('done', k < i); void d.offsetWidth; if (k === i) d.classList.add('on'); });
      clearTimeout(timer); if (slides.length > 1) timer = setTimeout(function () { go(i + 1); }, dur);
    }
    dots.forEach(function (d, k) { d.addEventListener('click', function () { go(k); }); });
    var p = $('[data-hero-prev]', hero), n = $('[data-hero-next]', hero);
    if (p) p.addEventListener('click', function () { go(i - 1); }); if (n) n.addEventListener('click', function () { go(i + 1); });
    hero.addEventListener('mousemove', function (e) { var r = hero.getBoundingClientRect(); hero.style.setProperty('--mx', (e.clientX - r.left) / r.width - .5); hero.style.setProperty('--my', (e.clientY - r.top) / r.height - .5); });
    hero.addEventListener('mouseenter', function () { clearTimeout(timer); }); hero.addEventListener('mouseleave', function () { go(i); });
    go(0);
  });

  /* ---------- scroll rails */
  $$('.rail-wrap').forEach(function (w) {
    var rail = $('.rail', w); if (!rail) return;
    var step = function (d) { rail.scrollBy({ left: d * Math.max(280, rail.clientWidth * .8), behavior: 'smooth' }); };
    var p = $('.rail-btn.prev', w), n = $('.rail-btn.next', w);
    if (p) p.addEventListener('click', function () { step(-1); }); if (n) n.addEventListener('click', function () { step(1); });
  });

  /* ---------- tabs */
  $$('[data-tabs]').forEach(function (box) {
    var btns = $$('[data-tab]', box), panes = $$('.tabpane', box.parentNode);
    function show(id) { btns.forEach(function (b) { b.classList.toggle('on', b.getAttribute('data-tab') === id); }); panes.forEach(function (p) { p.classList.toggle('on', p.id === id); }); }
    btns.forEach(function (b) { b.addEventListener('click', function () { show(b.getAttribute('data-tab')); }); });
    if (btns[0]) show(btns[0].getAttribute('data-tab'));
  });

  /* ---------- gallery + qty */
  $$('[data-gallery]').forEach(function (g) {
    var main = $('.gal-main', g);
    $$('.gal-thumbs button', g).forEach(function (b) {
      b.addEventListener('click', function () {
        $$('.gal-thumbs button', g).forEach(function (x) { x.classList.remove('on'); }); b.classList.add('on');
        var src = b.getAttribute('data-src'), im = $('img.gal-photo', main);
        if (src && im) im.src = src;
      });
    });
  });
  document.addEventListener('click', function (e) {
    var b = e.target.closest('[data-qty]'); if (!b) return;
    var inp = $('input', b.closest('.qty')), v = (parseInt(inp.value, 10) || 1) + parseInt(b.getAttribute('data-qty'), 10), mx = parseInt(inp.max, 10) || 999;
    inp.value = Math.max(1, Math.min(mx, v)); inp.dispatchEvent(new Event('change', { bubbles: true }));
  });

  /* ---------- cart / wishlist ajax */
  function setCart(n) { $$('[data-cart-count]').forEach(function (e) { e.textContent = n; e.style.display = n ? '' : 'none'; }); }
  document.addEventListener('submit', function (e) {
    var f = e.target.closest('form[data-ajax-cart]'); if (!f) return; e.preventDefault();
    if (e.submitter && e.submitter.name === 'buy_now') { f.submit(); return; }
    N.post(f.action, new FormData(f)).then(function (d) {
      N.toast(d.message || 'Done', d.ok ? 'success' : 'error'); if (d.count !== undefined) setCart(d.count);
      var b = $('.add-btn', f); if (b && d.ok) { b.classList.add('done'); setTimeout(function () { b.classList.remove('done'); }, 1400); }
    });
  });
  document.addEventListener('click', function (e) {
    var b = e.target.closest('[data-wish]'); if (!b) return; e.preventDefault();
    if (!root.hasAttribute('data-authed')) { location.href = '/login/?next=' + encodeURIComponent(location.pathname); return; }
    N.post(b.getAttribute('data-wish'), {}).then(function (d) { if (d.ok === false) return; b.classList.toggle('on', !!d.saved); N.toast(d.saved ? 'Saved to wishlist' : 'Removed from wishlist', 'success'); });
  });

  /* ---------- search suggestions */
  var si = $('#q'), sg = $('#suggest'), tmr;
  if (si && sg) {
    si.addEventListener('input', function () {
      clearTimeout(tmr); var q = si.value.trim();
      if (q.length < 2) { sg.classList.remove('open'); return; }
      tmr = setTimeout(function () {
        fetch('/api/search/?q=' + encodeURIComponent(q)).then(function (r) { return r.json(); }).then(function (d) {
          var h = ''; function esc(s) { var x = document.createElement('div'); x.textContent = s; return x.innerHTML; }
          if (d.products.length) { h += '<div class="grp">Products</div>'; d.products.forEach(function (p) { h += '<a href="' + p.url + '"><span>' + esc(p.name) + '<small class="text-muted d-block">' + esc(p.shop) + '</small></span><b>' + esc(window.NYOTA_CUR || 'KES') + ' ' + Number(p.price).toLocaleString() + '</b></a>'; }); }
          if (d.shops.length) { h += '<div class="grp">Shops</div>'; d.shops.forEach(function (s) { h += '<a href="' + s.url + '"><span>' + esc(s.name) + '</span><small class="text-muted">' + esc(s.city || '') + '</small></a>'; }); }
          sg.innerHTML = h || '<div class="grp">No matches</div>'; sg.classList.add('open');
        });
      }, 220);
    });
    document.addEventListener('click', function (e) { if (!e.target.closest('.hsearch')) sg.classList.remove('open'); });
  }

  /* ---------- sidebar, password helpers, login animation */
  var sb = $('.sidebar'); $$('.side-toggle').forEach(function (b) { b.addEventListener('click', function () { sb.classList.toggle('open'); }); });
  document.addEventListener('click', function (e) { if (sb && sb.classList.contains('open') && !e.target.closest('.sidebar') && !e.target.closest('.side-toggle')) sb.classList.remove('open'); });
  $$('[data-pw-toggle]').forEach(function (b) { b.addEventListener('click', function () { var i = document.getElementById(b.getAttribute('data-pw-toggle')); i.type = i.type === 'password' ? 'text' : 'password'; }); });
  $$('[data-pw-meter]').forEach(function (i) {
    var bar = $('i', document.getElementById(i.getAttribute('data-pw-meter')));
    i.addEventListener('input', function () {
      var v = i.value, s = 0; if (v.length >= 8) s++; if (v.length >= 12) s++; if (/[A-Z]/.test(v) && /[a-z]/.test(v)) s++; if (/\d/.test(v)) s++; if (/[^A-Za-z0-9]/.test(v)) s++;
      bar.style.width = s * 20 + '%'; bar.style.background = ['#ef4444', '#ef4444', '#f59e0b', '#eab308', '#22c55e', '#10b981'][s];
    });
  });
  $$('form[data-warp]').forEach(function (f) {
    f.addEventListener('submit', function (e) {
      if (f.dataset.warping || !f.checkValidity() || !window.NyotaWarp) return;
      e.preventDefault(); f.dataset.warping = 1;
      window.NyotaWarp(function () { f.submit(); }); setTimeout(function () { f.submit(); }, 2500);
    });
  });
  var errs = $('.auth-card .note.bad, .auth-card .invalid-feedback, .auth-card .errorlist'); if (errs) { var c = $('.auth-card'); c.classList.add('shake'); }
  $$('[data-copy]').forEach(function (b) { b.addEventListener('click', function () { navigator.clipboard && navigator.clipboard.writeText(b.getAttribute('data-copy')).then(function () { N.toast('Copied', 'success'); }); }); });
  $$('[data-confirm]').forEach(function (el) { el.addEventListener('click', function (e) { if (!confirm(el.getAttribute('data-confirm'))) e.preventDefault(); }); });
  $$('tr.click[data-href]').forEach(function (tr) { tr.addEventListener('click', function (e) { if (!e.target.closest('a,button,input,form')) location.href = tr.getAttribute('data-href'); }); });
  /* live clock */
  $$('[data-clock]').forEach(function (el) { (function t() { el.textContent = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' }); setTimeout(t, 1000); })(); });
})();
