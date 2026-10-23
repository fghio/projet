/* ProJet GUI front-end */

const $ = sel => document.querySelector(sel);
const $$ = sel => Array.from(document.querySelectorAll(sel));

const state = {
  engine: 'turbojet',
  presets: {},
  configs: {},
  stash: {},          // remembered values of switched-off modes / toggles
  resp: null,         // last successful /api/run response
  baseline: null,
  seq: 0,
  timer: null,
};

/* ---------------- utilities ---------------- */
const clone = o => JSON.parse(JSON.stringify(o));
const getPath = (o, p) => p.reduce((a, k) => (a == null ? undefined : a[k]), o);
function setPath(o, p, v) {
  let t = o;
  p.slice(0, -1).forEach(k => { if (typeof t[k] !== 'object' || t[k] === null) t[k] = {}; t = t[k]; });
  t[p[p.length - 1]] = v;
}
function delPath(o, p) {
  const t = getPath(o, p.slice(0, -1));
  if (t) delete t[p[p.length - 1]];
}
const hasPath = (o, p) => getPath(o, p) !== undefined;
const cfg = () => state.configs[state.engine];

function fmt(v, d = 2) {
  if (v == null || !isFinite(v)) return '–';
  return Number(v).toLocaleString('en-US', { minimumFractionDigits: d, maximumFractionDigits: d });
}
function cssVar(name) { return getComputedStyle(document.documentElement).getPropertyValue(name).trim(); }

function storage(key, value) {
  try {
    if (value === undefined) return localStorage.getItem(key);
    localStorage.setItem(key, value);
  } catch (e) { return null; }
}

async function api(url, body) {
  const opts = body === undefined ? {} : { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) };
  const r = await fetch(url, opts);
  return r.json();
}

function download(name, text, type = 'text/plain') {
  const a = document.createElement('a');
  a.href = URL.createObjectURL(new Blob([text], { type }));
  a.download = name;
  a.click();
  setTimeout(() => URL.revokeObjectURL(a.href), 1000);
}

/* ---------------- engine switch ---------------- */
function renderEngineSwitch() {
  $('#engineSwitch').innerHTML = Object.entries(ENGINES).map(([k, e]) =>
    `<button data-engine="${k}" class="${k === state.engine ? 'active' : ''}" title="${e.label}">${ENGINE_ICONS[k]}<span>${e.label}</span></button>`
  ).join('');
  $$('#engineSwitch button').forEach(b => b.addEventListener('click', () => setEngine(b.dataset.engine)));
}

function setEngine(engine) {
  state.engine = engine;
  storage('projet.engine', engine);
  renderEngineSwitch();
  renderForm();
  runNow();
}

/* ---------------- form ---------------- */
function groupActive(g) {
  return !g.toggle || hasPath(cfg(), g.toggle.paths[0]);
}

function activeMode(g) {
  const opts = g.modes.options;
  return opts.find(o => hasPath(cfg(), o.field.path)) || opts[0];
}

function fieldHTML(f, disabled = false) {
  if (f.subhead) return `<div class="subhead">${f.subhead}</div>`;
  if (f.check) {
    const v = getPath(cfg(), f.check);
    return `<label class="check"><input type="checkbox" data-check="${f.check.join('.')}" ${v === true || v === 'True' ? 'checked' : ''}> ${f.label}</label>`;
  }
  const raw = getPath(cfg(), f.path);
  const scale = f.scale || 1;
  const val = raw === undefined ? '' : +(raw / scale).toPrecision(10);
  const optional = f.optional ? (raw === undefined) : false;
  let placeholder = f.def !== undefined ? +(f.def / scale).toPrecision(6) : '';
  if (f.optional && optional && state.resp && state.resp.results.propeller) {
    placeholder = fmt(state.resp.results.propeller.alpha_power, 4);
  }
  const step = f.step === 'any' ? 'any' : f.step;
  const isDisabled = disabled || optional;
  return `
    <div class="field ${isDisabled ? 'disabled' : ''}" ${f.help ? `title="${f.help}"` : ''}>
      <label><span class="lbl">${f.label}</span><span class="sym">${f.sym}</span></label>
      <div class="inp">
        <input type="number" step="${step}" data-path="${f.path.join('.')}" value="${val}" placeholder="${placeholder}" ${isDisabled ? 'disabled' : ''}>
        <span class="unit">${f.unit}</span>
      </div>
    </div>
    ${f.isa ? `<div class="row" style="justify-content:flex-end"><button class="btn small" data-isa>Fill T, p, ρ from ISA</button></div>` : ''}
    ${f.optional ? `<label class="check"><input type="checkbox" data-optional="${f.path.join('.')}" ${optional ? 'checked' : ''}> ${f.optional.label}</label>` : ''}`;
}

const allFields = () => {
  const out = {};
  for (const g of Object.values(GROUPS)) {
    (g.fields || []).forEach(f => f.path && (out[f.path.join('.')] = f));
    if (g.modes) g.modes.options.forEach(o => (out[o.field.path.join('.')] = o.field));
  }
  return out;
};
const FIELD_INDEX = allFields();

function renderForm() {
  const openState = {};
  $$('#form details').forEach(d => (openState[d.dataset.group] = d.open));

  const html = ENGINES[state.engine].groups.map(id => {
    const g = GROUPS[id];
    const active = groupActive(g);
    let body = '';
    if (g.toggle) {
      body += `<label class="check"><input type="checkbox" data-toggle="${id}" ${active ? 'checked' : ''}> ${g.toggle.label}</label>`;
    }
    if (active) {
      if (g.modes) {
        const m = activeMode(g);
        body += `<div class="seg" data-modes="${id}">${g.modes.options.map((o, i) =>
          `<button data-mode="${i}" class="${o === m ? 'active' : ''}">${o.label}</button>`).join('')}</div>`;
        body += fieldHTML(m.field);
      }
      body += g.fields.map(f => fieldHTML(f)).join('');
    }
    const open = openState[id] !== undefined ? openState[id] : !g.closed;
    return `<details class="group" data-group="${id}" ${open ? 'open' : ''}>
      <summary><span class="dot" style="background:${g.color}"></span>${g.title}${g.toggle && !active ? ' <span class="muted small">(off)</span>' : ''}</summary>
      <div class="group-body">${body}</div>
    </details>`;
  }).join('');
  $('#form').innerHTML = html;
  bindForm();
  markFields();
  refreshSweepParams();
}

