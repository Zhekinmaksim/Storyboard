/* storyboard frontend — vanilla JS, no build step.
 *
 * Connects to the Fly.io API at the origin set in window.__SB_API__.
 * Defaults to localhost in dev, https://api.hermes-story.art in prod.
 */

const API_BASE =
  (typeof window !== 'undefined' && window.__SB_API__) ||
  (location.hostname === 'localhost' || location.hostname === '127.0.0.1'
    ? 'http://localhost:8080'
    : 'https://api.hermes-story.art');

// =================== DOM refs ===================

const $ = (id) => document.getElementById(id);
const proseEl = $('prose');
const generateBtn = $('generate-btn');
const demoButtons = $('demo-buttons');
const statusBar = $('status');
const statusText = $('status-text');
const statusMeta = $('status-meta');
const boardEmpty = $('board-empty');
const boardEl = $('board');
const critiquePanel = $('critique-panel');
const revisionsEl = $('revisions');
const memoryPanel = $('memory-panel');
const memoryRuleEl = $('memory-rule');
const memoryTagsEl = $('memory-tags');
const revisePanel = $('revise-panel');
const reviseTarget = $('revise-target');
const reviseNote = $('revise-note');
const reviseBtn = $('revise-btn');
const downloadPanel = $('download-panel');
const downloadLink = $('download-link');
const heroDemoBoard = $('hero-demo-board');
const heroDemoStage = $('hero-demo-stage');
const heroLine1 = $('hero-line-1');
const heroLine2 = $('hero-line-2');
const cinemaBars = $('cinema-bars');

// =================== State ===================

let currentJob = null;
let currentEventSource = null;
let svgRoot = null;
let selectedFrame = null;

// =================== Cinema intro: remove bars after they finish =====

if (cinemaBars) {
  setTimeout(() => {
    cinemaBars.style.display = 'none';
  }, 1700);
}

// =================== Hero text reveal ====================

setTimeout(() => heroLine1?.classList.add('reveal'), 300);
setTimeout(() => heroLine2?.classList.add('reveal'), 700);
// Trigger underline draw after the line that contains "Hermes" reveals
setTimeout(() => {
  const draw = document.querySelector('.hero-draw');
  if (draw) draw.classList.add('draw-active');
}, 1100);

// =================== Hero auto-demo =====================

async function loadHeroDemo() {
  if (!heroDemoBoard) return;
  try {
    const resp = await fetch('/assets/hero-demo.svg', { cache: 'force-cache' });
    if (!resp.ok) return;
    const svgText = await resp.text();

    // The SMIL animations inside the SVG begin at t=0 from page load.
    // To make the hero demo loop, we wait ~10s, fade out, fade in fresh.
    const cycleStage = (label) => {
      if (heroDemoStage) heroDemoStage.textContent = label;
    };

    const insert = () => {
      heroDemoBoard.style.opacity = 0;
      heroDemoBoard.innerHTML = svgText;
      requestAnimationFrame(() => {
        heroDemoBoard.style.transition = 'opacity 0.4s ease';
        heroDemoBoard.style.opacity = 1;
      });
    };

    insert();

    // Stage labels mimic the live pipeline so users associate the demo
    // with what happens when they hit Generate.
    setTimeout(() => cycleStage('PARSING…'), 100);
    setTimeout(() => cycleStage('RENDERING SHOT 1A'), 1200);
    setTimeout(() => cycleStage('RENDERING SHOT 1B'), 3200);
    setTimeout(() => cycleStage('RENDERING SHOT 1C'), 5200);
    setTimeout(() => cycleStage('KIMI K2.5 REVIEW'), 7200);
    setTimeout(() => cycleStage('READY'), 9000);

    // Loop every 12 seconds
    setInterval(() => {
      cycleStage('RESTARTING…');
      setTimeout(() => {
        insert();
        setTimeout(() => cycleStage('PARSING…'), 100);
        setTimeout(() => cycleStage('RENDERING SHOT 1A'), 1200);
        setTimeout(() => cycleStage('RENDERING SHOT 1B'), 3200);
        setTimeout(() => cycleStage('RENDERING SHOT 1C'), 5200);
        setTimeout(() => cycleStage('KIMI K2.5 REVIEW'), 7200);
        setTimeout(() => cycleStage('READY'), 9000);
      }, 400);
    }, 12000);
  } catch (err) {
    console.warn('hero demo unavailable:', err);
  }
}

