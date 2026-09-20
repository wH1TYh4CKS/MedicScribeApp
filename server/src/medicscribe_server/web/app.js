// MedicScribe browser app: record -> stream PCM over WS -> render SOAP note -> copy.
const els = {};
let ws = null;
let audioCtx = null;
let stream = null;
let workletNode = null;
let sourceNode = null;
let analyser = null;
let vizRAF = null;
let timerId = null;
let startedAt = 0;
let state = 'idle'; // idle | starting | recording | generating | done | error
let backendReady = false;
const MAX_RECORD_SECONDS = 1800; // client auto-stop; mirrors server max_recording_seconds
// Evidence that the capture is alive: the timestamp of the last PCM chunk the
// worklet handed us. A recording is judged on this, never on a guess about what
// a backgrounded tab does.
let lastChunkAt = 0;
let watchdogId = null;
let visibleSince = Date.now();
const CHUNK_STALL_MS = 6000;   // no audio for this long, while visible = dead
const RESUME_GRACE_MS = 3000;  // let a woken tab flush its queued chunks first
// This script's own ?v= token (set by the /scribe route) — reuse it to cache-bust
// the worklet load so a redeploy can't leave a stale worklet behind.
const ASSET_V = (() => {
  try { return new URL(document.currentScript.src).search; } catch { return ''; }
})();

function wsUrl() {
  const proto = location.protocol === 'https:' ? 'wss' : 'ws';
  return `${proto}://${location.host}/ws/scribe`;
}

function setStatus(text) { els.status.textContent = text; }

// Record button reflects both the app state and whether the backend is ready.
// While recording we always allow Stop, even if a health poll flickers.
function setLabel(text) {
  const span = els.recordBtn.querySelector('.rb-label');
  if (span) span.textContent = text; else els.recordBtn.textContent = text;
}

// One place to keep the visible label, the screen-reader label, the pressed
// state and disabled in sync. Recording used to be signalled by colour and
// pulse alone, which a screen reader never sees.
function setButton(label, ariaLabel, pressed, disabled) {
  const b = els.recordBtn;
  setLabel(label);
  b.setAttribute('aria-label', ariaLabel);
  b.setAttribute('aria-pressed', String(pressed));
  b.disabled = disabled;
}

function refreshButton() {
  els.recordBtn.classList.toggle('rec', state === 'recording');
  setPageTitle();
  setFavicon(state === 'recording' ? '#c23b2e' : '#0a7a66');
  if (state === 'recording') { setButton('Stop', 'Stop recording', true, false); return; }
  // Label the wait honestly: the button used to read "Record" while dead.
  if (state === 'generating') { setButton('Working…', 'Writing the note, please wait', false, true); return; }
  if (state === 'starting') { setButton('Working…', 'Waiting for microphone permission', false, true); return; }
  setButton('Record', 'Start recording', false, !backendReady);
}

// System status pill (green = ready, red = not). Polled from /health/ready, which
// checks the ASR model AND the note LLM backend — so a tester knows the difference
// between "down" and "their fault", and you don't panic opening the page.
function setSystemStatus(ready, detail) {
  backendReady = ready;
  els.sysDot.className = 'dot ' + (ready ? 'ok' : 'down');
  els.sysText.textContent = detail;
  // Keep the line under the record button honest: it must never claim "Ready."
  // while the backend can't take audio — mirror the pill's detail instead.
  if (!ready) setStatus(detail);
  else if (state === 'idle') setStatus('Ready.');
  refreshButton();
}

async function pollHealth() {
  try {
    const r = await fetch('/health/ready', { cache: 'no-store' });
    const d = await r.json();
    if (d.ready) setSystemStatus(true, 'System online');
    else if (d.asr && !d.note_llm) setSystemStatus(false, 'Starting up — note engine offline');
    else if (!d.asr) setSystemStatus(false, 'Starting up — transcriber offline');
    else setSystemStatus(false, 'System unavailable');
  } catch {
    setSystemStatus(false, 'Server unreachable');
  }
}

// Drop a live socket without letting its own close handler report a second
// error, and free the server-side session slot (per-IP cap) immediately.
function closeSocket() {
  if (!ws) return;
  ws.onopen = ws.onmessage = ws.onerror = ws.onclose = null;
  try { ws.close(); } catch {}
  ws = null;
}