function bindForm() {
  $$('#form input[data-path]').forEach(inp => {
    inp.addEventListener('input', () => {
      const path = inp.dataset.path.split('.');
      const f = FIELD_INDEX[inp.dataset.path];
      const box = inp.parentElement;
      if (inp.value.trim() === '') {
        if (f.def === undefined && !f.optional) { box.classList.add('invalid'); return; }
        delPath(cfg(), path);
        box.classList.remove('invalid');
      } else {
        const v = parseFloat(inp.value);
        if (!isFinite(v)) { box.classList.add('invalid'); return; }
        const outOfRange = (f.min !== undefined && v < f.min) || (f.max !== undefined && v > f.max);
        box.classList.toggle('invalid', outOfRange);
        setPath(cfg(), path, v * (f.scale || 1));
      }
      scheduleRun();
    });
  });

  $$('#form input[data-check]').forEach(inp => inp.addEventListener('change', () => {
    const path = inp.dataset.check.split('.');
    if (inp.checked) setPath(cfg(), path, true); else delPath(cfg(), path);
    runNow();
  }));

  $$('#form input[data-optional]').forEach(inp => inp.addEventListener('change', () => {
    const path = inp.dataset.optional.split('.');
    const f = FIELD_INDEX[inp.dataset.optional];
    if (inp.checked) {
      state.stash[inp.dataset.optional] = getPath(cfg(), path);
      delPath(cfg(), path);
    } else {
      const prev = state.stash[inp.dataset.optional];
      const fromResult = state.resp && state.resp.results.propeller ? +state.resp.results.propeller.alpha_power.toFixed(4) : undefined;
      setPath(cfg(), path, prev ?? fromResult ?? f.optional.value);
    }
    renderForm();
    runNow();
  }));

  $$('#form input[data-toggle]').forEach(inp => inp.addEventListener('change', () => {
    const g = GROUPS[inp.dataset.toggle];
    const key = `${state.engine}.${inp.dataset.toggle}`;
    if (inp.checked) {
      const saved = state.stash[key] || g.toggle.values;
      g.toggle.paths.forEach((p, i) => setPath(cfg(), p, clone(saved[i])));
    } else {
      state.stash[key] = g.toggle.paths.map(p => clone(getPath(cfg(), p) || {}));
      g.toggle.paths.forEach(p => delPath(cfg(), p));
    }
    renderForm();
    runNow();
  }));

  $$('#form [data-modes]').forEach(seg => seg.querySelectorAll('button').forEach(btn => btn.addEventListener('click', () => {
    const g = GROUPS[seg.dataset.modes];
    const target = g.modes.options[+btn.dataset.mode];
    const current = activeMode(g);
    if (target === current) return;
    const ck = current.field.path.join('.'), tk = target.field.path.join('.');
    state.stash[ck] = getPath(cfg(), current.field.path);
    delPath(cfg(), current.field.path);
    // start the new mode from the value the solver just computed, when available
    let v = state.stash[tk];
    if (v === undefined && state.resp) {
      const r = state.resp.results;
      const stName = seg.dataset.modes === 'combustor' ? 'Combustor' : 'PostCombustor';
      const s = r.stations.find(x => x.name === stName);
      if (s) v = target.field.path[2] === 'fuel_ratio' ? +s.fuel_ratio.toFixed(4) : Math.round(s.temperature);
    }
    setPath(cfg(), target.field.path, v ?? target.field.value);
    renderForm();
    runNow();
  })));

  $$('#form [data-isa]').forEach(btn => btn.addEventListener('click', async () => {
    const z = getPath(cfg(), ['flightConditions', 'altitude_km']);
    if (z === undefined) { flashBanner('warn', 'Enter an altitude first.'); return; }
    const a = await api(`/api/isa?altitude_km=${z}`);
    if (a.error) { flashBanner('warn', `ISA: ${a.error}.`); return; }
    setPath(cfg(), ['airProperties', 'temperature'], +a.temperature.toFixed(2));
    setPath(cfg(), ['airProperties', 'pressure'], +a.pressure.toFixed(1));
    setPath(cfg(), ['airProperties', 'density'], +a.density.toFixed(4));
    renderForm();
    runNow();
  }));
}

function focusGroup(id) {
  const el = $(`#form details[data-group="${id}"]`);
  if (!el) return;
  el.open = true;
  el.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
  el.classList.remove('flash');
  void el.offsetWidth;
  el.classList.add('flash');
  setTimeout(() => el.classList.remove('flash'), 1300);
  const first = el.querySelector('input[type=number]:not([disabled])');
  if (first) first.focus({ preventScroll: true });
}

/* ---------------- running ---------------- */
function scheduleRun() {
  clearTimeout(state.timer);
  state.timer = setTimeout(runNow, 250);
}