// =================== Status bar ===================

function setStatus(text, cls = '', meta = null) {
  statusText.textContent = text;
  statusBar.className = 'status-bar ' + cls;
  if (meta && statusMeta) statusMeta.textContent = meta;
}

// =================== Demo gallery buttons ===================

async function loadDemos() {
  // Fallback demos — used when API isn't reachable yet (e.g. deploying
  // to Vercel before Fly.io is up). Site looks complete regardless.
  const FALLBACK = [
    { id: 'noir', title: 'Noir alley',
      prose: 'A detective enters a rain-soaked alley at night. He walks past silent buildings, dispatch crackling in his ear. He finds a body. He kneels, recognises the knot at the wrist — the same one as last week. He straightens, calls his partner: "Marlowe. Third one this month."' },
    { id: 'stairwell', title: 'Stairwell pursuit',
      prose: 'A detective enters a dim stairwell. She listens. A killer is on the landing above. She raises her weapon. She climbs two flights. The landing is empty. "Marlowe. He was just here."' },
    { id: 'kitchen', title: 'Kitchen confrontation',
      prose: 'Two siblings argue across a kitchen table at noon. The older one stands. The younger looks down. A phone rings. Neither answers it.' },
  ];
  const CATEGORIES = {
    noir: 'NOIR · 6 SHOTS',
    stairwell: 'SUSPENSE · 6 SHOTS',
    kitchen: 'DRAMA · 6 SHOTS',
  };

  const fillDemos = (demos) => {
    demoButtons.innerHTML = '';
    for (const d of demos) {
      const b = document.createElement('button');
      b.setAttribute('data-cat', CATEGORIES[d.id] || 'SCENE · 6 SHOTS');
      const span = document.createElement('span');
      span.textContent = d.title;
      b.appendChild(span);
      b.title = d.prose;
      b.addEventListener('click', () => {
        proseEl.value = d.prose;
        proseEl.scrollIntoView({ behavior: 'smooth', block: 'center' });
        proseEl.focus();
      });
      demoButtons.appendChild(b);
    }
  };

  // Always show fallback first so demos appear even without API
  fillDemos(FALLBACK);

  try {
    const resp = await fetch(`${API_BASE}/api/demos`);
    if (!resp.ok) throw new Error(`demos http ${resp.status}`);
    const { demos } = await resp.json();
    fillDemos(demos);
    setStatus('ready', '', 'hermes-agent · api online');
  } catch (err) {
    console.warn('demos: using fallback (API not reachable):', err);
    setStatus('ready', '', 'preview mode · api will connect when live');
  }
}

// =================== Generate ===================

async function generate() {
  const prose = proseEl.value.trim();
  if (prose.length < 5) {
    setStatus('please write at least a couple of sentences', 'is-error');
    proseEl.focus();
    return;
  }

  resetBoard();
  generateBtn.disabled = true;
  setStatus('starting…', 'is-running', 'hermes-agent · running');

  const shareEl = document.getElementById('share-input');
  const sharing = !!(shareEl && shareEl.checked);

  try {
    const resp = await fetch(`${API_BASE}/api/start`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ prose, share_to_gallery: sharing }),
    });
    if (!resp.ok) {
      const err = await resp.json().catch(() => ({ error: `HTTP ${resp.status}` }));
      setStatus('error · ' + (err.error || 'request failed'), 'is-error');
      generateBtn.disabled = false;
      return;
    }
    const { job_id } = await resp.json();
    currentJob = job_id;
    listenForEvents(job_id);
  } catch (err) {
    setStatus('network error · could not reach API', 'is-error');
    generateBtn.disabled = false;
    console.error(err);
  }
}

