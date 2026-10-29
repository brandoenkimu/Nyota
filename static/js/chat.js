/* Nyota chat client: WebSocket with HTTP polling fallback, reply / react / delete / emoji */
(function () {
  'use strict';
  var root = document.getElementById('chat-app'); if (!root) return;
  var N = window.Nyota, conv = +root.dataset.conv, me = +root.dataset.me, moderate = root.dataset.moderate === '1';
  var box = document.getElementById('msgs'), ta = document.getElementById('compose'), sendBtn = document.getElementById('send');
  var replyBar = document.getElementById('reply-bar'), emojiPop = document.getElementById('emoji-pop'), dot = document.getElementById('conn');
  var EMOJI = '😀 😁 😂 🤣 😊 😍 😘 😎 🤔 😢 😭 😡 👍 👎 👏 🙏 🙌 💪 🔥 ✨ ❤️ 💔 🎉 🎁 📦 🚚 ✅ ❌ ⭐ 💯 👀 😅 😉 🥳 🤝 💬 📍 💳 📱 🛒'.split(' ');
  var QUICK = ['👍', '❤️', '😂', '😮', '😢', '🙏'];
  var ws, seen = {}, last = 0, replyTo = null, retry = 0, poll = null, lastDay = '';

  function el(t, c, h) { var e = document.createElement(t); if (c) e.className = c; if (h != null) e.textContent = h; return e; }
  function fmt(iso) { return new Date(iso).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }); }
  function dayLabel(iso) {
    var d = new Date(iso), t = new Date(), y = new Date(Date.now() - 864e5);
    if (d.toDateString() === t.toDateString()) return 'Today'; if (d.toDateString() === y.toDateString()) return 'Yesterday';
    return d.toLocaleDateString([], { day: 'numeric', month: 'short', year: 'numeric' });
  }
  function atBottom() { return box.scrollHeight - box.scrollTop - box.clientHeight < 140; }
  function toBottom() { box.scrollTop = box.scrollHeight; }

  function render(m, prepend) {
    var emp = box.querySelector('.chat-empty'); if (emp) emp.remove();
    var old = seen[m.id] || (m.client_id && seen['c' + m.client_id]);
    var mine = m.sender.id === me, node = el('div', 'msg ' + (mine ? 'me' : 'them') + (m.deleted ? ' deleted' : ''));
    node.dataset.id = m.id;
    if (!mine) node.appendChild(el('div', 'who', m.sender.name + (m.sender.role && m.sender.role !== 'customer' ? ' · ' + m.sender.role.replace('_', ' ') : '')));
    var b = el('div', 'bubble');
    if (m.reply_to) b.appendChild(el('div', 'quote', m.reply_to.sender + ': ' + (m.reply_to.deleted ? 'message deleted' : m.reply_to.body)));
    b.appendChild(document.createTextNode(m.deleted ? 'This message was deleted' : m.body)); node.appendChild(b);
    var rx = el('div', 'reacts'); drawReacts(rx, m); node.appendChild(rx);
    node.appendChild(el('div', 'time', fmt(m.created_at)));
    if (!m.deleted && m.id) {
      var tools = el('div', 'msg-tools');
      [['↩', 'Reply', function () { setReply(m); }], ['☺', 'React', function (e) { reactPicker(m, e.currentTarget); }]].forEach(function (t) { var bt = el('button', null, t[0]); bt.title = t[1]; bt.type = 'button'; bt.onclick = t[2]; tools.appendChild(bt); });
      if (mine || moderate) { var d = el('button', null, '🗑'); d.title = 'Delete'; d.type = 'button'; d.onclick = function () { if (confirm('Delete this message for everyone?')) del(m.id); }; tools.appendChild(d); }
      node.appendChild(tools);
    }
    node._m = m;
    if (old && old.parentNode) { old.parentNode.replaceChild(node, old); }
    else {
      var day = dayLabel(m.created_at);
      if (!prepend && day !== lastDay) { box.appendChild(el('div', 'day-sep', day)); lastDay = day; }
      var stick = atBottom() || mine; box.appendChild(node); if (stick) toBottom();
    }
    seen[m.id] = node; if (m.client_id) seen['c' + m.client_id] = node; if (m.id > last) last = m.id;
  }
  function drawReacts(rx, m) {
    rx.innerHTML = '';
    (m.reactions || []).forEach(function (r) {
      var c = el('span', 'react-chip' + (r.users.indexOf(me) > -1 ? ' mine' : ''), r.emoji + ' ' + r.users.length);
      c.onclick = function () { react(m.id, r.emoji); }; rx.appendChild(c);
    });
  }
  function reactPicker(m, anchor) {
    closePops(); var p = el('div', 'react-pop'); QUICK.forEach(function (e) { var b = el('button', null, e); b.type = 'button'; b.onclick = function () { react(m.id, e); closePops(); }; p.appendChild(b); });
    var r = anchor.getBoundingClientRect(), br = root.getBoundingClientRect(); p.style.left = Math.max(8, Math.min(r.left - br.left - 40, br.width - 290)) + 'px'; p.style.top = (r.top - br.top - 50) + 'px'; root.appendChild(p);
    setTimeout(function () { document.addEventListener('click', closePops, { once: true }); }, 0);
  }
  function closePops() { Array.prototype.forEach.call(root.querySelectorAll('.react-pop'), function (p) { p.remove(); }); }

  function setReply(m) { replyTo = m; replyBar.classList.add('on'); replyBar.querySelector('span').textContent = 'Replying to ' + m.sender.name + ': ' + (m.body || '').slice(0, 80); ta.focus(); }
  function clearReply() { replyTo = null; replyBar.classList.remove('on'); }
  document.getElementById('reply-x').onclick = clearReply;

  /* ---- network */
  function wsSend(o) { if (ws && ws.readyState === 1) { ws.send(JSON.stringify(o)); return true; } return false; }
  function api(path, body) { return N.post('/chat/api/' + path, body, true); }
  function connect() {
    var proto = location.protocol === 'https:' ? 'wss://' : 'ws://';
    try { ws = new WebSocket(proto + location.host + '/ws/chat/' + conv + '/'); } catch (e) { startPoll(); return; }
    ws.onopen = function () { retry = 0; dot.classList.add('on'); stopPoll(); catchUp(); wsSend({ type: 'read' }); };
    ws.onclose = function () { dot.classList.remove('on'); startPoll(); setTimeout(connect, Math.min(15000, 1000 * Math.pow(2, retry++))); };
    ws.onmessage = function (ev) {
      var d = JSON.parse(ev.data);
      if (d.type === 'message') { render(d.data); if (d.data.sender.id !== me) wsSend({ type: 'read' }); }
      else if (d.type === 'deleted') { var n = seen[d.data.id]; if (n) { var m = n._m; m.deleted = true; m.body = ''; render(m); } }
      else if (d.type === 'reactions') { var n2 = seen[d.data.id]; if (n2) { n2._m.reactions = d.data.reactions; drawReacts(n2.querySelector('.reacts'), n2._m); } }
      else if (d.type === 'error') { N.toast(d.message, 'error'); var f = d.client_id && seen['c' + d.client_id]; if (f) f.remove(); }
    };
  }
  function catchUp() { fetch('/chat/api/' + conv + '/messages/?after=' + last, { credentials: 'same-origin' }).then(function (r) { return r.json(); }).then(function (d) { (d.messages || []).forEach(function (m) { render(m); }); }); }
  function startPoll() { if (!poll) poll = setInterval(catchUp, 4000); }
  function stopPoll() { clearInterval(poll); poll = null; }
  function react(id, emoji) { if (!wsSend({ type: 'react', message_id: id, emoji: emoji })) api('message/' + id + '/react/', { emoji: emoji }).then(catchUp); }
  function del(id) { if (!wsSend({ type: 'delete', message_id: id })) api('message/' + id + '/delete/', {}).then(function (d) { if (d.ok) { var n = seen[id]; if (n) { n._m.deleted = true; render(n._m); } } else N.toast(d.message || 'Could not delete', 'error'); }); }

  function send() {
    var body = ta.value.trim(); if (!body) return;
    var cid = (window.crypto && crypto.randomUUID) ? crypto.randomUUID() : 'x' + Date.now() + Math.random().toString(16).slice(2);
    var rid = replyTo ? replyTo.id : null;
    render({ id: 0, client_id: cid, sender: { id: me, name: 'You', role: '' }, body: body, deleted: false, reply_to: replyTo ? { id: replyTo.id, sender: replyTo.sender.name, body: replyTo.body, deleted: false } : null, reactions: [], created_at: new Date().toISOString() });
    ta.value = ''; ta.style.height = 'auto'; clearReply();
    if (!wsSend({ type: 'send', body: body, reply_to: rid, client_id: cid })) {
      api(conv + '/send/', { body: body, reply_to: rid, client_id: cid }).then(function (d) { if (d.ok) render(d.message); else { N.toast(d.message || 'Could not send', 'error'); var n = seen['c' + cid]; if (n) n.remove(); } });
    }
  }
  sendBtn.onclick = send;
  ta.addEventListener('keydown', function (e) { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); send(); } });
  ta.addEventListener('input', function () { ta.style.height = 'auto'; ta.style.height = Math.min(140, ta.scrollHeight) + 'px'; });

  /* emoji picker */
  EMOJI.forEach(function (e) { var b = el('button', null, e); b.type = 'button'; b.onclick = function () { var p = ta.selectionStart || ta.value.length; ta.value = ta.value.slice(0, p) + e + ta.value.slice(p); ta.focus(); ta.selectionStart = ta.selectionEnd = p + e.length; }; emojiPop.appendChild(b); });
  document.getElementById('emoji-btn').onclick = function (e) { e.stopPropagation(); emojiPop.classList.toggle('on'); };
  document.addEventListener('click', function (e) { if (!e.target.closest('#emoji-pop')) emojiPop.classList.remove('on'); });

  /* boot: load history then connect */
  fetch('/chat/api/' + conv + '/messages/', { credentials: 'same-origin' }).then(function (r) { return r.json(); }).then(function (d) {
    (d.messages || []).forEach(function (m) { render(m); }); toBottom(); connect();
    if (!d.messages.length) box.appendChild(el('div', 'chat-empty', 'Say hello 👋'));
  }).catch(function () { startPoll(); });
})();