async function runNow() {
  clearTimeout(state.timer);
  const seq = ++state.seq;
  const rs = $('#runState');
  rs.textContent = 'computing…';
  rs.className = 'run-state busy';
  let r;
  try {
    r = await api('/api/run', cfg());
  } catch (e) {
    r = { ok: false, error: 'Cannot reach the ProJet server. Is projetGUI.py still running?' };
  }
  if (seq !== state.seq) return;

  if (!r.ok) {
    rs.textContent = 'error';
    rs.className = 'run-state error';
    showIssues(r.issues && r.issues.length ? r.issues : [{ level: 'error', message: r.error, path: [] }]);
    $$('.sol').forEach(e => e.classList.add('stale'));
    return;
  }
  const nWarn = r.issues.filter(i => i.level === 'warning').length;
  rs.textContent = nWarn ? `${nWarn} warning${nWarn > 1 ? 's' : ''}` : 'up to date';
  rs.className = nWarn ? 'run-state warn' : 'run-state';
  $$('.sol').forEach(e => e.classList.remove('stale'));
  r.engine = state.engine;
  state.resp = r;
  showIssues(r.issues);
  renderResults();
  // the optional α placeholder shows the computed optimum
  const opt = $('#form input[data-optional]');
  if (opt && opt.checked && r.results.propeller) {
    const inp = $(`#form input[data-path="${opt.dataset.optional}"]`);
    if (inp) inp.placeholder = fmt(r.results.propeller.alpha_power, 4);
  }
}

const ISSUE_ICON = { error: '⛔', warning: '⚠️', info: 'ℹ️' };

/* list errors / warnings in the banner and outline the inputs they refer to */
function showIssues(issues) {
  state.issues = issues || [];
  markFields();
  if (!state.issues.length) { hideBanner(); return; }
  const levels = state.issues.map(i => i.level);
  const kind = levels.includes('error') ? 'error' : levels.includes('warning') ? 'warn' : 'info';
  const b = $('#banner');
  b.className = `banner ${kind}`;
  b.innerHTML = `<ul class="issues">${state.issues.map((i, k) =>
    `<li class="${i.level}" data-k="${k}" ${i.path && i.path.length ? 'tabindex="0" title="Go to the input"' : ''}>
       <span>${ISSUE_ICON[i.level]}</span><span>${escapeHtml(i.message)}</span></li>`).join('')}</ul>`;
  b.hidden = false;
  b.querySelectorAll('li[tabindex]').forEach(li => li.addEventListener('click', () => focusPath(state.issues[+li.dataset.k].path)));
}