function resetBoard() {
  if (currentEventSource) {
    currentEventSource.close();
    currentEventSource = null;
  }
  boardEl.innerHTML = '';
  boardEl.hidden = true;
  boardEmpty.hidden = false;
  critiquePanel.hidden = true;
  revisionsEl.innerHTML = '';
  memoryPanel.hidden = true;
  revisePanel.hidden = true;
  const refinePanel = document.getElementById('refine-panel');
  if (refinePanel) refinePanel.hidden = true;
  downloadPanel.hidden = true;
  const inspectPanel = document.getElementById('inspect-panel');
  if (inspectPanel) inspectPanel.hidden = true;
  selectedFrame = null;
  reviseTarget.textContent = 'no frame selected';
  reviseTarget.classList.remove('is-active');
  reviseBtn.disabled = true;
  reviseNote.value = '';
  svgRoot = null;
}

// =================== SSE handling ===================

function listenForEvents(jobId) {
  const url = `${API_BASE}/api/events/${jobId}`;
  const es = new EventSource(url);
  currentEventSource = es;

  es.addEventListener('status', (e) => {
    try {
      const d = JSON.parse(e.data);
      setStatus(d.message || d.stage, 'is-running');
    } catch {}
  });

  es.addEventListener('scene', (e) => {
    const d = JSON.parse(e.data);
    setStatus(`scene parsed · ${d.shot_count} shots`, 'is-running');
  });

  es.addEventListener('skeleton', (e) => {
    const d = JSON.parse(e.data);
    boardEmpty.hidden = true;
    boardEl.hidden = false;
    boardEl.innerHTML = d.svg;
    svgRoot = boardEl.querySelector('svg');
    setStatus('drawing the board…', 'is-running');
  });

  es.addEventListener('skeleton_replace', (e) => {
    const d = JSON.parse(e.data);
    boardEl.innerHTML = d.svg;
    svgRoot = boardEl.querySelector('svg');
    setStatus('redrawing with new direction…', 'is-running');
  });

  es.addEventListener('shot', (e) => {
    const d = JSON.parse(e.data);
    if (!svgRoot) return;
    appendShotToBoard(svgRoot, d.svg);
    setStatus(`drawing shot ${d.label}…`, 'is-running');
  });

  es.addEventListener('shot_replace', (e) => {
    const d = JSON.parse(e.data);
    if (!svgRoot) return;
    replaceShotOnBoard(svgRoot, d.label, d.svg);
    setStatus(`re-rendered ${d.label}`, 'is-running');
  });

  es.addEventListener('revision', (e) => {
    const r = JSON.parse(e.data);
    showRevision(r);
    pulseFrame(r.shot_label);
  });

  es.addEventListener('memory_saved', (e) => {
    const d = JSON.parse(e.data);
    showMemorySaved(d);
  });

  es.addEventListener('done', () => {
    setStatus('done · click any frame to direct it', 'is-done', 'hermes-agent · awaiting director');
    generateBtn.disabled = false;
    revisePanel.hidden = false;
    const refinePanel = document.getElementById('refine-panel');
    if (refinePanel) refinePanel.hidden = false;
    showDownload(jobId);
    bindFrameClicks();
    showInspectPanel(jobId);
    // Reload gallery in case this run was shared
    loadGallery();
    // Keep SSE open — revise events flow back through the same channel.
  });

  es.addEventListener('error', (e) => {
    let msg = 'pipeline error';
    try {
      const d = JSON.parse(e.data);
      if (d && d.message) msg = 'error · ' + d.message;
    } catch {}
    setStatus(msg, 'is-error');
    generateBtn.disabled = false;
    es.close();
  });

  es.onerror = () => {
    if (es.readyState === EventSource.CLOSED) return;
    setStatus('connection lost', 'is-error');
    generateBtn.disabled = false;
  };
}

// =================== Board manipulation ===================

function appendShotToBoard(svg, fragment) {
  const tmp = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
  tmp.innerHTML = fragment;
  while (tmp.firstChild) {
    svg.appendChild(tmp.firstChild);
  }
}

function replaceShotOnBoard(svg, label, fragment) {
  const existing = svg.querySelector(`g[data-shot-label="${label}"]`);
  if (existing) existing.remove();
  appendShotToBoard(svg, fragment);
}

