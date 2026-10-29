/* Order journey map: shop pins, event pins, delivery pin, connected by a dashed line */
(function () {
  var el = document.getElementById('trackmap'); if (!el || !window.L) return;
  var pts = window.NYOTA_POINTS || [];
  if (!pts.length) { el.outerHTML = '<div class="empty" style="padding:2rem">No location updates yet. They appear here as your order moves.</div>'; return; }
  var map = L.map(el, { scrollWheelZoom: false }); L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', { maxZoom: 19, attribution: '&copy; OpenStreetMap contributors' }).addTo(map);
  var col = { shop: '#f5b324', event: '#8b5cf6', dest: '#10b981' }, line = [];
  pts.forEach(function (p) {
    L.circleMarker([p.lat, p.lng], { radius: p.kind === 'event' ? 7 : 10, color: '#fff', weight: 2, fillColor: col[p.kind] || '#8b5cf6', fillOpacity: 1 }).addTo(map).bindPopup(p.label);
    line.push([p.lat, p.lng]);
  });
  if (line.length > 1) { L.polyline(line, { color: '#8b5cf6', weight: 3, dashArray: '6 8' }).addTo(map); map.fitBounds(line, { padding: [50, 50] }); } else map.setView(line[0], 14);
  setTimeout(function () { map.invalidateSize(); }, 300);
})();