function escapeHtml(s) {
  return String(s).replace(/[&<>"]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
}

/* the input bound to a config path, or the first input of the same block */
function inputForPath(path) {
  if (!path || !path.length) return null;
  const key = path.join('.');
  return $(`#form input[data-path="${key}"]`) || $(`#form input[data-check="${key}"]`)
    || $$('#form input[data-path]').find(i => i.dataset.path.startsWith(key + '.'));
}

function markFields() {
  $$('#form .srv-error, #form .srv-warn').forEach(e => e.classList.remove('srv-error', 'srv-warn'));
  for (const i of state.issues || []) {
    if (i.level === 'info') continue;
    const inp = inputForPath(i.path);
    if (!inp) continue;
    const target = inp.dataset.path === i.path.join('.') ? (inp.closest('.inp') || inp.closest('label')) : inp.closest('details').querySelector('summary');
    if (!target || target.classList.contains('srv-error')) continue;
    target.classList.remove('srv-warn');
    target.classList.add(i.level === 'error' ? 'srv-error' : 'srv-warn');
  }
}

function focusPath(path) {
  const inp = inputForPath(path);
  if (!inp) return;
  const group = inp.closest('details');
  focusGroup(group.dataset.group);
  inp.focus({ preventScroll: true });
}

function showBanner(kind, text) {
  const b = $('#banner');
  b.className = `banner ${kind}`;
  b.textContent = text;
  b.hidden = false;
}
function hideBanner() { $('#banner').hidden = true; }
function flashBanner(kind, text) { showBanner(kind, text); setTimeout(hideBanner, 3000); }

/* ---------------- results ---------------- */
function derived(r) {
  const res = r.results;
  const fuel = res.stations.reduce((a, s) => a + (s.fuel_mass || 0), 0);
  const main = res.stations.find(s => s.name === 'Combustor');
  const ab = res.stations.find(s => s.name === 'PostCombustor');
  return {
    fuel,
    f: main ? main.fuel_ratio : null,
    fAB: ab ? ab.fuel_ratio : null,
    mdot: res.mass_flow_main + (r.engine === 'turboprop' ? 0 : res.mass_flow_secondary),
    bpr: r.engine.startsWith('turbofan') && res.mass_flow_main ? res.mass_flow_secondary / res.mass_flow_main : null,
  };
}

function deltaChip(cur, base, higherIsBetter) {
  if (base == null || cur == null || !isFinite(base) || base === 0) return '';
  const d = (cur - base) / Math.abs(base) * 100;
  if (Math.abs(d) < 0.05) return '<span class="delta">±0%</span>';
  const good = (d > 0) === higherIsBetter;
  return `<span class="delta ${good ? 'good' : 'bad'}">${d > 0 ? '+' : ''}${d.toFixed(1)}%</span>`;
}

function renderKPIs() {
  const r = state.resp, res = r.results, p = res.performance, D = derived(r);
  const b = state.baseline && state.baseline.engine === r.engine ? state.baseline : null;
  const bp = b ? b.results.performance : {}, bD = b ? derived(b) : {};
  const tp = r.engine === 'turboprop';

  const card = (color, label, value, unit, sub, delta = '') =>
    `<div class="kpi" style="--kc:${color}"><div class="k-label"><span>${label}</span>${delta}</div>
     <div class="k-value">${value}<span class="k-unit">${unit}</span></div><div class="k-sub">${sub}</div></div>`;

  const noz = res.mainNozzle;
  const nozKind = noz.onlyConvergent ? `<span class="badge">convergent · ${noz.mach < 0.999 ? 'not choked' : 'choked'}</span>`
    : noz.mach > 1.01 ? '<span class="badge hot">con-div required</span>' : '<span class="badge">convergent is enough</span>';

  let html = card('#2563eb', 'Thrust', fmt(p.thrust / 1000, 2), 'kN',
    tp ? 'propeller + jet' : `I<sub>a</sub> = ${fmt(p.impulse, 1)} m/s · ${fmt(p.impulse / 9.81, 1)} s`,
    b ? deltaChip(p.thrust, bp.thrust, true) : '');

  html += tp
    ? card('#7c3aed', 'BSFC', fmt(p.TSFC * 3600, 4), 'kg/(h·kW)', 'per equivalent shaft power', b ? deltaChip(p.TSFC, bp.TSFC, false) : '')
    : card('#7c3aed', 'TSFC', fmt(p.TSFC * 3600, 4), 'kg/(h·N)', `${fmt(p.TSFC * 1e6, 2)} g/(kN·s)`, b ? deltaChip(p.TSFC, bp.TSFC, false) : '');

  if (tp) {
    const pr = res.propeller;
    const auto = !hasPath(cfg(), ['components', 'propeller', 'alpha_power']);
    html += card('#a855f7', 'Turbine shaft power', fmt(pr.shaft_power / 1e6, 2), 'MW', `α = ${fmt(pr.alpha_power, 3)}${auto ? ' (optimal)' : ''}`,
      b && b.results.propeller ? deltaChip(pr.shaft_power, b.results.propeller.shaft_power, true) : '');
  }

  html += card('#0ea5e9', 'Air mass flow', fmt(D.mdot, 2), 'kg/s',
    r.engine.startsWith('turbofan') ? `core ${fmt(res.mass_flow_main, 2)} · bypass ${fmt(res.mass_flow_secondary, 2)}`
      : tp ? `propeller stream ${fmt(res.mass_flow_secondary, 1)} kg/s` : `u<sub>0</sub> = ${fmt(res.inlet_velocity, 1)} m/s`,
    b ? deltaChip(D.mdot, bD.mdot, true) : '');

  if (D.bpr != null) {
    html += card('#06b6d4', 'Bypass ratio', fmt(D.bpr, 3), '', r.engine === 'turbofan_AF' ? 'computed from LP power balance' : 'given',
      b ? deltaChip(D.bpr, bD.bpr, true) : '');
  }

  html += card('#ef4444', 'Fuel flow', fmt(D.fuel, 3), 'kg/s',
    `f = ${fmt(D.f, 4)}${D.fAB != null ? ` · f<sub>AB</sub> = ${fmt(D.fAB, 4)}` : ''}`, b ? deltaChip(D.fuel, bD.fuel, false) : '');

  html += card('#64748b', 'Nozzle exit', fmt(noz.mach, 2), 'Mach',
    `u<sub>e</sub> = ${fmt(noz.velocity, 0)} m/s ${nozKind}${res.secondaryNozzle ? `<br>bypass M = ${fmt(res.secondaryNozzle.mach, 2)}, u = ${fmt(res.secondaryNozzle.velocity, 0)} m/s` : ''}`);

  const meter = (lbl, v, c, bv) => `<div class="meter"><span>${lbl}</span><span class="bar"><i style="width:${Math.max(0, Math.min(1, v)) * 100}%;background:${c}"></i></span><b>${fmt(v, 3)}</b></div>`;
  html += `<div class="kpi" style="--kc:#059669"><div class="k-label"><span>Efficiencies</span>${b ? deltaChip(p.global, bp.global, true) : ''}</div>
    <div class="meters">${meter('η<sub>th</sub>', p.thermal, '#f97316')}${meter('η<sub>p</sub>', p.propulsive, '#0ea5e9')}${meter('η<sub>o</sub>', p.global, '#059669')}</div></div>`;

  $('#kpis').innerHTML = html;
}

function stationTip(s) {
  if (!s) return '';
  const kind = s.total ? 'total' : 'static';
  return `<b>${s.number} · ${s.name}</b>p<sub>${kind}</sub> = ${fmt(s.pressure / 1000, 2)} kPa<br>T<sub>${kind}</sub> = ${fmt(s.temperature, 1)} K<br>s − s₀ = ${fmt(s.entropy, 1)} J/(kg·K)` +
    (s.fuel_ratio != null ? `<br>f = ${fmt(s.fuel_ratio, 4)} · ṁ<sub>f</sub> = ${fmt(s.fuel_mass, 3)} kg/s` : '');
}

function tooltip(ev, html) {
  const t = $('#tooltip');
  if (!ev) { t.hidden = true; return; }
  t.innerHTML = html;
  t.hidden = false;
  const x = Math.min(ev.clientX + 14, window.innerWidth - t.offsetWidth - 8);
  t.style.left = `${x}px`;
  t.style.top = `${ev.clientY + 14}px`;
}

function renderStationsTable() {
  const res = state.resp.results;
  const temps = res.stations.map(s => s.temperature);
  const Tmin = Math.min(...temps), Tmax = Math.max(...temps);
  const rows = res.stations.map(s => {
    const c = heatColor((s.temperature - Tmin) / Math.max(1, Tmax - Tmin));
    return `<tr data-name="${s.name}">
      <td><span class="num" style="background:${c};color:${textOn(c)}">${s.number}</span></td>
      <td>${s.name}<span class="tag">${s.total ? 'total' : 'static'}</span></td>
      <td>${fmt(s.pressure / 1000, 2)}</td><td>${fmt(s.temperature, 1)}</td><td>${fmt(s.entropy, 1)}</td>
      <td>${s.fuel_ratio != null ? fmt(s.fuel_ratio, 4) : ''}</td></tr>`;
  }).join('');
  $('#stations').innerHTML = `<thead><tr><th>#</th><th>Station</th><th>p [kPa]</th><th>T [K]</th><th>s − s₀ [J/kgK]</th><th>f</th></tr></thead><tbody>${rows}</tbody>`;
  $$('#stations tbody tr').forEach(tr => {
    tr.addEventListener('mouseenter', () => $$(`.station[data-name="${tr.dataset.name}"]`).forEach(e => e.classList.add('hl')));
    tr.addEventListener('mouseleave', () => $$('.station.hl').forEach(e => e.classList.remove('hl')));
  });
}

/* ---------------- plots ---------------- */
const PLOT_CFG = { responsive: true, displaylogo: false, modeBarButtonsToRemove: ['lasso2d', 'select2d', 'autoScale2d'] };

function baseLayout(extra = {}) {
  const text = cssVar('--text'), grid = cssVar('--border'), muted = cssVar('--muted');
  const axis = { gridcolor: grid, zerolinecolor: grid, linecolor: grid, tickfont: { color: muted }, title: { font: { color: muted, size: 12 } } };
  return {
    paper_bgcolor: 'rgba(0,0,0,0)', plot_bgcolor: 'rgba(0,0,0,0)',
    font: { family: 'system-ui, sans-serif', color: text, size: 12 },
    margin: { l: 60, r: 20, t: 16, b: 50 },
    legend: { orientation: 'h', y: -0.18, font: { color: muted } },
    hoverlabel: { bgcolor: cssVar('--panel'), bordercolor: grid, font: { color: text } },
    xaxis: { ...axis, ...(extra.xaxis || {}) },
    yaxis: { ...axis, ...(extra.yaxis || {}) },
    ...(extra.yaxis2 ? { yaxis2: { ...axis, overlaying: 'y', side: 'right', showgrid: false, ...extra.yaxis2 } } : {}),
    ...Object.fromEntries(Object.entries(extra).filter(([k]) => !['xaxis', 'yaxis', 'yaxis2'].includes(k))),
  };
}

function isBypassSegment(engine, s) {
  return (engine === 'turbofan_SF' && s.name === 'Secondary nozzle');
}

function processPaths(r) {
  const res = r.results;
  const byName = Object.fromEntries(res.stations.map(s => [s.name, s]));
  const core = { x: [], y: [] }, bypass = { x: [], y: [] };
  const seg = (a, b, into) => {
    for (let i = 0; i <= 20; i++) {
      const t = i / 20;
      into.x.push(a.entropy + t * (b.entropy - a.entropy));
      into.y.push(a.temperature * Math.pow(b.temperature / a.temperature, t));
    }
    into.x.push(null); into.y.push(null);
  };
  for (const s of res.stations) {
    if (!s.parent) continue;
    seg(byName[s.parent], s, isBypassSegment(r.engine, s) ? bypass : core);
  }
  if (r.engine === 'turbofan_AF' && byName['Mixing zone']) seg(byName['Fan'], byName['Mixing zone'], bypass);
  return { core, bypass };
}

function isobar(s, gas, sFrom, sTo) {
  const xs = [], ys = [];
  for (let i = 0; i <= 40; i++) {
    const x = sFrom + (sTo - sFrom) * i / 40;
    xs.push(x);
    ys.push(s.temperature * Math.exp((x - s.entropy) / gas.cp_s));
  }
  return { xs, ys };
}

function renderTS() {
  const r = state.resp, res = r.results;
  const muted = cssVar('--muted'), accent = cssVar('--accent');
  const { core, bypass } = processPaths(r);
  const traces = [];

  // isobars through the key states
  const byName = Object.fromEntries(res.stations.map(s => [s.name, s]));
  const airSt = res.stations.filter(s => s.gas === 'air');
  const sAirMax = Math.max(...airSt.map(s => s.entropy));
  const pMaxAir = airSt.reduce((a, s) => (s.pressure > a.pressure ? s : a), airSt[0]);
  const exits = res.stations.filter(s => !s.total && s.number > 0);
  const isos = [
    { s: byName['Ambient'], from: -80, to: sAirMax + 200, label: 'p₀' },
    { s: pMaxAir, from: pMaxAir.entropy - 120, to: pMaxAir.entropy + 260, label: `p${pMaxAir.number}` },
    ...exits.filter(e => e.gas !== 'air').map(e => ({ s: e, from: e.entropy - 600, to: e.entropy + 80, label: 'p₀' })),
  ];
  const burner = byName['Combustor'];
  if (burner) isos.push({ s: burner, from: burner.entropy - 700, to: burner.entropy + 120, label: `p${burner.number}` });

  isos.forEach((iso, i) => {
    const { xs, ys } = isobar(iso.s, res.gases[iso.s.gas], iso.from, iso.to);
    traces.push({
      x: xs, y: ys, mode: 'lines', line: { color: muted, width: 1, dash: 'dot' }, hoverinfo: 'skip',
      name: 'isobars', legendgroup: 'iso', showlegend: i === 0,
    });
    traces.push({
      x: [xs[xs.length - 1]], y: [ys[ys.length - 1]], mode: 'text', text: [`${iso.label} = ${fmt(iso.s.pressure / 1000, 1)} kPa`],
      textposition: 'middle right', textfont: { color: muted, size: 10 }, hoverinfo: 'skip', showlegend: false, cliponaxis: false,
    });
  });

  const b = state.baseline && state.baseline.engine === r.engine ? state.baseline : null;
  if (b) {
    const bp = processPaths(b);
    traces.push({ x: bp.core.x.concat(bp.bypass.x), y: bp.core.y.concat(bp.bypass.y), mode: 'lines', name: 'baseline',
      line: { color: muted, width: 2, dash: 'dash' }, hoverinfo: 'skip', opacity: 0.7 });
  }

  traces.push({ x: core.x, y: core.y, mode: 'lines', name: r.engine.startsWith('turbofan') ? 'core flow' : 'cycle', line: { color: accent, width: 3 }, hoverinfo: 'skip' });
  if (bypass.x.length) {
    traces.push({ x: bypass.x, y: bypass.y, mode: 'lines', name: r.engine === 'turbofan_AF' ? 'bypass → mixer' : 'bypass flow',
      line: { color: '#06b6d4', width: 3, dash: r.engine === 'turbofan_AF' ? 'dash' : 'solid' }, hoverinfo: 'skip' });
  }

  const temps = res.stations.map(s => s.temperature);
  const Tmin = Math.min(...temps), Tmax = Math.max(...temps);
  traces.push({
    x: res.stations.map(s => s.entropy), y: temps, mode: 'markers+text', name: 'stations',
    text: res.stations.map(s => String(s.number)), textposition: 'top left', textfont: { size: 11, color: cssVar('--text') },
    marker: { size: 11, color: res.stations.map(s => heatColor((s.temperature - Tmin) / Math.max(1, Tmax - Tmin))), line: { color: cssVar('--panel'), width: 2 } },
    customdata: res.stations.map(s => [s.name, s.pressure / 1000, s.total ? 'total' : 'static']),
    hovertemplate: '<b>%{text} · %{customdata[0]}</b><br>T = %{y:.1f} K (%{customdata[2]})<br>p = %{customdata[1]:.2f} kPa<br>s − s₀ = %{x:.1f} J/(kg·K)<extra></extra>',
    showlegend: false,
  });

  Plotly.react('tsPlot', traces, baseLayout({
    xaxis: { title: { text: 's − s₀  [J/(kg·K)]' } },
    yaxis: { title: { text: 'T  [K]' } },
    margin: { l: 60, r: 100, t: 10, b: 50 },
  }), PLOT_CFG);
}

function renderProfiles() {
  const res = state.resp.results;
  const st = res.stations.slice().sort((a, b) => a.number - b.number);
  const labels = st.map(s => `${s.number} ${s.name.replace('Turbine LP | Propeller', 'LPT | Prop').replace('Air at entrance', 'Entry')}`);
  Plotly.react('profilePlot', [
    { type: 'bar', x: labels, y: st.map(s => s.pressure / 1000), name: 'p [kPa]', marker: { color: cssVar('--accent'), opacity: 0.75 },
      customdata: st.map(s => (s.total ? 'total' : 'static')), hovertemplate: 'p = %{y:.2f} kPa (%{customdata})<extra></extra>' },
    { type: 'scatter', mode: 'lines+markers', x: labels, y: st.map(s => s.temperature), name: 'T [K]', yaxis: 'y2',
      line: { color: '#f97316', width: 3, shape: 'spline' }, marker: { size: 8 },
      customdata: st.map(s => (s.total ? 'total' : 'static')), hovertemplate: 'T = %{y:.1f} K (%{customdata})<extra></extra>' },
  ], baseLayout({
    yaxis: { title: { text: 'pressure  [kPa]' } },
    yaxis2: { title: { text: 'temperature  [K]' } },
    margin: { l: 60, r: 60, t: 10, b: 90 },
    legend: { orientation: 'h', y: 1.08, x: 0 },
    bargap: 0.35,
  }), PLOT_CFG);
}

function renderEnergy() {
  const p = state.resp.results.performance;
  const MW = v => v / 1e6;
  const jet = p.propulsivePower + p.dissipatedPower;
  const thermalLoss = Math.max(0, p.availablePower - jet);
  const muted = cssVar('--muted');
  Plotly.react('sankeyPlot', [{
    type: 'sankey', arrangement: 'snap', valueformat: '.2f', valuesuffix: ' MW',
    node: {
      label: ['Fuel power', 'Jet kinetic power', 'Thermal losses (heat in exhaust)', 'Propulsive power', 'Residual kinetic energy'],
      color: ['#ef4444', '#f97316', '#94a3b8', '#059669', '#cbd5e1'],
      pad: 22, thickness: 18, line: { width: 0 },
    },
    link: {
      source: [0, 0, 1, 1], target: [1, 2, 3, 4],
      value: [MW(jet), MW(thermalLoss), MW(p.propulsivePower), MW(p.dissipatedPower)],
      color: ['rgba(249,115,22,.35)', 'rgba(148,163,184,.3)', 'rgba(5,150,105,.35)', 'rgba(203,213,225,.35)'],
    },
    textfont: { color: cssVar('--text'), size: 12 },
  }], baseLayout({ margin: { l: 10, r: 10, t: 10, b: 10 }, font: { color: muted } }), PLOT_CFG);

  $('#effChain').innerHTML = `
    <div class="eq">
      <span class="box">${fmt(p.thermal, 3)}<small>η<sub>th</sub> thermal</small></span> ×
      <span class="box">${fmt(p.propulsive, 3)}<small>η<sub>p</sub> propulsive</small></span> =
      <span class="box"><b>${fmt(p.global, 3)}</b><small>η<sub>o</sub> overall</small></span>
    </div>
    <div class="pw">
      <span>Fuel power ṁ<sub>f</sub>·LHV</span><b>${fmt(MW(p.availablePower), 2)} MW</b>
      <span>Propulsive power T·u<sub>0</sub></span><b>${fmt(MW(p.propulsivePower), 2)} MW</b>
      <span>Kinetic energy left in the jet</span><b>${fmt(MW(p.dissipatedPower), 2)} MW</b>
      <span>Heat rejected with the exhaust</span><b>${fmt(MW(thermalLoss), 2)} MW</b>
    </div>
    <p class="hint">η<sub>th</sub> = (P<sub>p</sub> + P<sub>d</sub>) / P<sub>f</sub> · η<sub>p</sub> = P<sub>p</sub> / (P<sub>p</sub> + P<sub>d</sub>)</p>`;
}

const PLOTS = ['tsPlot', 'profilePlot', 'sankeyPlot'];

function plotlyMissing() {
  if (window.Plotly) return false;
  PLOTS.forEach(id => {
    document.getElementById(id).innerHTML =
      '<p class="hint">Charts unavailable: plotly.js could not be loaded. Install plotly for the Python running ProJet ' +
      '(<code>pip install plotly</code>) or check the internet connection, then reload.</p>';
  });
  return true;
}

function renderResults() {
  const r = state.resp;
  // each view is independent: a failure in one must not blank the others
  const safely = (name, fn) => {
    try { fn(); } catch (e) { console.error(`${name}:`, e); }
  };
  safely('kpis', renderKPIs);
  safely('schematic', () => {
    const range = renderSchematic($('#schematic'), r.engine, cfg(), r.results, {
      onComponent: focusGroup, onHover: tooltip, stationTip,
    });
    $('#tmin').textContent = fmt(range.Tmin, 0);
    $('#tmax').textContent = fmt(range.Tmax, 0);
  });
  safely('stations', renderStationsTable);
  $('#examText').textContent = r.exam.text;
  $('#examData').textContent = r.exam.data;
  $('#console').textContent = r.console;
  if (plotlyMissing()) return;
  safely('T-s', renderTS);
  safely('profiles', renderProfiles);
  safely('energy', renderEnergy);
  safely('sweep', updateSweepMarker);
}

/* ---------------- sweep ---------------- */
function sweepableFields() {
  const out = [];
  for (const id of ENGINES[state.engine].groups) {
    const g = GROUPS[id];
    if (!groupActive(g)) continue;
    const list = [];
    if (g.modes) list.push(activeMode(g).field);
    g.fields.forEach(f => f.path && list.push(f));
    list.filter(f => f.sweep !== false && !(f.optional && !hasPath(cfg(), f.path)))
      .forEach(f => out.push({ f, group: g.title }));
  }
  return out;
}

function refreshSweepParams() {
  const sel = $('#sweepParam');
  const prev = sel.value;
  sel.innerHTML = sweepableFields().map(({ f, group }) =>
    `<option value="${f.path.join('.')}">${group} — ${f.label} (${f.sym})</option>`).join('');
  const preferred = ['components.compressor.pressure_ratio'];
  if ([...sel.options].some(o => o.value === prev)) { sel.value = prev; return; }
  if ([...sel.options].some(o => o.value === preferred[0])) sel.value = preferred[0];
  setSweepRange();
}

function setSweepRange() {
  const key = $('#sweepParam').value;
  if (!key) return;
  const f = FIELD_INDEX[key];
  const scale = f.scale || 1;
  let v = getPath(cfg(), key.split('.'));
  if (v === undefined) v = f.def !== undefined ? f.def : 1;
  v /= scale;
  let lo, hi;
  if (f.max === 1) { lo = Math.max(0.5, +(v - 0.15).toFixed(3)); hi = 1; }
  else { lo = +(v * 0.5).toPrecision(3); hi = +(v * 1.5).toPrecision(3); if (f.min !== undefined) lo = Math.max(f.min, lo); }
  $('#sweepFrom').value = lo;
  $('#sweepTo').value = hi;
}

let lastSweep = null;

async function runSweep() {
  const key = $('#sweepParam').value;
  if (!key) return;
  const f = FIELD_INDEX[key];
  const scale = f.scale || 1;
  const a = parseFloat($('#sweepFrom').value), b = parseFloat($('#sweepTo').value);
  const n = Math.max(3, Math.min(200, parseInt($('#sweepN').value, 10) || 25));
  if (!isFinite(a) || !isFinite(b)) return;
  const values = Array.from({ length: n }, (_, i) => (a + (b - a) * i / (n - 1)) * scale);
  if (!window.Plotly) { flashBanner('warn', 'Charts unavailable: plotly.js could not be loaded.'); return; }
  const btn = $('#btnSweep');
  btn.disabled = true; btn.textContent = 'Running…';
  try {
    const r = await api('/api/sweep', { config: cfg(), path: key.split('.'), values });
    const good = r.points.filter(p => p.thrust != null);
    lastSweep = { key, f, points: good.map(p => ({ ...p, x: p.x / scale })), engine: state.engine };
    plotSweep();
    const skipped = r.points.filter(p => p.thrust == null);
    $('#sweepNote').textContent = skipped.length
      ? `${skipped.length} of ${r.points.length} points skipped (not physical), e.g. at ${fmt(skipped[0].x / scale, 3)}: ${skipped[0].error.split('\n')[0]}`
      : `${good.length} points computed.`;
  } finally {
    btn.disabled = false; btn.textContent = 'Run sweep';
  }
}

function sweepMarkerShapes() {
  if (!lastSweep || lastSweep.engine !== state.engine) return [];
  const v = getPath(cfg(), lastSweep.key.split('.'));
  if (v === undefined) return [];
  return [{ type: 'line', xref: 'x', yref: 'paper', x0: v / (lastSweep.f.scale || 1), x1: v / (lastSweep.f.scale || 1), y0: 0, y1: 1,
    line: { color: cssVar('--muted'), dash: 'dot', width: 1.5 } }];
}

function plotSweep() {
  if (!lastSweep) return;
  const { f, points } = lastSweep;
  const xs = points.map(p => p.x);
  const xTitle = `${f.label} ${f.sym} [${f.unit}]`;
  const tp = lastSweep.engine === 'turboprop';
  const shapes = sweepMarkerShapes();
  Plotly.react('sweepPlot1', [
    { x: xs, y: points.map(p => p.thrust / 1000), name: 'Thrust [kN]', mode: 'lines+markers', line: { color: '#2563eb', width: 3 }, marker: { size: 5 } },
    { x: xs, y: points.map(p => p.TSFC * 3600), name: tp ? 'BSFC [kg/(h·kW)]' : 'TSFC [kg/(h·N)]', yaxis: 'y2', mode: 'lines+markers', line: { color: '#7c3aed', width: 3 }, marker: { size: 5 } },
  ], baseLayout({
    xaxis: { title: { text: xTitle } }, yaxis: { title: { text: 'thrust [kN]' } }, yaxis2: { title: { text: tp ? 'BSFC' : 'TSFC' } },
    margin: { l: 60, r: 60, t: 10, b: 50 }, legend: { orientation: 'h', y: 1.1 }, shapes,
  }), PLOT_CFG);

  const t2 = [
    { x: xs, y: points.map(p => p.thermal), name: 'η th', mode: 'lines', line: { color: '#f97316', width: 3 } },
    { x: xs, y: points.map(p => p.propulsive), name: 'η p', mode: 'lines', line: { color: '#0ea5e9', width: 3 } },
    { x: xs, y: points.map(p => p.global), name: 'η o', mode: 'lines', line: { color: '#059669', width: 3 } },
    { x: xs, y: points.map(p => p.mach), name: 'nozzle Mach', yaxis: 'y2', mode: 'lines', line: { color: '#64748b', width: 2, dash: 'dot' } },
  ];
  if (lastSweep.engine === 'turbofan_AF') t2.push({ x: xs, y: points.map(p => p.BPR), name: 'BPR', yaxis: 'y2', mode: 'lines', line: { color: '#06b6d4', width: 2, dash: 'dash' } });
  Plotly.react('sweepPlot2', t2, baseLayout({
    xaxis: { title: { text: xTitle } }, yaxis: { title: { text: 'efficiency' }, rangemode: 'tozero' }, yaxis2: { title: { text: lastSweep.engine === 'turbofan_AF' ? 'Mach · BPR' : 'Mach' } },
    margin: { l: 60, r: 60, t: 10, b: 50 }, legend: { orientation: 'h', y: 1.1 }, shapes,
  }), PLOT_CFG);
}

function updateSweepMarker() {
  if (!lastSweep || lastSweep.engine !== state.engine) return;
  const shapes = sweepMarkerShapes();
  ['sweepPlot1', 'sweepPlot2'].forEach(id => { const el = document.getElementById(id); if (el.data) Plotly.relayout(el, { shapes }); });
}

/* ---------------- misc actions ---------------- */
function stationsCSV() {
  const res = state.resp.results;
  const lines = ['station,name,kind,p_Pa,T_K,s_J_kgK,fuel_ratio,fuel_mass_kg_s'];
  res.stations.forEach(s => lines.push([s.number, `"${s.name}"`, s.total ? 'total' : 'static', s.pressure, s.temperature, s.entropy, s.fuel_ratio ?? '', s.fuel_mass ?? ''].join(',')));
  return lines.join('\n');
}

function setExamMode(on) {
  document.body.classList.toggle('exam-mode', on);
  $('#examMode').checked = on;
  $('#btnReveal').hidden = !on;
}

function applyTheme(theme) {
  document.documentElement.dataset.theme = theme;
  storage('projet.theme', theme);
  if (state.resp) renderResults();
  if (window.Plotly) plotSweep();
}

function bindGlobal() {
  $('#btnPreset').addEventListener('click', () => {
    state.configs[state.engine] = clone(state.presets[state.engine]);
    renderForm(); runNow();
  });

  $('#fileImport').addEventListener('change', async ev => {
    const file = ev.target.files[0];
    if (!file) return;
    const text = await file.text();
    ev.target.value = '';
    const r = await api('/api/parse', { text });
    if (!r.ok) { showBanner('error', `Import failed: ${r.error}`); return; }
    state.configs[r.config.engineType] = r.config;
    flashBanner('warn', `Loaded "${file.name}" (${ENGINES[r.config.engineType].label}).`);
    setEngine(r.config.engineType);
  });

  $('#btnExport').addEventListener('click', async () => {
    const r = await api('/api/export', cfg());
    download('input', r.text);
  });

  $('#btnBaseline').addEventListener('click', () => {
    const btn = $('#btnBaseline');
    if (state.baseline) {
      state.baseline = null;
      btn.textContent = '📌 Set baseline'; btn.classList.remove('on');
    } else if (state.resp) {
      state.baseline = clone(state.resp);
      btn.textContent = '📌 Clear baseline'; btn.classList.add('on');
    }
    if (state.resp) renderResults();
  });

  $('#examMode').addEventListener('change', e => setExamMode(e.target.checked));
  $('#btnReveal').addEventListener('click', () => setExamMode(false));

  $('#btnTheme').addEventListener('click', () => applyTheme(document.documentElement.dataset.theme === 'dark' ? 'light' : 'dark'));

  $('#btnCsv').addEventListener('click', () => state.resp && download(`projet_${state.engine}_stations.csv`, stationsCSV(), 'text/csv'));

  $$('#tabs button').forEach(b => b.addEventListener('click', () => {
    $$('#tabs button').forEach(x => x.classList.toggle('active', x === b));
    $$('.tab-panel').forEach(p => p.classList.toggle('active', p.dataset.panel === b.dataset.tab));
    // plots drawn while hidden need a resize
    $$(`.tab-panel[data-panel="${b.dataset.tab}"] .js-plotly-plot`).forEach(el => Plotly.Plots.resize(el));
  }));

  $$('[data-copy]').forEach(b => b.addEventListener('click', async () => {
    const text = `${$('#examText').textContent}\n\n${$('#examData').textContent}`;
    try { await navigator.clipboard.writeText(text); b.textContent = 'Copied ✓'; } catch (e) { b.textContent = 'Copy failed'; }
    setTimeout(() => (b.textContent = 'Copy text'), 1500);
  }));

  $('#btnExamDownload').addEventListener('click', () => {
    if (!state.resp) return;
    const r = state.resp;
    download(`esercizio_${state.engine}.txt`, `${r.exam.text}\n\n${r.exam.data}\n\n\n===================== SOLUZIONE =====================\n${r.console}`);
  });

  $('#sweepParam').addEventListener('change', setSweepRange);
  $('#btnSweep').addEventListener('click', runSweep);
}

/* ---------------- boot ---------------- */
async function init() {
  const params = new URLSearchParams(location.search);
  const theme = params.get('theme') || storage('projet.theme') || (matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light');
  document.documentElement.dataset.theme = theme;

  bindGlobal();
  state.presets = await api('/api/presets');
  state.configs = clone(state.presets);
  const saved = params.get('engine') || storage('projet.engine');
  state.engine = saved && ENGINES[saved] && state.presets[saved] ? saved : 'turbojet';
  renderEngineSwitch();
  renderForm();
  runNow();
}

init();