function showError(msg) {
  state = 'error';
  teardownAudio();               // release mic + stop the visualizer on any error
  stopWatchdog();
  closeSocket();
  els.skeleton.hidden = true;
  // The status line sits under the button — where the user is already looking.
  // Blanking it made that spot go empty; point at the message instead.
  setStatus('Something went wrong — details below.');
  renderErrorBox(msg);
  stopTimer();
  refreshButton();
}

// The error box carries its own Retry. The recorded audio is already gone
// server-side, so retry means "put the UI back to ready", not "re-send".
function renderErrorBox(msg) {
  els.errorBox.textContent = '';
  const text = document.createElement('span');
  text.className = 'error-text';
  text.textContent = msg;
  const retry = document.createElement('button');
  retry.type = 'button';
  retry.className = 'error-retry';
  retry.textContent = 'Try again';
  retry.addEventListener('click', resetToIdle);
  els.errorBox.append(text, retry);
  els.errorBox.hidden = false;
}

function clearError() { els.errorBox.hidden = true; els.errorBox.textContent = ''; }

// Return the whole UI to a fresh, ready-to-record state. Used by Retry.
function resetToIdle() {
  clearError();
  closeSocket();
  els.skeleton.hidden = true;
  els.noteCard.hidden = true;
  els.privacy.hidden = true;
  hideOffer();
  setRecorderCompact(false);
  stopTimer();
  els.timer.hidden = true;
  state = 'idle';
  setStatus('Ready.');
  refreshButton();
  els.recordBtn.focus();         // keyboard/screen-reader users land on the next action
}

// Once a note is on screen the 180px record button no longer deserves the
// viewport. CSS owns the shrink; JS only says when.
function setRecorderCompact(on) {
  if (els.recorder) els.recorder.classList.toggle('compact', on);
}

function startTimer() {
  startedAt = Date.now();
  els.timer.hidden = false;
  timerId = setInterval(() => {
    const s = Math.floor((Date.now() - startedAt) / 1000);
    const mm = String(Math.floor(s / 60)).padStart(2, '0');
    const ss = String(s % 60).padStart(2, '0');
    els.timer.textContent = `${mm}:${ss}`;
    setPageTitle();
    if (s >= MAX_RECORD_SECONDS && state === 'recording') stopRecording();
  }, 250);
}

function stopTimer() { if (timerId) { clearInterval(timerId); timerId = null; } }

async function startRecording() {
  if (!backendReady) { showError('System is starting up — please wait a moment and try again.'); return; }
  clearError();
  els.noteCard.hidden = true;
  els.skeleton.hidden = true;
  els.privacy.hidden = true;
  hideOffer();
  setRecorderCompact(false);     // a new take gets the full-size control back
  // Deaf spot between click and mic grant: keep the label honest there too.
  // `state` must move off 'idle' first — pollHealth fires every 15s and calls
  // refreshButton(), which would otherwise re-enable the button and relabel it
  // 'Record' while the permission dialog is still open, inviting a second click
  // and a parallel getUserMedia.
  state = 'starting';
  setButton('Working…', 'Waiting for microphone permission', false, true);
  setStatus('Requesting microphone…');

  try {
    stream = await navigator.mediaDevices.getUserMedia({ audio: true });
  } catch (e) {
    showError('Microphone permission denied. Allow mic access and try again.');
    return;
  }

  audioCtx = new (window.AudioContext || window.webkitAudioContext)();
  try {
    await audioCtx.audioWorklet.addModule('/static/scribe/pcm-worklet.js' + ASSET_V);
  } catch (e) {
    showError('Audio engine failed to load. Reload the page and try again.');
    return;
  }

  ws = new WebSocket(wsUrl());
  ws.binaryType = 'arraybuffer';

  ws.onopen = () => {
    const sessionId = (crypto.randomUUID && crypto.randomUUID()) ||
      `s-${Date.now()}-${Math.random().toString(16).slice(2)}`;
    ws.send(JSON.stringify({ type: 'start', session_id: sessionId, template: 'soap_v1' }));

    sourceNode = audioCtx.createMediaStreamSource(stream);
    workletNode = new AudioWorkletNode(audioCtx, 'pcm-downsampler');
    workletNode.port.onmessage = (ev) => {
      lastChunkAt = Date.now();
      if (ws && ws.readyState === WebSocket.OPEN) ws.send(ev.data);
    };
    // Keep the graph pumping in Safari: route through a muted gain to destination.
    const mute = audioCtx.createGain();
    mute.gain.value = 0;
    sourceNode.connect(workletNode);
    workletNode.connect(mute);
    mute.connect(audioCtx.destination);
    startViz(); // live level meter so the client sees the mic is picking up audio

    state = 'recording';
    setStatus('Recording. You can switch tabs — it keeps going.');
    lastChunkAt = Date.now();
    startTimer();
    startWatchdog();
    refreshButton();
  };

  ws.onmessage = (ev) => handleServerMessage(ev.data);
  // 'generating' too: a drop after Stop (server restart mid note-gen) must surface
  // an error, not leave the shimmer skeleton spinning forever.
  ws.onerror = () => {
    if (state === 'recording' || state === 'generating') showError('Connection error.');
  };
  ws.onclose = () => {
    if (state === 'recording') showError('Connection lost. Please try again.');
    else if (state === 'generating') showError('Connection lost while generating the note. Please try again.');
  };
}

