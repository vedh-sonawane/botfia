/* Botfia, the shared-device client.
   Polls the Pi for the current screen and renders it. Private turns use
   press-and-hold so a screen only shows while it's held; a neutral hand-off
   sits between players. Night mode dims the screen to near-black. */

'use strict';

// ---------- tiny DOM helper ----------
function h(tag, props = {}, children = []) {
  const e = document.createElement(tag);
  for (const k in props) {
    if (k === 'class') e.className = props[k];
    else if (k === 'html') e.innerHTML = props[k];
    else if (k.startsWith('on')) e.addEventListener(k.slice(2).toLowerCase(), props[k]);
    else if (props[k] === true) e.setAttribute(k, k.startsWith('aria-') ? 'true' : '');
    else if (props[k] !== false && props[k] != null) e.setAttribute(k, props[k]);
  }
  for (const c of [].concat(children)) if (c != null) e.append(c.nodeType ? c : document.createTextNode(c));
  return e;
}
const $ = (s) => document.querySelector(s);
const screenEl = () => $('#screen');

// ---------- api ----------
async function get(path) { const r = await fetch(path, { cache: 'no-store' }); return r.json(); }
async function post(path, body) {
  const r = await fetch(path, { method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: body ? JSON.stringify(body) : null });
  const json = await r.json();
  // Render straight from the action's response, one round-trip, no waiting on
  // a second fetch, so the screen changes the instant the Pi replies.
  if (json && json.device && json.state) render(json.device, json.state);
  else setTimeout(() => loop(), 50);
  return json;
}
// Fire-and-forget POST with no screen refresh, for the volume slider, so
// dragging it doesn't thrash the UI on every step.
async function postQuiet(path, body) {
  try {
    await fetch(path, { method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: body ? JSON.stringify(body) : null });
  } catch (e) {}
}

// ---------- device niceties ----------
function haptic(ms = 12) { try { navigator.vibrate && navigator.vibrate(ms); } catch (e) {} }
let wakeLock = null;
async function keepAwake() {
  try { if ('wakeLock' in navigator) wakeLock = await navigator.wakeLock.request('screen'); } catch (e) {}
}
document.addEventListener('visibilitychange', () => { if (document.visibilityState === 'visible') keepAwake(); });

function toast(msg) {
  const t = $('#toast'); t.textContent = msg; t.hidden = false;
  clearTimeout(toast._t); toast._t = setTimeout(() => { t.hidden = true; }, 1600);
}

// ---------- press-and-hold ring ----------
function holdRing(label, onComplete, holdMs = 650) {
  const circ = 594;
  const fill = h('circle', { class: 'fill', cx: 98, cy: 98, r: 93, fill: 'none', 'stroke-width': 6 });
  const svg = h('svg', { viewBox: '0 0 196 196', width: 196, height: 196 },
    [h('circle', { class: 'track', cx: 98, cy: 98, r: 93, fill: 'none', 'stroke-width': 6 }), fill]);
  const lab = h('span', { class: 'label' }, label);
  const wrap = h('div', { class: 'hold' }, [svg, lab]);
  let raf, start = 0, done = false;
  const step = (t) => {
    if (!start) start = t;
    const p = Math.min(1, (t - start) / holdMs);
    fill.style.strokeDashoffset = circ * (1 - p);
    if (p >= 1 && !done) { done = true; haptic(24); wrap.classList.remove('active'); wrap.classList.add('done'); onComplete(); return; }
    raf = requestAnimationFrame(step);
  };
  const begin = (ev) => { ev.preventDefault(); if (done) return; wrap.classList.add('active'); haptic(8); start = 0; raf = requestAnimationFrame(step); };
  const end = () => { if (done) return; cancelAnimationFrame(raf); wrap.classList.remove('active'); fill.style.strokeDashoffset = circ; };
  wrap.addEventListener('pointerdown', begin);
  wrap.addEventListener('pointerup', end);
  wrap.addEventListener('pointerleave', end);
  wrap.addEventListener('pointercancel', end);
  return wrap;
}

// press-and-hold that reveals content while held, hides on release
function holdReveal(closedLabel, buildOpen) {
  const inner = h('div', {});
  const closed = () => { inner.innerHTML = ''; inner.append(h('div', { class: 'center muted', style: 'padding:40px 0;font-size:15px' }, closedLabel)); };
  const open = () => { inner.innerHTML = ''; inner.append(buildOpen()); haptic(10); };
  closed();
  const target = h('div', { class: 'role-card', style: 'cursor:pointer' }, inner);
  target.addEventListener('pointerdown', (e) => { e.preventDefault(); open(); });
  target.addEventListener('pointerup', closed);
  target.addEventListener('pointerleave', closed);
  target.addEventListener('pointercancel', closed);
  return target;
}

