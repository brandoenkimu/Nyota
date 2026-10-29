/* Nyota: twinkling starfield + shooting stars, shop constellation, login warp */
(function () {
  'use strict';
  var reduce = window.matchMedia && matchMedia('(prefers-reduced-motion: reduce)').matches;

  function rgb() {
    var v = getComputedStyle(document.documentElement).getPropertyValue('--accent-rgb').trim() || '139,92,246';
    return v;
  }
  function isLight() { return document.documentElement.getAttribute('data-ui') === 'light'; }

  function Starfield(canvas) {
    var ctx = canvas.getContext('2d'), w, h, stars = [], shooters = [], dpr = Math.min(window.devicePixelRatio || 1, 2);
    function resize() {
      w = canvas.clientWidth; h = canvas.clientHeight;
      canvas.width = w * dpr; canvas.height = h * dpr; ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      var n = Math.round(Math.min(220, (w * h) / 6500));
      stars = [];
      for (var i = 0; i < n; i++) stars.push({
        x: Math.random() * w, y: Math.random() * h, r: Math.random() * 1.4 + .3,
        p: Math.random() * 6.28, s: Math.random() * .02 + .005, d: Math.random() * .5 + .2
      });
    }
    function shoot() {
      if (shooters.length < 2 && Math.random() < .012)
        shooters.push({ x: Math.random() * w, y: Math.random() * h * .5, vx: 7 + Math.random() * 6, vy: 3 + Math.random() * 3, life: 1 });
    }
    function frame() {
      ctx.clearRect(0, 0, w, h);
      if (isLight()) { requestAnimationFrame(frame); return; }
      var a = rgb();
      for (var i = 0; i < stars.length; i++) {
        var s = stars[i]; s.p += s.s;
        var o = .35 + Math.sin(s.p) * .35 + .3;
        ctx.beginPath(); ctx.arc(s.x, s.y, s.r, 0, 6.283);
        ctx.fillStyle = (i % 9 === 0) ? 'rgba(' + a + ',' + o + ')' : 'rgba(255,255,255,' + o * s.d + ')';
        ctx.fill();
        if (s.r > 1.2) { ctx.fillStyle = 'rgba(255,255,255,' + o * .12 + ')'; ctx.fillRect(s.x - 6, s.y - .3, 12, .6); ctx.fillRect(s.x - .3, s.y - 6, .6, 12); }
      }
      shoot();
      for (var j = shooters.length - 1; j >= 0; j--) {
        var m = shooters[j]; m.x += m.vx; m.y += m.vy; m.life -= .016;
        var g = ctx.createLinearGradient(m.x, m.y, m.x - m.vx * 9, m.y - m.vy * 9);
        g.addColorStop(0, 'rgba(255,255,255,' + m.life + ')'); g.addColorStop(1, 'rgba(' + a + ',0)');
        ctx.strokeStyle = g; ctx.lineWidth = 1.6; ctx.beginPath(); ctx.moveTo(m.x, m.y); ctx.lineTo(m.x - m.vx * 9, m.y - m.vy * 9); ctx.stroke();
        if (m.life <= 0 || m.x > w + 50 || m.y > h + 50) shooters.splice(j, 1);
      }
      requestAnimationFrame(frame);
    }
    resize(); window.addEventListener('resize', resize);
    if (reduce) { frame = function () { }; }
    requestAnimationFrame(frame);
  }

  /* shops as a constellation: data-shops='[{"name","url","city","size"}]' */
  function Constellation(box) {
    var canvas = box.querySelector('canvas'), tip = box.querySelector('.const-tip'), ctx = canvas.getContext('2d');
    var data = []; try { data = JSON.parse(box.getAttribute('data-shops') || '[]'); } catch (e) { }
    var w, h, dpr = Math.min(window.devicePixelRatio || 1, 2), nodes = [], mouse = { x: -999, y: -999 }, hover = null;
    function layout() {
      w = box.clientWidth; h = box.clientHeight; canvas.width = w * dpr; canvas.height = h * dpr; ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      nodes = data.map(function (d, i) {
        var a = i / Math.max(1, data.length) * 6.283 + (Math.random() - .5) * .4, rr = .25 + .2 * ((i * 7) % 5) / 4;
        return { d: d, x: w / 2 + Math.cos(a) * w * rr * 1.5, y: h / 2 + Math.sin(a) * h * (rr + .1), bx: 0, by: 0, ph: Math.random() * 6.28, r: 5 + Math.min(9, (d.size || 1)) };
      });
      nodes.forEach(function (n) { n.bx = n.x; n.by = n.y; });
    }
    function draw(t) {
      ctx.clearRect(0, 0, w, h); var a = rgb(); hover = null;
      nodes.forEach(function (n) {
        n.x = n.bx + Math.sin(t / 1800 + n.ph) * 8; n.y = n.by + Math.cos(t / 2100 + n.ph) * 8;
        if (Math.hypot(mouse.x - n.x, mouse.y - n.y) < n.r + 8) hover = n;
      });
      ctx.lineWidth = 1;
      for (var i = 0; i < nodes.length; i++) for (var j = i + 1; j < nodes.length; j++) {
        var d = Math.hypot(nodes[i].x - nodes[j].x, nodes[i].y - nodes[j].y);
        if (d < w * .28) { ctx.strokeStyle = 'rgba(' + a + ',' + (1 - d / (w * .28)) * .45 + ')'; ctx.beginPath(); ctx.moveTo(nodes[i].x, nodes[i].y); ctx.lineTo(nodes[j].x, nodes[j].y); ctx.stroke(); }
      }
      nodes.forEach(function (n) {
        var tw = .6 + Math.sin(t / 500 + n.ph) * .4, rad = n.r * (n === hover ? 1.6 : 1);
        var g = ctx.createRadialGradient(n.x, n.y, 0, n.x, n.y, rad * 4);
        g.addColorStop(0, 'rgba(' + a + ',' + .9 * tw + ')'); g.addColorStop(1, 'rgba(' + a + ',0)');
        ctx.fillStyle = g; ctx.beginPath(); ctx.arc(n.x, n.y, rad * 4, 0, 6.283); ctx.fill();
        ctx.fillStyle = '#fff'; ctx.beginPath(); ctx.arc(n.x, n.y, rad * .6, 0, 6.283); ctx.fill();
      });
      if (hover) { tip.textContent = hover.d.name + (hover.d.city ? ' · ' + hover.d.city : ''); tip.style.left = hover.x + 'px'; tip.style.top = hover.y + 'px'; tip.classList.add('on'); canvas.style.cursor = 'pointer'; }
      else { tip.classList.remove('on'); canvas.style.cursor = 'default'; }
      requestAnimationFrame(draw);
    }
    canvas.addEventListener('mousemove', function (e) { var r = canvas.getBoundingClientRect(); mouse.x = e.clientX - r.left; mouse.y = e.clientY - r.top; });
    canvas.addEventListener('mouseleave', function () { mouse.x = mouse.y = -999; });
    canvas.addEventListener('click', function () { if (hover) location.href = hover.d.url; });
    layout(); window.addEventListener('resize', layout); requestAnimationFrame(draw);
  }

  /* hyperspace warp played after a successful login submit */
  window.NyotaWarp = function (done) {
    var el = document.createElement('div'); el.className = 'warp'; var c = document.createElement('canvas'); el.appendChild(c); document.body.appendChild(el);
    var w = c.width = innerWidth, h = c.height = innerHeight, ctx = c.getContext('2d'), a = rgb(), pts = [], t0 = performance.now();
    for (var i = 0; i < 260; i++) pts.push({ ang: Math.random() * 6.283, r: Math.random() * 40, v: 2 + Math.random() * 5 });
    requestAnimationFrame(function () { el.classList.add('on'); });
    (function step(t) {
      var p = Math.min(1, (t - t0) / 900);
      ctx.fillStyle = 'rgba(0,0,0,.25)'; ctx.fillRect(0, 0, w, h);
      pts.forEach(function (s) {
        var px = w / 2 + Math.cos(s.ang) * s.r, py = h / 2 + Math.sin(s.ang) * s.r; s.r += s.v * (1 + p * 9);
        var nx = w / 2 + Math.cos(s.ang) * s.r, ny = h / 2 + Math.sin(s.ang) * s.r;
        ctx.strokeStyle = 'rgba(' + (Math.random() < .25 ? a : '255,255,255') + ',' + (.4 + p * .6) + ')'; ctx.lineWidth = 1 + p * 1.6;
        ctx.beginPath(); ctx.moveTo(px, py); ctx.lineTo(nx, ny); ctx.stroke();
        if (s.r > Math.max(w, h)) s.r = Math.random() * 30;
      });
      if (p < 1) requestAnimationFrame(step); else done && done();
    })(t0);
  };

  document.addEventListener('DOMContentLoaded', function () {
    document.querySelectorAll('canvas.starfield').forEach(Starfield);
    document.querySelectorAll('.constellation').forEach(Constellation);
  });
})();