function handleServerMessage(raw) {
  let msg;
  try { msg = JSON.parse(raw); } catch { return; }
  switch (msg.type) {
    case 'ack':
      break;
    case 'note_progress':
      setStatus(`Generating note… ${msg.pct || ''}%`);
      break;
    case 'audio_deleted':
      els.privacy.hidden = false;
      break;
    case 'note_done':
      renderNote(msg.note);
      break;
    case 'error':
      showError(serverErrorText(msg));
      break;
  }
}

function serverErrorText(msg) {
  if (msg.code === 'NOTE_FAILED') return 'Note generation failed. Please try again.';
  if (msg.code === 'ASR_FAILED') return 'Transcription failed. Please try again.';
  if (msg.code === 'NO_SPEECH') return 'No speech detected — speak clearly and try again.';
  if (msg.code === 'BUSY') return 'System is busy with other consultations — please try again shortly.';
  if (msg.code === 'LIMIT_EXCEEDED') return 'Recording too long. Please keep consults under the limit and try again.';
  // A whole clinic shares one NAT'd IP and the per-IP cap is 2, so the third
  // person to press Record lands here — the raw server string ("too many active
  // sessions from your connection") reads like their own fault.
  if (msg.code === 'IP_LIMIT') return 'Another MedicScribe session is already running on this network. Close the other tab or wait for it to finish, then try again.';
  if (msg.code === 'ALREADY_STARTED') return 'This session is already recording. Reload the page and try again.';
  if (msg.code === 'INVALID_MESSAGE') return "The server didn't understand this session. Please reload the page and try again.";
  return msg.message || 'Server error.';
}

// Privacy receipt: a toggle reveals a live /transparency panel. Two call sites
// share this — the pre-record link (the doctor decides to trust us BEFORE the
// mic prompt) and the post-note pill — so the target is passed in, not assumed.
function togglePrivacy(btn, panel) {
  const open = panel.hidden;
  btn.setAttribute('aria-expanded', String(open));
  if (!open) { panel.hidden = true; return; }
  panel.hidden = false;
  loadPrivacy(panel);
}

// Re-fetched on every open so audio_files_now reflects the current disk state.
async function loadPrivacy(panel) {
  panel.textContent = 'Checking…';
  try {
    const res = await fetch('/transparency');
    if (!res.ok) throw new Error('HTTP ' + res.status);
    renderPrivacy(panel, await res.json());
  } catch {
    panel.textContent = "Couldn't load the privacy receipt.";
  }
}

function renderPrivacy(panel, t) {
  const rows = [
    ['Audio on disk now', `${t.audio_files_now} file(s)`],
    ['Audio storage', t.audio_storage],
    ['Audio retention', t.audio_retention],
    ['Transcript', t.transcript_storage],
    ['Note', t.note_storage],
    ['Database', t.database ? 'yes' : 'none'],
    ['Cloud egress', t.cloud_egress ? 'yes' : 'none'],
  ];
  panel.innerHTML = '';
  for (const [k, v] of rows) {
    const row = document.createElement('div');
    row.className = 'pd-row';
    const key = document.createElement('span'); key.className = 'pd-key'; key.textContent = k;
    const val = document.createElement('span'); val.className = 'pd-val'; val.textContent = v;
    row.append(key, val);
    panel.append(row);
  }
  if (t.source_commit) {
    const foot = document.createElement('div');
    foot.className = 'pd-foot';
    foot.textContent = 'build ' + t.source_commit;
    panel.append(foot);
  }
}