// ---------- screen state ----------
let last = { sig: '', data: null };
let selected = null;
let dayTimer = null;

function sigOf(d, s) {
  return [s.phase, d.screen, d.name || '', d.stage || '', d.night ? 'n' : '',
    (d.result ? 'r' : ''), (s.winner || '')].join(':');
}

function setNight(on) { document.body.classList.toggle('night', !!on); }

function render(d, s) {
  const sig = sigOf(d, s);
  const dot = $('#status-dot'); dot.className = 'dot ok';
  // night theme: during the actual night turns (room is dark)
  setNight(d.night || (s.phase === 'night'));
  if (sig === last.sig) { tick(d, s); return; }
  last = { sig, data: d };
  selected = null;
  const root = screenEl(); root.innerHTML = '';
  const view = buildScreen(d, s);
  view.classList.add('view');
  root.append(view);
}

function tick(d, s) { /* dynamic updates handled per-screen (countdown) */ }

// ---------- screens ----------
function buildScreen(d, s) {
  switch (d.screen) {
    case 'lobby': return lobby(s);
    case 'handoff': return handoff(d);
    case 'reveal': return reveal(d);
    case 'ready_night': return readyNight();
    case 'night': return nightTurn(d);
    case 'morning': return morning(d);
    case 'day': return d.stage === 'post_vote' ? postVote(d) : discussion(d, s);
    case 'vote': return voteSecret(d);
    case 'vote_open': return voteOpen(d);
    case 'end': return endScreen(d);
    default: return h('div', { class: 'center muted' }, 'Botfia');
  }
}

// --- lobby / setup ---
// Setup persists to localStorage so a refresh (or the auto-update reload) never
// loses the typed names or chosen options.
function loadNames() {
  try { const v = JSON.parse(localStorage.getItem('botfia_names')); if (Array.isArray(v) && v.length >= 4) return v; } catch (e) {}
  return ['', '', '', '', ''];
}
function saveNames(names) { try { localStorage.setItem('botfia_names', JSON.stringify(names)); } catch (e) {} }
function loadOpts() {
  const def = { voting_style: 'secret', discussion_seconds: 180, reveal_roles_on_death: true, include_jester: false };
  try { const v = JSON.parse(localStorage.getItem('botfia_opts')); if (v && typeof v === 'object') return Object.assign(def, v); } catch (e) {}
  return def;
}
function saveOpts(opts) { try { localStorage.setItem('botfia_opts', JSON.stringify(opts)); } catch (e) {} }