function pulseFrame(label) {
  if (!svgRoot) return;
  const target = svgRoot.querySelector(`g[data-shot-label="${label}"]`);
  if (!target) return;
  target.classList.add('kimi-flag');
  setTimeout(() => target.classList.remove('kimi-flag'), 3500);
}

function bindFrameClicks() {
  if (!svgRoot) return;
  const frames = svgRoot.querySelectorAll('g[data-shot-label]');
  frames.forEach((g) => {
    g.addEventListener('click', () => {
      frames.forEach((f) => f.classList.remove('is-selected'));
      g.classList.add('is-selected');
      const label = g.getAttribute('data-shot-label');
      selectedFrame = label;
      reviseTarget.textContent = `frame ${label}`;
      reviseTarget.classList.add('is-active');
      reviseBtn.disabled = false;
      reviseNote.focus();
    });
  });
}

// =================== Critique panel ===================

function showRevision(r) {
  critiquePanel.hidden = false;
  const li = document.createElement('li');

  const label = document.createElement('span');
  label.className = 'rev-label';
  label.textContent = r.shot_label;

  const field = document.createElement('span');
  field.className = 'rev-field';
  field.textContent = r.field;

  const arrow = document.createElement('span');
  arrow.className = 'rev-arrow';
  arrow.textContent = '→';

  const value = document.createElement('span');
  value.className = 'rev-value';
  value.textContent = r.new_value;

  const reason = document.createElement('p');
  reason.className = 'rev-reason';
  reason.textContent = r.reason || '';

  li.appendChild(label);
  li.appendChild(field);
  li.appendChild(arrow);
  li.appendChild(value);
  li.appendChild(reason);
  revisionsEl.appendChild(li);
}

// =================== Memory panel ===================

function showMemorySaved({ preference, applies_to }) {
  memoryPanel.hidden = false;
  memoryRuleEl.textContent = preference || '';
  if (Array.isArray(applies_to) && applies_to.length) {
    memoryTagsEl.textContent = 'applies to: ' + applies_to.join(' · ');
  } else {
    memoryTagsEl.textContent = '';
  }
}

// =================== Download ===================

function showDownload(jobId) {
  downloadPanel.hidden = false;
  downloadLink.href = `${API_BASE}/api/result/${jobId}.zip`;
  const gif = document.getElementById('download-gif');
  if (gif) gif.href = `${API_BASE}/api/result/${jobId}.gif`;
  // Stash currentJob for share button
  window.__SB_CURRENT_JOB = jobId;
}

// =================== Revise ===================

async function revise() {
  if (!currentJob || !selectedFrame) return;
  const note = reviseNote.value.trim();
  if (!note) return;
  reviseBtn.disabled = true;
  setStatus(`revising frame ${selectedFrame}…`, 'is-running');

  try {
    const resp = await fetch(`${API_BASE}/api/revise`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ job_id: currentJob, frame: selectedFrame, note }),
    });
    if (!resp.ok) {
      const err = await resp.json().catch(() => ({ error: `HTTP ${resp.status}` }));
      setStatus('revise error · ' + (err.error || 'failed'), 'is-error');
      reviseBtn.disabled = false;
      return;
    }
    reviseNote.value = '';
    reviseBtn.disabled = false;
  } catch (err) {
    console.error(err);
    setStatus('revise network error', 'is-error');
    reviseBtn.disabled = false;
  }
}

// =================== Wire up ===================

generateBtn.addEventListener('click', generate);
reviseBtn.addEventListener('click', revise);
proseEl.addEventListener('keydown', (e) => {
  if ((e.metaKey || e.ctrlKey) && e.key === 'Enter') generate();
});
reviseNote.addEventListener('keydown', (e) => {
  if (e.key === 'Enter' && !reviseBtn.disabled) revise();
});

setStatus('ready');
loadHeroDemo();
loadDemos();
startPlaceholderCycle();

// =================== Cycling placeholder ===================
// Rotates the textarea placeholder through genre examples so users
// understand "any scene works" without an explicit disclaimer.
// Pauses while the user has focus or has typed anything.