function renderNote(note) {
  els.skeleton.hidden = true;
  const text = (note && note.soap_text) ? note.soap_text : '';
  if (!text.trim()) {
    setStatus('Nothing captured. Try recording again.');
    state = 'idle';
    refreshButton();
    return;
  }
  els.noteBody.innerHTML = '';
  for (const section of parseSoap(text)) {
    const h = document.createElement('div');
    h.className = 'soap-section';
    const label = document.createElement('span');
    label.className = 'soap-label';
    label.textContent = section.label;
    const body = document.createElement('span');
    body.className = 'soap-text';
    body.textContent = section.body;
    h.append(label, body);
    els.noteBody.append(h);
  }
  els.noteCard.dataset.raw = text;
  els.noteCard.hidden = false;
  // re-trigger the reveal animation each time
  els.noteCard.classList.remove('reveal');
  void els.noteCard.offsetWidth;
  els.noteCard.classList.add('reveal');
  showOffer();
  setRecorderCompact(true);      // the note is the subject now, not the button
  scrollNoteIntoView();
  state = 'done';
  setStatus('Note ready.');
  refreshButton();
}

// The note card is revealed below the fold: on a phone the doctor sees only its
// top edge, on desktop the body sits under the viewport. Scroll to the note —
// never past it to the offer, which stays discoverable just underneath.
function scrollNoteIntoView() {
  const reduced = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  els.noteCard.scrollIntoView({ behavior: reduced ? 'auto' : 'smooth', block: 'start' });
}

// Conversion card shares the note's lifecycle, but lands last so it reads as
// the end of the journey rather than competing with the note.
function showOffer() {
  if (!els.offer) return;
  els.offer.hidden = false;
  els.offer.classList.remove('reveal-late');
  void els.offer.offsetWidth;
  els.offer.classList.add('reveal-late');
}

function hideOffer() {
  if (!els.offer) return;
  els.offer.hidden = true;
  els.offer.classList.remove('reveal-late');
}

// Split "S: ...\nO: ...\nA: ...\nP: ..." into labelled sections; falls back to
// one block if the markers are absent.
function parseSoap(text) {
  const map = { S: 'Subjective', O: 'Objective', A: 'Assessment', P: 'Plan' };
  const lines = text.split('\n');
  const sections = [];
  let cur = null;
  for (const line of lines) {
    const m = line.match(/^\s*([SOAP])\s*:\s*(.*)$/);
    if (m) {
      cur = { label: map[m[1]], body: m[2] };
      sections.push(cur);
    } else if (cur) {
      cur.body += (cur.body ? '\n' : '') + line;
    }
  }
  if (sections.length === 0) return [{ label: 'Note', body: text }];
  return sections;
}

// ---- live mic level visualizer (confidence cue that audio is being picked up) ----
function startViz() {
  if (!audioCtx || !sourceNode) return;
  analyser = audioCtx.createAnalyser();
  analyser.fftSize = 128;            // 64 frequency bins
  analyser.smoothingTimeConstant = 0.78;
  sourceNode.connect(analyser);      // parallel tap; analyser is a sink, no further wiring
  els.viz.hidden = false;
  drawViz();
}

function drawViz() {
  vizRAF = requestAnimationFrame(drawViz);
  const canvas = els.viz;
  const ctx = canvas.getContext('2d');
  const dpr = window.devicePixelRatio || 1;
  const w = canvas.clientWidth, h = canvas.clientHeight;
  if (canvas.width !== Math.round(w * dpr)) { canvas.width = w * dpr; canvas.height = h * dpr; }
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  ctx.clearRect(0, 0, w, h);

  const bins = analyser.frequencyBinCount;
  const data = new Uint8Array(bins);
  analyser.getByteFrequencyData(data);

  const bars = 28, gap = 3;
  const bw = (w - gap * (bars - 1)) / bars;
  const mid = h / 2;
  for (let i = 0; i < bars; i++) {
    const v = data[Math.floor((i / bars) * bins * 0.7)] / 255; // voice sits low-mid
    const bh = Math.max(2, v * v * (h * 0.9));                  // squared = snappier
    const x = i * (bw + gap);
    const g = ctx.createLinearGradient(0, mid - bh / 2, 0, mid + bh / 2);
    g.addColorStop(0, '#6cb6e8');
    g.addColorStop(1, '#36d6b4');
    ctx.fillStyle = g;
    roundRect(ctx, x, mid - bh / 2, bw, bh, Math.min(bw / 2, 3));
    ctx.fill();
  }
}