function lobby(s) {
  const names = (lobby._names ||= loadNames());
  const opts = (lobby._opts ||= loadOpts());
  const wrap = h('div', {});
  wrap.append(h('p', { class: 'kicker' }, 'New game'),
    h('h1', { class: 'display serif' }, 'Who is playing?'),
    h('p', { class: 'sub' }, 'Enter names in the order the device will be passed.'));

  const list = h('div', { class: 'stack tight', style: 'margin:22px 0' });
  function drawList() {
    list.innerHTML = '';
    names.forEach((n, i) => {
      const inp = h('input', { class: 'input', placeholder: `Player ${i + 1}`, value: n, maxlength: 20,
        oninput: (e) => { names[i] = e.target.value; saveNames(names); } });
      const x = h('button', { class: 'x', onclick: () => { names.splice(i, 1); saveNames(names); drawList(); } }, '×');
      list.append(h('div', { class: 'player-row' }, [h('span', { class: 'idx' }, i + 1), inp, names.length > 4 ? x : h('span', { style: 'width:44px' })]));
    });
  }
  drawList();
  const add = h('button', { class: 'btn quiet', onclick: () => { if (names.length < 30) { names.push(''); saveNames(names); drawList(); } } }, '+  Add player');

  // options
  const voteSeg = h('div', { class: 'seg' }, ['secret', 'open'].map((v) =>
    h('button', { 'aria-pressed': opts.voting_style === v ? 'true' : 'false', onclick: () => { opts.voting_style = v; saveOpts(opts); voteSeg.querySelectorAll('button').forEach((b, k) => b.setAttribute('aria-pressed', ['secret', 'open'][k] === v ? 'true' : 'false')); } }, v[0].toUpperCase() + v.slice(1))));
  const timeSeg = h('div', { class: 'seg' }, [[120, '2m'], [180, '3m'], [300, '5m']].map(([v, t]) =>
    h('button', { 'aria-pressed': opts.discussion_seconds === v ? 'true' : 'false', onclick: () => { opts.discussion_seconds = v; saveOpts(opts); timeSeg.querySelectorAll('button').forEach((b, k) => b.setAttribute('aria-pressed', [120, 180, 300][k] === v ? 'true' : 'false')); } }, t)));
  const jesterSeg = h('div', { class: 'seg' }, [['off', 'Off'], ['on', 'On']].map(([v, t]) =>
    h('button', { 'aria-pressed': (opts.include_jester ? 'on' : 'off') === v ? 'true' : 'false', onclick: () => { opts.include_jester = (v === 'on'); saveOpts(opts); jesterSeg.querySelectorAll('button').forEach((b, k) => b.setAttribute('aria-pressed', ['off', 'on'][k] === v ? 'true' : 'false')); } }, t)));

  const start = h('button', { class: 'btn primary', style: 'margin-top:12px', onclick: async () => {
    const clean = names.map((n) => n.trim()).filter(Boolean);
    if (clean.length < 4) { toast('Need at least 4 players.'); return; }
    const r = await post('/api/configure', { names: clean, options: opts });
    if (r.error) { toast(r.error); return; }
    await post('/api/start'); keepAwake();
  } }, 'Start');

  wrap.append(list, add,
    h('div', { class: 'row' }, [h('span', { class: 'lab' }, 'Voting'), voteSeg]),
    h('div', { class: 'row' }, [h('span', { class: 'lab' }, 'Discussion'), timeSeg]),
    h('div', { class: 'row' }, [h('span', { class: 'lab' }, 'Jester'), jesterSeg]),
    h('p', { class: 'sub', style: 'margin-top:-6px;font-size:13px' }, 'Jester: one player secretly wins if the town votes them out.'),
    start);
  return wrap;
}

// --- hand-off ---
function handoff(d) {
  const ring = holdRing('hold to begin', async () => { await post('/api/begin_turn'); }, 620);
  return h('div', { class: 'center' }, [
    h('div', { class: 'spacer' }),
    h('p', { class: 'kicker' }, 'Pass the device'),
    h('h1', { class: 'display serif', style: 'margin-bottom:6px' }, d.next_name),
    h('div', { class: 'hold-wrap' }, ring),
    h('p', { class: 'hidden-note' }, 'Only ' + d.next_name + ' should look.'),
    h('div', { class: 'spacer' }),
  ]);
}

// --- reveal role ---
function reveal(d) {
  const card = holdReveal('Hold to see your role', () => {
    const inner = h('div', {});
    inner.append(h('p', { class: 'role-name serif' }, d.role),
      h('p', { class: 'role-blurb' }, d.blurb || ''));
    if (d.teammates && d.teammates.length) {
      inner.append(h('div', { class: 'team' }, [h('span', {}, 'With you'), d.teammates.join(', ')]));
    } else if (d.teammates) {
      inner.append(h('div', { class: 'team muted' }, [h('span', {}, 'Mafia'), 'You work alone.']));
    }
    return inner;
  });
  const done = timedDone('Done', () => post('/api/finish_turn'), d.min_turn_seconds);
  return h('div', {}, [
    h('div', { class: 'spacer' }),
    h('p', { class: 'kicker center' }, 'Your role'),
    card,
    h('p', { class: 'hidden-note center' }, 'Let go to hide it.'),
    h('div', { class: 'spacer' }), done,
  ]);
}

function readyNight() {
  return h('div', { class: 'center' }, [
    h('div', { class: 'spacer' }),
    h('p', { class: 'kicker' }, 'Ready'),
    h('h1', { class: 'display serif' }, 'Everyone has their role.'),
    h('p', { class: 'sub' }, 'Place the device down. The night is about to begin.'),
    h('div', { class: 'spacer' }),
    h('button', { class: 'btn primary', onclick: () => post('/api/begin_night') }, 'Begin night'),
  ]);
}

