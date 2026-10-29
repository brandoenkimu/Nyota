/* Chart.js wrappers. Usage: <canvas data-chart='{"type":"line","labels":[],"datasets":[{"label":"","data":[]}]}'> */
(function () {
  'use strict';
  if (!window.Chart) return;
  function css(v) { return getComputedStyle(document.documentElement).getPropertyValue(v).trim(); }
  var PAL = ['#8b5cf6', '#10b981', '#f5b324', '#f43f5e', '#0ea5e9', '#fb7c2c', '#d946ef', '#14b8a6'];
  function build(cv) {
    var cfg = {}; try { cfg = JSON.parse(cv.getAttribute('data-chart')); } catch (e) { return; }
    var type = cfg.type || 'line', acc = css('--accent') || PAL[0], txt = css('--muted') || '#999', grid = css('--line') || 'rgba(128,128,128,.2)';
    var circ = type === 'doughnut' || type === 'pie';
    var ds = (cfg.datasets || []).map(function (d, i) {
      var c = d.color || (i === 0 && !circ ? acc : PAL[i % PAL.length]);
      var o = Object.assign({ borderWidth: type === 'bar' ? 0 : 2.5, tension: .38, pointRadius: 0, pointHoverRadius: 5, borderRadius: 8 }, d);
      if (circ) { o.backgroundColor = (d.data || []).map(function (_, k) { return PAL[k % PAL.length]; }); o.borderWidth = 0; }
      else {
        o.borderColor = c; o.backgroundColor = type === 'line' ? (function () { var g = cv.getContext('2d').createLinearGradient(0, 0, 0, cv.height || 300); g.addColorStop(0, c + '66'); g.addColorStop(1, c + '00'); return g; })() : c;
        if (type === 'line' && d.fill !== false) o.fill = true;
      }
      return o;
    });
    new Chart(cv, {
      type: type, data: { labels: cfg.labels || [], datasets: ds },
      options: Object.assign({
        responsive: true, maintainAspectRatio: false, interaction: { mode: 'index', intersect: false },
        plugins: { legend: { display: ds.length > 1 || circ, position: 'bottom', labels: { color: txt, usePointStyle: true, boxWidth: 8 } }, tooltip: { backgroundColor: css('--surface-solid') || '#111', titleColor: css('--text') || '#fff', bodyColor: css('--text') || '#fff', borderColor: grid, borderWidth: 1, padding: 12, cornerRadius: 12 } },
        scales: circ ? {} : { x: { grid: { display: false }, ticks: { color: txt, maxTicksLimit: 8 } }, y: { beginAtZero: true, grid: { color: grid }, ticks: { color: txt, maxTicksLimit: 6 } } },
        cutout: circ ? '68%' : undefined, animation: { duration: 1100, easing: 'easeOutQuart' }
      }, cfg.options || {})
    });
  }
  document.querySelectorAll('canvas[data-chart]').forEach(build);
})();