function startPlaceholderCycle() {
  if (!proseEl) return;
  const examples = [
    'A detective enters a rain-soaked alley at night. He finds a body. He kneels…',
    'A samurai walks through a bamboo forest at dusk. He stops. He listens…',
    'A spaceship crash-lands on a swamp moon at dawn. The cockpit is on fire…',
    'Two siblings argue across a kitchen table at noon. A phone rings. Neither answers…',
    'A bee approaches a sunflower. She lands on a petal. She walks across the florets…',
    'Хакеры в неоновом переулке штурмуют корпоративный сервер. Воют сирены…',
    '1815. Napoleon paces his tent at midnight. A messenger enters, bowing…',
  ];
  let idx = 0;

  const apply = () => {
    // Skip rotation if the user has typed or the field has focus
    if (proseEl.value.length > 0) return;
    if (document.activeElement === proseEl) return;
    proseEl.classList.add('placeholder-fade');
    setTimeout(() => {
      proseEl.placeholder = examples[idx];
      idx = (idx + 1) % examples.length;
      proseEl.classList.remove('placeholder-fade');
    }, 220);
  };

  apply();
  setInterval(apply, 4500);
}

// =================== API status pill ===================

const apiPill = document.getElementById('api-pill');
const apiPillStatus = document.getElementById('api-pill-status');
const apiPillMeta = document.getElementById('api-pill-meta');

async function pollApi() {
  if (!apiPill) return;
  const start = performance.now();
  try {
    const resp = await fetch(`${API_BASE}/api/health`, {
      method: 'GET',
      cache: 'no-store',
    });
    const ms = Math.round(performance.now() - start);
    if (!resp.ok) throw new Error(`status ${resp.status}`);
    const data = await resp.json();
    const region = data.region || 'fly';
    apiPill.classList.remove('is-offline');
    apiPill.classList.add('is-online');
    apiPillStatus.textContent = 'api · live';
    apiPillMeta.textContent = `${ms}ms · ${region}`;
  } catch (err) {
    apiPill.classList.remove('is-online');
    apiPill.classList.add('is-offline');
    apiPillStatus.textContent = 'api · sleeping';
    apiPillMeta.textContent = 'wakes on first generate';
  }
}
pollApi();
setInterval(pollApi, 30000);

// =================== Frame info tip on board hover ===================

const frameTip = document.getElementById('frame-tip');
const frameTipLabel = document.getElementById('frame-tip-label');
const frameTipMeta = document.getElementById('frame-tip-meta');

let lastHoveredFrame = null;

function setupFrameHover(scope) {
  if (!scope) return;
  scope.addEventListener('mousemove', (e) => {
    const g = e.target.closest('g[data-shot-label]');
    if (!g) {
      if (frameTip.classList.contains('visible')) {
        frameTip.classList.remove('visible');
        lastHoveredFrame = null;
      }
      return;
    }
    const label = g.getAttribute('data-shot-label');
    const shotType = (g.getAttribute('data-shot-type') || '').replace(/_/g, ' ');
    if (label !== lastHoveredFrame) {
      frameTipLabel.textContent = `FRAME ${label}`;
      frameTipMeta.textContent = shotType
        ? `${shotType} · click to direct`
        : 'click to direct this frame';
      lastHoveredFrame = label;
    }
    // Position relative to viewport, with offset
    const x = e.clientX + 14;
    const y = e.clientY + 14;
    frameTip.style.left = `${x}px`;
    frameTip.style.top = `${y}px`;
    frameTip.classList.add('visible');
  });

  scope.addEventListener('mouseleave', () => {
    frameTip.classList.remove('visible');
    lastHoveredFrame = null;
  });
}

setupFrameHover(boardEl);
setupFrameHover(document.getElementById('hero-demo-board'));

// =================== Pull-quote scroll reveal ===================

const pullquote = document.querySelector('.pullquote');
if (pullquote && 'IntersectionObserver' in window) {
  const obs = new IntersectionObserver((entries) => {
    for (const entry of entries) {
      if (entry.isIntersecting) {
        entry.target.classList.add('in-view');
        obs.unobserve(entry.target);
      }
    }
  }, { threshold: 0.4 });
  obs.observe(pullquote);
}

// =================== Voice input (Web Speech API) ===================