// --- night action ---
function nightTurn(d) {
  const wrap = h('div', {});
  wrap.append(h('p', { class: 'kicker' }, 'Night'), h('h2', { class: 'lead serif' }, d.prompt));

  if (d.kind === 'detective' && d.result) {
    const red = !!d.result.suspicious;
    const card = holdReveal('Hold to see the result', () =>
      h('div', { class: 'verdict ' + (red ? 'red' : 'green') }, [
        h('div', { class: 'verdict-dot' }),
        h('p', { class: 'verdict-name serif' }, d.result.name),
        h('p', { class: 'verdict-word' }, red ? 'Suspicious' : 'Clear'),
      ]));
    wrap.append(h('div', { style: 'margin:22px 0' }, card));
  } else {
    const list = optionList(d.options, (seat) => post('/api/night/submit', { target: seat }), d);
    wrap.append(list);
  }
  wrap.append(h('div', { class: 'spacer' }), timedDone('Done', () => post('/api/finish_turn'), d.min_turn_seconds));
  return wrap;
}

// --- morning ---
function morning(d) {
  return h('div', { class: 'center' }, [
    h('div', { class: 'spacer' }),
    h('p', { class: 'kicker' }, 'Morning'),
    h('h1', { class: 'display serif' }, d.died ? d.died + ' did not wake up.' : 'Everyone is still here.'),
    h('div', { class: 'spacer' }),
    h('button', { class: 'btn primary', onclick: () => post('/api/morning/continue') }, 'Continue'),
  ]);
}

// --- day discussion (countdown) ---
function discussion(d, s) {
  const total = d.discussion_seconds || 180;
  const key = 'disc:' + s.day_number;
  if (dayTimer?.key !== key) dayTimer = { key, remaining: total, paused: false };
  const timeEl = h('div', { class: 'time serif' }, fmt(dayTimer.remaining));
  const fillEl = h('div', { class: 'bar-fill' });
  const voteBtn = h('button', { class: 'btn primary', onclick: () => post('/api/start_vote') },
    s.voting_style === 'open' ? 'Vote by hands' : 'Start vote');
  clearInterval(discussion._iv);
  discussion._iv = setInterval(() => {
    if (!document.body.contains(timeEl)) { clearInterval(discussion._iv); return; }
    if (dayTimer.paused) return;
    dayTimer.remaining = Math.max(0, dayTimer.remaining - 1);
    timeEl.textContent = fmt(dayTimer.remaining);
    timeEl.classList.toggle('low', dayTimer.remaining <= 15);
    fillEl.style.width = (100 * dayTimer.remaining / total) + '%';
    if (dayTimer.remaining === 0) { haptic(40); }
  }, 1000);
  discussion._ctl = dayTimer;
  const alive = d.alive || (s.players || []).filter((p) => p.alive).map((p) => p.name);
  const chips = h('div', { class: 'chips' }, alive.map((n) => h('span', { class: 'chip' }, n)));
  return h('div', {}, [
    h('div', { class: 'spacer' }),
    h('p', { class: 'kicker center' }, 'Day ' + s.day_number + ', ' + s.alive_count + ' left'),
    h('div', { class: 'count' }, [timeEl, h('div', { class: 'bar-track' }, fillEl)]),
    h('h2', { class: 'lead serif center', style: 'margin:10px 0 4px' }, d.prompt || 'Talk it out. Who is lying?'),
    h('p', { class: 'sub center' }, d.line || 'Make your case. Accuse, defend, decide.'),
    chips,
    h('div', { class: 'spacer' }), voteBtn,
  ]);
}

function postVote(d) {
  return h('div', { class: 'center' }, [
    h('div', { class: 'spacer' }),
    h('p', { class: 'kicker' }, 'The vote'),
    h('h1', { class: 'display serif' },
      (d.last_vote && d.last_vote.out) ? d.last_vote.out + ' was voted out.'
        : (d.last_vote && d.last_vote.tie) ? 'The vote was tied. No one leaves.'
        : 'No one was voted out.'),
    h('div', { class: 'spacer' }),
    h('button', { class: 'btn primary', onclick: () => post('/api/day/continue') }, 'Begin night'),
  ]);
}

// --- vote (secret) ---
function voteSecret(d) {
  const wrap = h('div', {});
  wrap.append(h('p', { class: 'kicker' }, 'Vote'), h('h2', { class: 'lead serif' }, 'Vote someone out.'));
  wrap.append(optionList(d.options, (seat) => { selected = seat; }, d));
  const confirm = timedDone('Confirm vote', async () => {
    await post('/api/vote/submit', { target: selected });
    await post('/api/finish_turn');
  }, d.min_turn_seconds, () => selected != null);
  const abstain = h('button', { class: 'btn ghost', onclick: async () => {
    await post('/api/vote/submit', { target: null }); await post('/api/finish_turn');
  } }, 'Abstain');
  wrap.append(h('div', { class: 'spacer' }), h('div', { class: 'stack tight' }, [confirm, abstain]));
  return wrap;
}

