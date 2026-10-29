/* Leaflet helpers (OpenStreetMap tiles). Requires Leaflet loaded first. */
(function () {
  'use strict';
  if (!window.L) return;
  var N = window.Nyota = window.Nyota || {};
  function tiles(map) { L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', { maxZoom: 19, attribution: '&copy; OpenStreetMap contributors' }).addTo(map); }
  function pin(color) {
    return L.divIcon({ className: '', iconSize: [30, 40], iconAnchor: [15, 38], popupAnchor: [0, -34],
      html: '<svg width="30" height="40" viewBox="0 0 30 40"><path d="M15 0C7 0 1 6 1 14c0 10 14 26 14 26s14-16 14-26C29 6 23 0 15 0z" fill="' + (color || '#8b5cf6') + '" stroke="#fff" stroke-width="2"/><circle cx="15" cy="14" r="5" fill="#fff"/></svg>' });
  }
  function esc(s) { var d = document.createElement('div'); d.textContent = s == null ? '' : s; return d.innerHTML; }

  /* data-map='{"markers":[{"lat","lng","title","url"}],"route":true}' */
  document.querySelectorAll('[data-map]').forEach(function (el) {
    var cfg = {}; try { cfg = JSON.parse(el.getAttribute('data-map')); } catch (e) { }
    var ms = (cfg.markers || []).filter(function (m) { return m.lat != null && m.lng != null; });
    var map = L.map(el, { scrollWheelZoom: false }).setView(ms.length ? [ms[0].lat, ms[0].lng] : [-1.2921, 36.8219], ms.length ? 13 : 6);
    tiles(map); var pts = [];
    ms.forEach(function (m, i) {
      var mk = L.marker([m.lat, m.lng], { icon: pin(m.color || cfg.color) }).addTo(map);
      mk.bindPopup('<b>' + esc(m.title) + '</b>' + (m.sub ? '<br>' + esc(m.sub) : '') + (m.url ? '<br><a href="' + m.url + '">Visit →</a>' : ''));
      if (i === 0 && cfg.open) mk.openPopup(); pts.push([m.lat, m.lng]);
    });
    if (cfg.route && pts.length > 1) L.polyline(pts, { color: cfg.color || '#8b5cf6', weight: 4, dashArray: '8 8' }).addTo(map);
    if (pts.length > 1) map.fitBounds(pts, { padding: [40, 40] });
    el.addEventListener('click', function () { map.scrollWheelZoom.enable(); });
    setTimeout(function () { map.invalidateSize(); }, 300);
  });

  /* data-picker="lat_input_id,lng_input_id" : click or drag to choose a spot */
  document.querySelectorAll('[data-picker]').forEach(function (el) {
    var ids = el.getAttribute('data-picker').split(','), la = document.getElementById(ids[0]), lo = document.getElementById(ids[1]);
    var lat = parseFloat(la.value), lng = parseFloat(lo.value), has = !isNaN(lat) && !isNaN(lng);
    var map = L.map(el).setView(has ? [lat, lng] : [-1.2921, 36.8219], has ? 15 : 11); tiles(map);
    var mk = L.marker(has ? [lat, lng] : map.getCenter(), { draggable: true, icon: pin() }).addTo(map);
    function set(p) { la.value = p.lat.toFixed(6); lo.value = p.lng.toFixed(6); }
    if (has) set({ lat: lat, lng: lng });
    mk.on('dragend', function () { set(mk.getLatLng()); });
    map.on('click', function (e) { mk.setLatLng(e.latlng); set(e.latlng); });
    var btn = document.querySelector('[data-locate="' + el.id + '"]');
    if (btn) btn.addEventListener('click', function () {
      if (!navigator.geolocation) return N.toast && N.toast('Location is not available in this browser.', 'error');
      navigator.geolocation.getCurrentPosition(function (p) { var ll = L.latLng(p.coords.latitude, p.coords.longitude); mk.setLatLng(ll); map.setView(ll, 16); set(ll); }, function () { N.toast && N.toast('Could not get your location. Click the map instead.', 'warning'); });
    });
    setTimeout(function () { map.invalidateSize(); }, 300);
  });
})();