(function setupVoice() {
  const btn = document.getElementById('voice-btn');
  if (!btn) return;
  const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
  if (!SR) {
    btn.classList.add('is-unsupported');
    btn.title = 'Speech recognition not available in this browser. Try Chrome or Safari.';
    btn.addEventListener('click', () => {
      setStatus('voice input not supported in this browser', 'is-error');
    });
    return;
  }

  let recog = null;
  let listening = false;

  btn.addEventListener('click', () => {
    if (listening && recog) {
      recog.stop();
      return;
    }
    recog = new SR();
    recog.lang = navigator.language || 'en-US';
    recog.continuous = true;
    recog.interimResults = true;
    let baseValue = proseEl.value;
    if (baseValue && !baseValue.endsWith(' ')) baseValue += ' ';

    recog.onstart = () => {
      listening = true;
      btn.classList.add('is-listening');
      btn.querySelector('.voice-text').textContent = 'STOP';
      setStatus('listening…', 'is-running', 'speech recognition');
    };
    recog.onresult = (event) => {
      let interim = '';
      let final = '';
      for (let i = event.resultIndex; i < event.results.length; i++) {
        const transcript = event.results[i][0].transcript;
        if (event.results[i].isFinal) final += transcript;
        else interim += transcript;
      }
      if (final) baseValue += final;
      proseEl.value = baseValue + interim;
    };
    recog.onerror = (e) => {
      console.warn('speech error:', e.error);
      if (e.error === 'not-allowed' || e.error === 'service-not-allowed') {
        setStatus('microphone permission denied', 'is-error');
      }
    };
    recog.onend = () => {
      listening = false;
      btn.classList.remove('is-listening');
      btn.querySelector('.voice-text').textContent = 'VOICE';
      setStatus('ready');
    };
    recog.start();
  });
})();

// =================== Compose / refine the whole scene ===================

(function setupRefine() {
  const refineBtn = document.getElementById('refine-btn');
  const refineInput = document.getElementById('refine-input');
  if (!refineBtn || !refineInput) return;

  async function refine() {
    const job = window.__SB_CURRENT_JOB || currentJob;
    if (!job) {
      setStatus('generate a scene first', 'is-error');
      return;
    }
    const instruction = refineInput.value.trim();
    if (!instruction) return;
    refineBtn.disabled = true;
    setStatus('Hermes is composing…', 'is-running');

    try {
      const resp = await fetch(`${API_BASE}/api/refine`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ job_id: job, instruction }),
      });
      if (!resp.ok) {
        const err = await resp.json().catch(() => ({ error: `HTTP ${resp.status}` }));
        setStatus('compose error · ' + (err.error || 'failed'), 'is-error');
        refineBtn.disabled = false;
        return;
      }
      // Server pushes skeleton_replace + shot events on the open SSE channel
      refineInput.value = '';
      refineBtn.disabled = false;
    } catch (err) {
      console.error(err);
      setStatus('compose network error', 'is-error');
      refineBtn.disabled = false;
    }
  }

  refineBtn.addEventListener('click', refine);
  refineInput.addEventListener('keydown', (e) => {
    if (e.key === 'Enter' && !refineBtn.disabled) refine();
  });
})();

// =================== Public gallery ===================

async function loadGallery() {
  const grid = document.getElementById('gallery-grid');
  if (!grid) return;
  try {
    const resp = await fetch(`${API_BASE}/api/gallery`, { cache: 'no-store' });
    if (!resp.ok) throw new Error(`gallery http ${resp.status}`);
    const { entries } = await resp.json();
    if (!entries || entries.length === 0) {
      // keep the existing empty state
      return;
    }
    grid.innerHTML = '';
    for (const e of entries) {
      const card = document.createElement('a');
      card.className = 'gallery-card';
      card.href = e.share_url;
      card.target = '_blank';
      card.rel = 'noopener';

      const img = document.createElement('img');
      img.src = `${API_BASE}${e.board_url}`;
      img.alt = e.title || 'storyboard';
      img.loading = 'lazy';
      card.appendChild(img);

      const body = document.createElement('div');
      body.className = 'gallery-card-body';
      const title = document.createElement('h3');
      title.className = 'gallery-card-title';
      title.textContent = e.title || 'Untitled';
      body.appendChild(title);
      const prose = document.createElement('p');
      prose.className = 'gallery-card-prose';
      prose.textContent = e.prose_preview || '';
      body.appendChild(prose);
      const meta = document.createElement('div');
      meta.className = 'gallery-card-meta';
      const ts = e.created_at
        ? new Date(e.created_at * 1000).toLocaleDateString(undefined,
            { month: 'short', day: 'numeric' })
        : '';
      meta.textContent = `${ts} · open ↗`;
      body.appendChild(meta);
      card.appendChild(body);

      grid.appendChild(card);
    }
  } catch (err) {
    console.warn('gallery unavailable:', err);
  }
}
loadGallery();
setInterval(loadGallery, 60000);