// --- vote (open, host enters) ---
function voteOpen(d) {
  const wrap = h('div', {});
  wrap.append(h('p', { class: 'kicker' }, 'Open vote'),
    h('h2', { class: 'lead serif' }, 'Who did the table vote out?'));
  wrap.append(optionList(d.options, (seat) => { selected = seat; }, d));
  wrap.append(h('div', { class: 'spacer' }), h('div', { class: 'stack tight' }, [
    h('button', { class: 'btn primary', onclick: () => post('/api/vote/open', { target: selected }) }, 'Confirm'),
    h('button', { class: 'btn ghost', onclick: () => post('/api/vote/open', { target: null }) }, 'No one'),
  ]));
  return wrap;
}

// --- end ---
function endScreen(d) {
  const list = h('div', { class: 'reveal-list' }, (d.reveal || []).map((p, i) =>
    h('div', { class: 'reveal-row', style: 'animation-delay:' + (i * 0.05).toFixed(3) + 's' },
      [h('span', {}, p.name), h('span', { class: 'r' }, p.role)])));
  return h('div', {}, [
    h('div', { class: 'spacer' }),
    h('p', { class: 'kicker center' }, 'Game over'),
    h('h1', { class: 'result serif center' }, d.winner === 'mafia' ? 'The mafia wins.' : d.winner === 'jester' ? 'The jester wins.' : d.winner === 'ended' ? 'Game ended.' : 'The town wins.'),
    list,
    h('div', { class: 'spacer' }),
    h('button', { class: 'btn primary', onclick: () => { lobby._names = null; lobby._opts = null; post('/api/restart'); } }, 'New game'),
  ]);
}

// ---------- shared pieces ----------
function optionList(options, onPick, d) {
  const el = h('div', { class: 'options' });
  (options || []).forEach((o, i) => {
    const disabled = (d && d.blocked_seat === o.seat);
    const preselected = (d && d.current_pick === o.seat);
    if (preselected) selected = o.seat;
    const row = h('button', { class: 'option' + (disabled ? ' disabled' : ''),
      style: 'animation-delay:' + (i * 0.035).toFixed(3) + 's',
      'aria-selected': preselected ? 'true' : 'false', onclick: () => {
        el.querySelectorAll('.option').forEach((x) => x.setAttribute('aria-selected', 'false'));
        row.setAttribute('aria-selected', 'true'); haptic(10);
        selected = o.seat; onPick && onPick(o.seat);
      } }, [h('span', {}, o.name), h('span', { class: 'mark' })]);
    el.append(row);
  });
  return el;
}

// a Done button that only enables after the minimum turn time (and an optional
// extra condition), so every turn takes the same minimum time.
function timedDone(label, action, minSeconds, extraOk) {
  const btn = h('button', { class: 'btn primary', disabled: true, onclick: async () => {
    const r = await action(); if (r && r.ok === false) toast('A moment longer.');
  } }, label);
  const started = performance.now();
  const update = () => {
    if (!document.body.contains(btn)) return;
    const elapsed = (performance.now() - started) / 1000;
    const ok = elapsed >= (minSeconds || 0) && (!extraOk || extraOk());
    btn.disabled = !ok;
    requestAnimationFrame(update);
  };
  requestAnimationFrame(update);
  return btn;
}

function fmt(sec) { const m = Math.floor(sec / 60), s = sec % 60; return m + ':' + String(s).padStart(2, '0'); }

// ---------- host sheet (hidden behind a deliberate long-press on the wordmark) ----------
let hostMusicOn = null, hostVol = null;   // client-side music-on + speaker-volume state for the host sheet
(function hostControls() {
  const brand = $('#brand'); let t;
  const open = () => openHostSheet();
  brand.addEventListener('pointerdown', () => { t = setTimeout(open, 750); });
  brand.addEventListener('pointerup', () => clearTimeout(t));
  brand.addEventListener('pointerleave', () => clearTimeout(t));
})();