function roundRect(ctx, x, y, w, h, r) {
  if (ctx.roundRect) { ctx.beginPath(); ctx.roundRect(x, y, w, h, r); return; }
  ctx.beginPath();
  ctx.moveTo(x + r, y);
  ctx.arcTo(x + w, y, x + w, y + h, r);
  ctx.arcTo(x + w, y + h, x, y + h, r);
  ctx.arcTo(x, y + h, x, y, r);
  ctx.arcTo(x, y, x + w, y, r);
  ctx.closePath();
}

function stopViz() {
  if (vizRAF) { cancelAnimationFrame(vizRAF); vizRAF = null; }
  if (analyser) { try { analyser.disconnect(); } catch {} analyser = null; }
  if (els.viz) {
    els.viz.hidden = true;
    const ctx = els.viz.getContext('2d');
    if (ctx) ctx.clearRect(0, 0, els.viz.width, els.viz.height);
  }
}

// Single place to release mic + audio graph (used by stop and by errors).
function teardownAudio() {
  stopViz();
  if (stream) { stream.getTracks().forEach((t) => t.stop()); stream = null; }
  if (sourceNode) { try { sourceNode.disconnect(); } catch {} sourceNode = null; }
  if (workletNode) { try { workletNode.disconnect(); } catch {} workletNode = null; }
  if (audioCtx) { audioCtx.close().catch(() => {}); audioCtx = null; }
}

function stopRecording() {
  if (ws && ws.readyState === WebSocket.OPEN) {
    ws.send(JSON.stringify({ type: 'stop' }));
  }
  teardownAudio();
  stopWatchdog();
  state = 'generating';
  stopTimer();
  els.skeleton.hidden = false; // shimmer placeholder while the note is built
  setStatus('Generating note…');
  refreshButton();
}

function onRecordClick() {
  if (state === 'recording') stopRecording();
  else startRecording();
}

async function copyNote() {
  const text = els.noteCard.dataset.raw || '';
  try {
    await navigator.clipboard.writeText(text);
    els.copyBtn.textContent = 'Copied ✓';
    setTimeout(() => { els.copyBtn.textContent = 'Copy note'; }, 1500);
  } catch {
    // Reset like the success path does — a stuck "Copy failed" reads as a dead
    // button and the doctor has no way to tell a retry is allowed.
    els.copyBtn.textContent = 'Copy failed';
    setTimeout(() => { els.copyBtn.textContent = 'Copy note'; }, 1500);
  }
}

// ---- lifecycle: the recording must survive a tab switch ----
// The whole point of this tool is "press Record, put it to one side". A hidden
// tab keeps an AudioWorklet running as long as the mic track is live, so a tab
// switch is NOT a reason to end the session. What genuinely kills a capture is
// the AudioContext being suspended (a phone call, an app switch, the machine
// sleeping) — so on return we try to resume it, and then judge the session on
// evidence: are PCM chunks still arriving?

function socketIsOpen() { return !!ws && ws.readyState === WebSocket.OPEN; }

function audioIsFlowing() { return Date.now() - lastChunkAt < CHUNK_STALL_MS; }

// Runs only while the page is visible. A background tab can deliver the
// worklet's messages in bursts, and failing the session on that gap was exactly
// the old bug — so a hidden tab is never judged at all.
function startWatchdog() {
  stopWatchdog();
  watchdogId = setInterval(() => {
    if (state !== 'recording') return;
    if (document.visibilityState !== 'visible') return;
    if (Date.now() - visibleSince < RESUME_GRACE_MS) return;
    if (!socketIsOpen()) {
      showError('Connection lost. Nothing was saved — please record again.');
    } else if (!audioIsFlowing()) {
      showError('The microphone stopped sending audio — the device may have slept, ' +
        'or another app took the mic. Nothing was saved — please record again.');
    }
  }, 2000);
}

function stopWatchdog() { if (watchdogId) { clearInterval(watchdogId); watchdogId = null; } }