// =================== Share button ===================

(function setupShare() {
  const btn = document.getElementById('share-btn');
  if (!btn) return;
  btn.addEventListener('click', async () => {
    const job = window.__SB_CURRENT_JOB || currentJob;
    if (!job) return;

    const original = btn.textContent;
    btn.textContent = '… publishing';
    btn.disabled = true;

    try {
      // Publish to gallery, get back canonical share_url. This is the
      // only way to guarantee /board/{slug} actually resolves.
      const resp = await fetch(`${API_BASE}/api/share`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ job_id: job }),
      });
      if (!resp.ok) {
        btn.textContent = '✗ Share failed';
        setTimeout(() => { btn.textContent = original; btn.disabled = false; }, 2200);
        return;
      }
      const { share_url } = await resp.json();

      if (navigator.share) {
        try {
          await navigator.share({
            title: 'My storyboard',
            text: 'Made with storyboard — a Hermes Agent skill',
            url: share_url,
          });
        } catch (err) {
          // User cancelled — silently fall back to clipboard
          if (navigator.clipboard) {
            await navigator.clipboard.writeText(share_url);
          }
        }
      } else if (navigator.clipboard) {
        await navigator.clipboard.writeText(share_url);
      }
      btn.textContent = '✓ Link copied';
      setTimeout(() => { btn.textContent = original; btn.disabled = false; }, 1800);
    } catch (err) {
      console.warn('share failed:', err);
      btn.textContent = '✗ Network error';
      setTimeout(() => { btn.textContent = original; btn.disabled = false; }, 2200);
    }
  });
})();

// =================== Inspect panel ===================

function showInspectPanel(jobId) {
  const panel = document.getElementById('inspect-panel');
  if (!panel) return;
  panel.hidden = false;
  panel.dataset.jobId = jobId;
  // Default to scene tab
  const firstTab = panel.querySelector('.inspect-tab.is-active');
  if (firstTab) loadInspectArtifact(jobId, firstTab.dataset.art);
}

function _highlightJSON(s) {
  // very small/safe pretty-printer-style highlighter; runs on already-stringified text
  return s
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/("(?:[^"\\]|\\.)*")(\s*:)/g, '<span class="ij-key">$1</span>$2')
    .replace(/: ("(?:[^"\\]|\\.)*")/g, ': <span class="ij-str">$1</span>')
    .replace(/\b(true|false)\b/g, '<span class="ij-bool">$1</span>')
    .replace(/\bnull\b/g, '<span class="ij-null">null</span>')
    .replace(/(:\s*)(-?\d+(?:\.\d+)?)/g, '$1<span class="ij-num">$2</span>');
}