async function openHostSheet() {
  haptic(20);
  const s = last.data ? await get('/api/state') : {};
  const hl = s.health || {};
  const sheet = $('#host-sheet');
  const hrow = (name, ok, extra) => h('div', { class: 'h' }, [h('b', {}, name),
    h('span', { class: 's' + (ok ? ' ok' : '') }, ok ? (extra || 'ok') : 'off')]);
  sheet.innerHTML = '';
  sheet.hidden = false;
  // Music on/off + volume. Track locally so the control responds instantly
  // (health only refreshes every few seconds).
  const m = hl.music || {};
  if (hostMusicOn === null) hostMusicOn = (m.enabled !== false);
  if (hostVol === null) hostVol = (m.volume != null ? m.volume : 0.35);
  const musicRow = h('div', { class: 'music' }, [
    h('div', { class: 'music-head' }, [
      h('b', {}, 'Music'),
      h('button', {
        class: 'toggle' + (hostMusicOn ? ' on' : ''),
        onclick: () => { hostMusicOn = !hostMusicOn; post('/api/host/music', { on: hostMusicOn }); openHostSheet(); },
      }, hostMusicOn ? 'On' : 'Off'),
    ]),
  ]);
  if (hostMusicOn) {
    musicRow.append(
      h('div', { class: 'music-head', style: 'margin-top:2px' }, [h('b', {}, 'Music volume')]),
      h('input', {
        type: 'range', min: '0', max: '100', step: '1', class: 'vol',
        value: String(Math.round(hostVol * 100)), 'aria-label': 'Music volume',
        onchange: (e) => { hostVol = Number(e.target.value) / 100; postQuiet('/api/host/music_volume', { volume: hostVol }); },
      }),
    );
  }
  sheet.append(
    h('h3', {}, 'Host'),
    h('div', { class: 'health' }, [
      hrow('ESP32', hl.esp32?.online, hl.esp32?.dark ? 'dark' : 'lit'),
      hrow('Speaker', hl.speaker?.connected, hl.speaker?.name),
      hrow('Claude', hl.claude?.enabled),
      hrow('Voice', hl.tts?.available),
      hrow('Light', !!hl.light),
    ]),
    musicRow,
    h('div', { class: 'grid' }, [
      hbtn('Pause', () => { if (discussion._ctl) { discussion._ctl.paused = !discussion._ctl.paused; toast(discussion._ctl.paused ? 'Paused' : 'Running'); } }),
      hbtn('+30s', () => { if (discussion._ctl) { discussion._ctl.remaining += 30; toast('+30 seconds'); } }),
      hbtn('Repeat line', () => { post('/api/host/repeat'); toast('Repeating'); }),
      hbtn('Light test', () => post('/api/host/light_test')),
      hbtn('Skip to vote', () => post('/api/start_vote')),
      hbtn('End game', () => { if (confirm('End the game now and reveal every role?')) post('/api/host/end'); }),
      hbtn('Restart game', () => { if (confirm('Restart the game?')) post('/api/restart'); }),
      hbtn('Close', () => { sheet.hidden = true; }),
    ]),
  );
  const closeOnOutside = (e) => { if (!sheet.contains(e.target) && e.target.id !== 'brand') { sheet.hidden = true; document.removeEventListener('pointerdown', closeOnOutside); } };
  setTimeout(() => document.addEventListener('pointerdown', closeOnOutside), 50);
}
function hbtn(label, fn) { return h('button', { class: 'btn', onclick: () => { fn(); } }, label); }

// ---------- splash + reconnect ----------
function splash() {
  screenEl().innerHTML = '';
  screenEl().append(h('div', { class: 'splash' }, h('div', { class: 'mark' }, 'BOTFIA')));
}
function setReconnect(on) {
  const o = document.getElementById('reconnect');
  if (on && !o) document.body.append(h('div', { id: 'reconnect', class: 'reconnect' }, h('div', { class: 'r' }, 'Reconnecting')));
  else if (!on && o) o.remove();
}

// ---------- poll loop ----------
let fails = 0, first = true;
async function loop() {
  try {
    const [d, s] = await Promise.all([get('/api/device'), get('/api/state')]);
    fails = 0; setReconnect(false); first = false; render(d, s);
  } catch (e) {
    fails++; $('#status-dot').className = 'dot off';
    if (fails >= 3 && !first) setReconnect(true);
  }
}
splash();
loop();
setInterval(loop, 900);

// register the service worker for installable PWA + offline shell
if ('serviceWorker' in navigator) {
  navigator.serviceWorker.register('/sw.js').catch(() => {});
  // When a freshly deployed worker takes control, reload once so the new
  // app.js/styles.css actually load, no manual cache-clearing needed.
  let refreshing = false;
  navigator.serviceWorker.addEventListener('controllerchange', () => {
    if (refreshing) return;
    refreshing = true;
    location.reload();
  });
}