async function onPageVisible() {
  visibleSince = Date.now();
  if (state !== 'recording' && state !== 'generating') return;
  // A suspended context is recoverable often enough to be worth trying before
  // telling a doctor their consult is gone.
  if (audioCtx && audioCtx.state === 'suspended') {
    try { await audioCtx.resume(); } catch {}
  }
  if (!socketIsOpen()) {
    showError(state === 'recording'
      ? 'The connection dropped while this page was in the background. Nothing was saved — please record again.'
      : 'The connection dropped while the note was being written. Please record again.');
  }
}

// Closing or reloading the tab mid-consult loses the audio, so make it a
// deliberate act rather than a stray Ctrl-W.
function onBeforeUnload(e) {
  if (state !== 'recording' && state !== 'generating') return;
  e.preventDefault();
  e.returnValue = '';
}

// Leaving the page must never leave the mic light on; teardownAudio is the one
// mic-release point, so route through it rather than touching tracks here.
function onPageHide() {
  if (state !== 'recording' && state !== 'generating') return;
  closeSocket();
  teardownAudio();
  stopWatchdog();
}

// ---- the tab itself as the status light ----
// A doctor who parked this tab beside their notes reads the title, not the
// page. Keep the state and the running time in it, and colour the favicon.
function setPageTitle() {
  if (state === 'recording') document.title = `● ${els.timer.textContent} · Recording — MedicScribe`;
  else if (state === 'generating') document.title = 'Writing note… — MedicScribe';
  else if (state === 'done') document.title = 'Note ready — MedicScribe';
  else document.title = 'MedicScribe';
}

let faviconColor = '';
function setFavicon(color) {
  if (color === faviconColor) return;
  faviconColor = color;
  const svg = `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 32 32">` +
    `<circle cx="16" cy="16" r="11" fill="${color}"/></svg>`;
  let link = document.querySelector('link[rel="icon"]');
  if (!link) { link = document.createElement('link'); link.rel = 'icon'; document.head.append(link); }
  link.type = 'image/svg+xml';
  link.href = 'data:image/svg+xml,' + encodeURIComponent(svg);
}

// ---- theme: light by default, dark on request, remembered per browser ----
const THEME_KEY = 'ms-theme';

function systemPrefersDark() {
  return window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches;
}

function currentTheme() {
  const set = document.documentElement.dataset.theme;
  if (set === 'light' || set === 'dark') return set;
  return systemPrefersDark() ? 'dark' : 'light';
}

function applyTheme(theme) {
  document.documentElement.dataset.theme = theme;
  try { localStorage.setItem(THEME_KEY, theme); } catch {}
  if (els.themeBtn) {
    els.themeBtn.setAttribute('aria-label',
      theme === 'dark' ? 'Switch to light theme' : 'Switch to dark theme');
  }
}

window.addEventListener('DOMContentLoaded', () => {
  for (const id of ['recordBtn', 'status', 'timer', 'noteCard', 'noteBody', 'copyBtn',
    'privacy', 'privacyBtn', 'privacyDetail', 'themeBtn',
    'offer', 'errorBox', 'sysDot', 'sysText', 'skeleton', 'viz']) {
    els[id] = document.getElementById(id);
  }
  els.recorder = document.querySelector('.recorder');
  els.recordBtn.addEventListener('click', onRecordClick);
  els.copyBtn.addEventListener('click', copyNote);
  els.privacyBtn.addEventListener('click', () => togglePrivacy(els.privacyBtn, els.privacyDetail));
  applyTheme(currentTheme());
  els.themeBtn.addEventListener('click', () => {
    applyTheme(currentTheme() === 'dark' ? 'light' : 'dark');
  });

  // Announce state to screen readers. Set here too so the wiring survives an
  // index.html that hasn't got the initial attributes yet.
  els.status.setAttribute('aria-live', 'polite');
  els.errorBox.setAttribute('role', 'alert');

  document.addEventListener('visibilitychange', () => {
    if (document.visibilityState === 'visible') onPageVisible();
  });
  // bfcache restore doesn't reliably fire visibilitychange — check there too.
  window.addEventListener('pageshow', onPageVisible);
  window.addEventListener('pagehide', onPageHide);
  window.addEventListener('beforeunload', onBeforeUnload);

  // Not "Ready." until /health/ready confirms it — the pill and this line are
  // both seeded by the same poll, so start with the honest pre-poll state.
  setStatus('Starting up…');
  refreshButton();              // seed aria-label/aria-pressed before the first poll
  pollHealth();                 // immediate, then keep the pill live
  setInterval(pollHealth, 15000);
});