async function loadInspectArtifact(jobId, artifact) {
  const body = document.getElementById('inspect-body');
  if (!body) return;
  body.innerHTML = '<code class="ij-comment">// loading…</code>';
  try {
    const url = `${API_BASE}/api/inspect/${jobId}/${artifact}`;
    const resp = await fetch(url);
    if (!resp.ok) {
      body.innerHTML = `<code class="ij-comment">// not produced for this job (HTTP ${resp.status})</code>`;
      return;
    }
    const ct = resp.headers.get('Content-Type') || '';
    const text = await resp.text();

    // Trace gets a custom column-aligned render — "agent workflow" feel
    if (artifact === 'trace') {
      try {
        const data = JSON.parse(text);
        body.innerHTML = _renderTrace(data.trace || []);
      } catch (err) {
        body.innerHTML = `<code class="ij-comment">// trace parse error</code>`;
      }
      return;
    }

    if (ct.includes('json')) {
      let pretty;
      try { pretty = JSON.stringify(JSON.parse(text), null, 2); }
      catch { pretty = text; }
      body.innerHTML = '<code>' + _highlightJSON(pretty) + '</code>';
    } else if (ct.includes('csv')) {
      body.innerHTML = '<code>' + text
        .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
        + '</code>';
    } else {
      const escaped = text.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
      body.innerHTML = '<code>' + escaped + '</code>';
    }
  } catch (err) {
    body.innerHTML = `<code class="ij-comment">// error: ${String(err).replace(/</g, '&lt;')}</code>`;
  }
}

function _renderTrace(steps) {
  // Format like:  01  parse scene        Kimi K2.5      812ms
  // Right-pad stage to 22, source to 18, ms right-aligned to 8.
  if (!steps.length) {
    return '<code class="ij-comment">// no trace events recorded yet</code>';
  }
  const pad = (s, n) => (s + ' '.repeat(Math.max(0, n - s.length))).slice(0, n);
  const padR = (s, n) => (' '.repeat(Math.max(0, n - s.length)) + s).slice(-n);
  const fmtMs = (ms) => ms >= 1000 ? `${(ms / 1000).toFixed(1)}s` : `${ms}ms`;

  const header =
    `<span class="tr-head">` +
    `${pad('  ', 4)}${pad('STAGE', 22)}${pad('SOURCE', 20)}${padR('LATENCY', 9)}` +
    `</span>\n` +
    `<span class="tr-rule">${'─'.repeat(54)}</span>\n`;
  const rows = steps.map((s, i) => {
    const num = String(i + 1).padStart(2, '0');
    const stage = pad(String(s.stage || ''), 22);
    const source = pad(String(s.source || ''), 20);
    const ms = padR(fmtMs(Number(s.ms || 0)), 9);
    const sourceClass = /kimi/i.test(s.source || '') ? 'tr-kimi' : 'tr-local';
    return (
      `<span class="tr-num">${num}</span>  ` +
      `<span class="tr-stage">${stage}</span>` +
      `<span class="${sourceClass}">${source}</span>` +
      `<span class="tr-ms">${ms}</span>` +
      (s.note ? `\n      <span class="tr-note"># ${String(s.note).replace(/</g, '&lt;')}</span>` : '')
    );
  }).join('\n');
  return '<code>' + header + rows + '</code>';
}

// Expose for direct invocation in test pages / dev console
if (typeof window !== 'undefined') {
  window._renderTrace = _renderTrace;
}

// Tab click handlers — wire up once at load
(function setupInspectTabs() {
  const panel = document.getElementById('inspect-panel');
  if (!panel) return;
  const tabs = panel.querySelectorAll('.inspect-tab');
  tabs.forEach((tab) => {
    tab.addEventListener('click', () => {
      tabs.forEach((t) => t.classList.remove('is-active'));
      tab.classList.add('is-active');
      const jobId = panel.dataset.jobId;
      if (jobId) loadInspectArtifact(jobId, tab.dataset.art);
    });
  });
})();

(function loadSharedBoard() {
  const params = new URLSearchParams(location.search);
  const slug = params.get('board');
  if (!slug || !slug.match(/^[a-z0-9]{1,32}$/i)) return;

  // Fetch the board PNG and scene JSON, render them in the output panel
  fetch(`${API_BASE}/api/gallery/${slug}/board.png`, { cache: 'force-cache' })
    .then((r) => {
      if (!r.ok) throw new Error('not found');
      boardEmpty.hidden = true;
      boardEl.hidden = false;
      boardEl.innerHTML = `<img src="${API_BASE}/api/gallery/${slug}/board.png"
        alt="shared storyboard" style="width:100%;display:block;">`;
      setStatus(`viewing shared board · ${slug}`, 'is-done');
      document.getElementById('try').scrollIntoView({ behavior: 'smooth' });
    })
    .catch(() => {
      // silent — keep page in normal state
    });
})();
