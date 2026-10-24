/* Engine flow-path schematic (inline SVG) coloured by total temperature. */

const HEAT_STOPS = ['#3b82f6', '#22d3ee', '#facc15', '#f97316', '#dc2626'];

function hexToRgb(h) {
  const n = parseInt(h.slice(1), 16);
  return [(n >> 16) & 255, (n >> 8) & 255, n & 255];
}

function heatColor(t) {
  t = Math.min(1, Math.max(0, isFinite(t) ? t : 0));
  const pos = t * (HEAT_STOPS.length - 1);
  const i = Math.min(HEAT_STOPS.length - 2, Math.floor(pos));
  const f = pos - i;
  const a = hexToRgb(HEAT_STOPS[i]), b = hexToRgb(HEAT_STOPS[i + 1]);
  const c = a.map((v, k) => Math.round(v + (b[k] - v) * f));
  return `rgb(${c[0]},${c[1]},${c[2]})`;
}

function textOn(rgb) {
  const [r, g, b] = rgb.match(/\d+/g).map(Number);
  return (0.299 * r + 0.587 * g + 0.114 * b) > 150 ? '#0f172a' : '#ffffff';
}

/* Thrust-chamber contour in throat radii: cylindrical chamber (contraction ratio 3),
 * 30° convergent cone, bell divergent (80% of a 15° cone, 30° at the throat, 10° at the exit).
 * Only the exit radius √ε comes from the solver: the rest is a representative shape. */
function rocketContour(eps) {
  const rad = Math.PI / 180;
  const Rc = Math.sqrt(3), Lc = 3, Lconv = (Rc - 1) / Math.tan(30 * rad);
  const Re = Math.sqrt(eps), Ln = 0.8 * (Re - 1) / Math.tan(15 * rad);
  const tn = Math.tan(30 * rad), te = Math.tan(10 * rad);
  const xq = (Re - 1 - te * Ln) / (tn - te);       // control point: tangents at throat and exit
  const pts = [{ x: -Lc - Lconv, r: Rc, part: 'chamber' }, { x: -Lconv, r: Rc, part: 'chamber' }];
  for (let i = 1; i <= 12; i++) pts.push({ x: -Lconv + Lconv * i / 12, r: Rc - (Rc - 1) * i / 12, part: 'convergent' });
  for (let i = 1; i <= 40; i++) {
    const t = i / 40;
    pts.push({ x: 2 * (1 - t) * t * xq + t * t * Ln, r: (1 - t) ** 2 + 2 * (1 - t) * t * (1 + tn * xq) + t * t * Re, part: 'divergent' });
  }
  return { pts, Rc, Re, Lc, Lconv, Ln };
}

/* Mach number from A/A* on the subsonic or supersonic branch (bisection) */
function machFromArea(ratio, g, supersonic) {
  const f = M => 1 / M * Math.pow(2 / (g + 1) * (1 + (g - 1) / 2 * M * M), (g + 1) / (2 * (g - 1)));
  if (ratio <= 1) return 1;
  let lo = supersonic ? 1 : 1e-6, hi = supersonic ? 2 : 1;
  if (supersonic) while (f(hi) < ratio) hi *= 2;
  for (let i = 0; i < 100; i++) {
    const m = (lo + hi) / 2;
    if ((f(m) < ratio) === supersonic) lo = m; else hi = m;
  }
  return (lo + hi) / 2;
}

/* Layout of the engine: blocks (symmetric about the axis), bypass bands and station markers. */
function engineLayout(engine, cfg, res) {
  const st = Object.fromEntries(res.stations.map(s => [s.name, s]));
  const comps = cfg.components;
  const hasAB = 'postCombustor' in comps;
  const mainNoz = res.mainNozzle || {};
  const conDiv = noz => noz && noz.mach > 1.01 && !noz.onlyConvergent;

  const blocks = [];
  let x = 40;
  const add = (id, label, group, w, hIn, hOut, inSt, outSt, kind = 'duct', extra = {}) => {
    blocks.push({ id, label, group, x0: x, x1: x + w, hIn, hOut, inSt, outSt, kind, ...extra });
    x += w;
  };
  const bands = [];
  const extras = [];

  if (engine === 'turboprop') {
    extras.push({ kind: 'propeller', x: 46, h: 112, group: 'propeller' });
    x = 100;
  }

  if (engine === 'turbojet') {
    add('intake', 'Intake', 'intake', 80, 64, 58, 'Air at entrance', 'Intake');
    add('comp', 'Compressor', 'compressor', 170, 58, 32, 'Intake', 'Compressor', 'comp');
    add('burner', 'Combustor', 'combustor', 120, 32, 32, 'Compressor', 'Combustor', 'burner');
    add('turb', 'Turbine', 'turbine', 90, 32, 46, 'Combustor', 'Turbine HP', 'turb');
    let last = 'Turbine HP';
    if (hasAB) { add('ab', 'Afterburner', 'afterburner', 130, 46, 46, last, 'PostCombustor', 'ab'); last = 'PostCombustor'; }
    add('noz', 'Nozzle', 'nozzle', 90, 46, conDiv(mainNoz) ? 42 : 30, last, 'Nozzle', 'nozzle', { conDiv: conDiv(mainNoz), noz: mainNoz });
  }

  if (engine === 'turbofan_SF' || engine === 'turbofan_AF') {
    const SF = engine === 'turbofan_SF';
    add('intake', 'Intake', 'intake', 60, 112, 108, 'Air at entrance', 'Intake');
    add('fan', 'Fan', SF ? 'fanBPR' : 'fan', 50, 108, 108, 'Intake', 'Fan', 'comp');
    const xSplit = x;
    add('comp', 'Compressor', 'compressor', 150, 46, 28, 'Fan', 'Compressor', 'comp');
    add('burner', 'Combustor', 'combustor', 100, 28, 28, 'Compressor', 'Combustor', 'burner');
    add('hpt', 'HPT', 'turbineHigh', 60, 28, 34, 'Combustor', 'Turbine HP', 'turb');
    add('lpt', 'LPT', 'turbineLow', 80, 34, 46, 'Turbine HP', 'Turbine LP', 'turb');

    if (SF) {
      const xEnd = xSplit + 330;
      bands.push({ id: 'bypass', group: 'nozzlesSF', x0: xSplit, x1: xEnd, rIn: 52, rOut0: 108, rOut1: 82,
                   inSt: 'Fan', outSt: 'Secondary nozzle', noz: res.secondaryNozzle });
      add('noz', 'Core nozzle', 'nozzlesSF', 80, 46, conDiv(mainNoz) ? 40 : 30, 'Turbine LP', 'Main nozzle', 'nozzle', { conDiv: conDiv(mainNoz), noz: mainNoz });
    } else {
      bands.push({ id: 'bypass', group: 'fan', x0: xSplit, x1: x, rIn: 52, rOut0: 108, rOut1: 108, inSt: 'Fan', outSt: 'Fan' });
      add('mix', 'Mixer', null, 80, 108, 92, 'Turbine LP', 'Mixing zone', 'mix');
      let last = 'Mixing zone';
      if (hasAB) { add('ab', 'Afterburner', 'afterburner', 120, 92, 92, last, 'PostCombustor', 'ab'); last = 'PostCombustor'; }
      add('noz', 'Nozzle', 'nozzle', 90, 92, conDiv(mainNoz) ? 80 : 62, last, 'Nozzle', 'nozzle', { conDiv: conDiv(mainNoz), noz: mainNoz });
    }
  }

  if (engine === 'turboprop') {
    add('intake', 'Intake', 'intake', 60, 44, 40, 'Air at entrance', 'Intake');
    add('comp', 'Compressor', 'compressor', 140, 40, 24, 'Intake', 'Compressor', 'comp');
    add('burner', 'Combustor', 'combustor', 100, 24, 24, 'Compressor', 'Combustor', 'burner');
    add('hpt', 'HPT', 'turbineHigh', 60, 24, 30, 'Combustor', 'Turbine HP', 'turb');
    add('lpt', 'LPT', 'turbineLow', 70, 30, 38, 'Turbine HP', 'Turbine LP | Propeller', 'turb');
    add('noz', 'Nozzle', 'nozzle', 70, 38, conDiv(mainNoz) ? 34 : 28, 'Turbine LP | Propeller', 'Nozzle', 'nozzle', { conDiv: conDiv(mainNoz), noz: mainNoz });
  }

  // station markers on the axis at block boundaries
  const markers = [];
  const seen = new Set();
  const mark = (name, mx, my) => {
    if (!st[name] || seen.has(name)) return;
    seen.add(name);
    markers.push({ s: st[name], x: mx, y: my });
  };
  blocks.forEach((b, i) => {
    if (i === 0) mark(b.inSt, b.x0, 0);
    mark(b.outSt, b.x1, 0);
  });
  bands.forEach(b => { if (b.outSt !== b.inSt) mark(b.outSt, b.x1, -(b.rIn + b.rOut1) / 2); });

  return { blocks, bands, extras, markers, width: x + 120, st };
}

function bladeLines(x0, x1, hIn, hOut, A, spacing) {
  let d = '';
  for (let xx = x0 + spacing / 2; xx < x1; xx += spacing) {
    const h = hIn + (hOut - hIn) * (xx - x0) / (x1 - x0) - 4;
    d += `M${xx.toFixed(1)} ${(A - h).toFixed(1)}V${(A + h).toFixed(1)}`;
  }
  return d;
}

/* hover and click behaviour shared by the schematics */
function bindSchematic(container, stations, handlers) {
  container.querySelectorAll('.block').forEach(el => {
    el.addEventListener('click', () => el.dataset.group && handlers.onComponent(el.dataset.group));
    el.addEventListener('mousemove', ev => handlers.onHover(ev, `<b>${el.dataset.label}</b>${el.dataset.group ? 'click to edit inputs' : 'no inputs'}`));
    el.addEventListener('mouseleave', () => handlers.onHover(null));
  });
  container.querySelectorAll('.station').forEach(el => {
    const s = stations[el.dataset.name];
    el.addEventListener('mousemove', ev => handlers.onHover(ev, handlers.stationTip(s)));
    el.addEventListener('mouseleave', () => handlers.onHover(null));
  });
}

function stationMarker(s, x, y, color, scale = 1) {
  return `<g class="station" data-name="${s.name}" transform="translate(${x} ${y}) scale(${scale})">
      <circle r="11" fill="${color}" stroke="var(--panel)" stroke-width="2.5"/>
      <text text-anchor="middle" dy="4" font-size="11" font-weight="700" fill="${textOn(color)}">${s.number}</text>
    </g>`;
}

/* Thrust chamber drawn to scale from the area ratio, coloured by the isentropic temperature. */
function renderRocketSchematic(container, res, handlers) {
  const st = Object.fromEntries(res.stations.map(s => [s.name, s]));
  const temps = res.stations.map(s => s.temperature).filter(isFinite);
  const Tmin = Math.min(...temps), Tmax = Math.max(...temps);
  const col = T => heatColor((T - Tmin) / Math.max(1, Tmax - Tmin));
  const noz = res.mainNozzle, g = res.gases.hot.gamma, Tc = st['Chamber'].temperature;

  const C = rocketContour(noz.area_ratio);
  const k = 90 / Math.max(C.Rc, C.Re);                  // px per throat radius
  const x0 = 70 - C.pts[0].x * k, A = 90 + 40;          // throat at x0, axis at A
  const X = x => x0 + x * k;
  const xEnd = X(C.Ln), plumeLen = 140;
  const W = xEnd + plumeLen + 150, H = 2 * 90 + 100;

  // temperature along the wall (isentropic), as gradient stops over the whole length
  const xFirst = C.pts[0].x, xLast = C.Ln;
  const stops = C.pts.filter((q, i) => i % 3 === 0 || i === C.pts.length - 1).map(q => {
    const m = machFromArea(q.r * q.r, g, q.part === 'divergent');
    const T = Tc / (1 + (g - 1) / 2 * m * m);
    return `<stop offset="${((q.x - xFirst) / (xLast - xFirst)).toFixed(4)}" stop-color="${col(T)}"/>`;
  }).join('');
  let defs = `<linearGradient id="rk-flow" gradientUnits="userSpaceOnUse" x1="${X(xFirst)}" x2="${X(xLast)}" y1="0" y2="0">${stops}</linearGradient>`;

  const half = (pts, sgn) => pts.map(q => `${X(q.x).toFixed(1)} ${(A - sgn * q.r * k).toFixed(1)}`);
  const region = pts => `M${half(pts, 1).join('L')}L${half(pts.slice().reverse(), -1).join('L')}Z`;
  const chamberPts = C.pts.filter(q => q.part === 'chamber');
  const nozzlePts = [chamberPts[chamberPts.length - 1], ...C.pts.filter(q => q.part !== 'chamber')];

  // plume: contracts when over-expanded, widens when under-expanded
  const pe = noz.exit_pressure, pa = res.ambient_pressure;
  const re = C.Re * k;
  const spread = Math.min(pa > 0 ? Math.max(0.55, Math.pow(pe / pa, 0.25)) : 1.6, 1.6, 110 / re);
  defs += `<linearGradient id="rk-plume" x1="0" x2="1"><stop offset="0" stop-color="${col(st['Nozzle exit'].temperature)}" stop-opacity=".6"/>
    <stop offset="1" stop-color="${col(st['Nozzle exit'].temperature)}" stop-opacity="0"/></linearGradient>`;
  let body = `<path d="M${xEnd} ${A - re}Q${xEnd + plumeLen * 0.5} ${A - re * (1 + spread) / 2} ${xEnd + plumeLen} ${A - re * spread}
    L${xEnd + plumeLen} ${A + re * spread}Q${xEnd + plumeLen * 0.5} ${A + re * (1 + spread) / 2} ${xEnd} ${A + re}Z" fill="url(#rk-plume)"/>`;

  const injX = X(chamberPts[0].x);
  body += `<g class="block" data-group="rocketChamber" data-label="Combustion chamber">
      <path d="${region(chamberPts)}" fill="url(#rk-flow)"/>
      <rect x="${injX - 12}" y="${A - C.Rc * k - 4}" width="12" height="${2 * C.Rc * k + 8}" rx="3" fill="var(--shaft)"/>
    </g>
    <g class="block" data-group="rocketNozzle" data-label="Nozzle"><path d="${region(nozzlePts)}" fill="url(#rk-flow)"/></g>
    <path d="M${half(C.pts, 1).join('L')}" fill="none" stroke="var(--text)" stroke-opacity=".7" stroke-width="3"/>
    <path d="M${half(C.pts, -1).join('L')}" fill="none" stroke="var(--text)" stroke-opacity=".7" stroke-width="3"/>`;

  // dimensions and exit annotation
  // dimension labels on a common baseline below the chamber
  const tx = X(0), yDim = A + Math.max(C.Rc, C.Re) * k + 18;
  const dim = (x, r, label) => `<line x1="${x}" x2="${x}" y1="${A - r}" y2="${yDim - 12}" stroke="var(--muted)" stroke-dasharray="3 3"/>
    <text x="${x}" y="${yDim}" text-anchor="middle" font-size="11" fill="var(--muted)">${label}</text>`;
  let marks = dim(tx, k, `D<tspan baseline-shift="sub" font-size="8">t</tspan> = ${res.geometry.throat_diameter.toFixed(3)} m`)
    + dim(xEnd, re, `D<tspan baseline-shift="sub" font-size="8">e</tspan> = ${res.geometry.exit_diameter.toFixed(3)} m`);
  const expansion = pa === 0 ? 'vacuum' : Math.abs(pe - pa) / pa < 0.01 ? 'adapted' : pe < pa ? 'over-expanded' : 'under-expanded';
  marks += `<text x="${xEnd + 10}" y="${A - re - 22}" font-size="12" fill="var(--text)" font-weight="650">M = ${noz.mach.toFixed(2)} · ε = ${(+noz.area_ratio).toFixed(2)}</text>
    <text x="${xEnd + 10}" y="${A - re - 7}" font-size="11" fill="var(--muted)">${expansion}, pₑ = ${(pe / 1000).toFixed(1)} kPa${pa > 0 ? ` vs pₐ = ${(pa / 1000).toFixed(1)} kPa` : ''}</text>`;

  marks += stationMarker(st['Chamber'], X((chamberPts[0].x + chamberPts[1].x) / 2), A, col(st['Chamber'].temperature));
  marks += stationMarker(st['Throat'], tx, A, col(st['Throat'].temperature));
  marks += stationMarker(st['Nozzle exit'], xEnd, A, col(st['Nozzle exit'].temperature));

  const labels = `<text x="${X((chamberPts[0].x + chamberPts[1].x) / 2)}" y="${H - 8}" text-anchor="middle" font-size="12" fill="var(--muted)">Chamber</text>
    <text x="${(tx + xEnd) / 2}" y="${H - 8}" text-anchor="middle" font-size="12" fill="var(--muted)">Nozzle</text>`;

  container.innerHTML = `<svg viewBox="0 0 ${W} ${H}" role="img" aria-label="Thrust chamber schematic">
    <defs>${defs}</defs>
    <line x1="10" x2="${W - 10}" y1="${A}" y2="${A}" stroke="var(--muted)" stroke-opacity=".35" stroke-dasharray="6 6"/>
    ${body}${marks}${labels}
  </svg>`;
  bindSchematic(container, st, handlers);
  return { Tmin, Tmax };
}

/* Solid motor to scale: case, grain (drawn by o.grain), nozzle and plume at the maximum-pressure state.
 * o: D (case inner diameter), grainLength [m], aftGap [m] free length before the nozzle,
 *    foreGap [m] free length at the head end (default 0.04 D),
 *    grain(k, A, x0, f) -> { body, marks }, chamberX(xGrain, xAft) for station 1, grainLabel, dimLabel. */
function drawSolidMotor(container, res, handlers, o) {
  const st = Object.fromEntries(res.stations.map(s => [s.name, s]));
  const temps = res.stations.map(s => s.temperature).filter(isFinite);
  const Tmin = Math.min(...temps), Tmax = Math.max(...temps);
  const col = T => heatColor((T - Tmin) / Math.max(1, Tmax - Tmin));
  const noz = res.mainNozzle, g = res.gases.hot.gamma, D = o.D;
  const rt = res.geometry.throat_diameter / 2;

  const k = 70 / (D / 2);                                 // px per metre
  const A = 70 + 50, wall = 5;
  const xCase = 40, xGrain = xCase + (o.foreGap ?? 0.04 * D) * k;
  const xAft = xGrain + (o.grainLength + o.aftGap) * k;   // aft end of the case
  // nozzle: 45° convergent from the case to the throat, then the bell of rocketContour
  const C = rocketContour(noz.area_ratio);
  const conv = (D / 2 / rt - 1) * rt * k;
  const xT = xAft + conv;
  const div = C.pts.filter(q => q.part === 'divergent');
  const xEnd = xT + C.Ln * rt * k, re = C.Re * rt * k;
  const W = xEnd + 260, H = 2 * 70 + 140;
  const f = Math.max(1, W / 1000);                      // long motors: keep the text readable once scaled down

  let defs = '', body = '', marks = '', labels = '';
  // hot gas in the chamber and in the nozzle (temperature along the nozzle)
  const stops = [{ x: 0, T: st['Chamber'].temperature }, ...div.filter((q, i) => i % 4 === 0 || i === div.length - 1).map(q => {
    const m = machFromArea(q.r * q.r, g, true);
    return { x: q.x, T: st['Chamber'].temperature / (1 + (g - 1) / 2 * m * m) };
  })];
  defs += `<linearGradient id="srm-noz" gradientUnits="userSpaceOnUse" x1="${xT}" x2="${xEnd}" y1="0" y2="0">${
    stops.map(s => `<stop offset="${(s.x / C.Ln).toFixed(4)}" stop-color="${col(s.T)}"/>`).join('')}</linearGradient>`;
  body += `<rect x="${xCase}" y="${A - D / 2 * k}" width="${xAft - xCase}" height="${D * k}" fill="${col(st['Chamber'].temperature)}" opacity=".9"/>`;

  const grain = o.grain(k, A, xGrain, f);
  body += grain.body;
  marks += grain.marks;

  // nozzle gas and walls
  const wallPts = sgn => [`${xAft} ${A - sgn * D / 2 * k}`, `${xT} ${A - sgn * rt * k}`,
    ...div.map(q => `${(xT + q.x * rt * k).toFixed(1)} ${(A - sgn * q.r * rt * k).toFixed(1)}`)];
  const top = wallPts(1), bottom = wallPts(-1);
  body += `<g class="block" data-group="srmNozzle" data-label="Nozzle">
    <path d="M${top.join('L')}L${bottom.slice().reverse().join('L')}Z" fill="url(#srm-noz)"/></g>`;
  body += `<path d="M${top.join('L')}" fill="none" stroke="var(--text)" stroke-opacity=".7" stroke-width="3"/>
    <path d="M${bottom.join('L')}" fill="none" stroke="var(--text)" stroke-opacity=".7" stroke-width="3"/>`;
  // case and forward closure
  body += `<path d="M${xAft} ${A - D / 2 * k - wall}L${xCase - wall} ${A - D / 2 * k - wall}L${xCase - wall} ${A + D / 2 * k + wall}L${xAft} ${A + D / 2 * k + wall}"
    fill="none" stroke="var(--shaft)" stroke-width="${2 * wall}"/>`;

  // plume, contracted or widened by the expansion at the maximum pressure
  const pe = noz.exit_pressure, pa = res.ambient_pressure;
  const spread = Math.min(pa > 0 ? Math.max(0.55, Math.pow(pe / pa, 0.25)) : 1.6, 1.6, 100 / re);
  defs += `<linearGradient id="srm-plume" x1="0" x2="1"><stop offset="0" stop-color="${col(st['Nozzle exit'].temperature)}" stop-opacity=".6"/>
    <stop offset="1" stop-color="${col(st['Nozzle exit'].temperature)}" stop-opacity="0"/></linearGradient>`;
  body += `<path d="M${xEnd} ${A - re}Q${xEnd + 60} ${A - re * (1 + spread) / 2} ${xEnd + 120} ${A - re * spread}
    L${xEnd + 120} ${A + re * spread}Q${xEnd + 60} ${A + re * (1 + spread) / 2} ${xEnd} ${A + re}Z" fill="url(#srm-plume)"/>`;

  // dimensions
  const yDim = A + D / 2 * k + 14 + 12 * f;
  const dim = (x, label) => `<text x="${x}" y="${yDim}" text-anchor="middle" font-size="${11 * f}" fill="var(--muted)">${label}</text>`;
  // a short nozzle: exit diameter on a second line
  const dimE = (xEnd + 30 - xT < 130 * f) ? (x, label) => dim(x, label).replace(`y="${yDim}"`, `y="${yDim + 15 * f}"`) : dim;
  marks += dim(xT, `D<tspan baseline-shift="sub" font-size="${8 * f}">t</tspan> = ${(2 * rt).toFixed(3)} m`)
    + dimE(xEnd + 30, `D<tspan baseline-shift="sub" font-size="${8 * f}">e</tspan> = ${res.geometry.exit_diameter.toFixed(3)} m`)
    + dim(xGrain + Math.min(o.grainLength * k, 300) / 2, o.dimLabel);
  marks += `<text x="${xEnd + 10}" y="${A - re - 12 - 14 * f}" font-size="${12 * f}" fill="var(--text)" font-weight="650">M = ${noz.mach.toFixed(2)} · ε = ${(+noz.area_ratio).toFixed(2)}</text>
    <text x="${xEnd + 10}" y="${A - re - 10}" font-size="${11 * f}" fill="var(--muted)">at max pressure ${(st['Chamber'].pressure / 1e6).toFixed(2)} MPa</text>`;

  marks += stationMarker(st['Chamber'], o.chamberX(xGrain, xAft), A, col(st['Chamber'].temperature), f);
  marks += stationMarker(st['Throat'], xT, A, col(st['Throat'].temperature), f);
  marks += stationMarker(st['Nozzle exit'], xEnd, A, col(st['Nozzle exit'].temperature), f);

  labels = `<text x="${(xGrain + xAft) / 2}" y="${H - 8}" text-anchor="middle" font-size="${12 * f}" fill="var(--muted)">${o.grainLabel}</text>
    <text x="${(xT + xEnd) / 2}" y="${H - 8}" text-anchor="middle" font-size="${12 * f}" fill="var(--muted)">Nozzle</text>`;

  container.innerHTML = `<svg viewBox="0 0 ${W} ${H}" role="img" aria-label="Solid motor schematic">
    <defs>${defs}</defs>
    <line x1="10" x2="${W - 10}" y1="${A}" y2="${A}" stroke="var(--muted)" stroke-opacity=".35" stroke-dasharray="6 6"/>
    ${body}${marks}${labels}
  </svg>`;
  bindSchematic(container, st, handlers);
  return { Tmin, Tmax };
}

/* BATES: segments in section with burn-back contours at 1/3 and 2/3 of the web */
function renderSolidSchematic(container, cfg, res, handlers) {
  const G = cfg.components.grain;
  const N = G.segments, D = G.outer_diameter, d0 = G.core_diameter, L0 = G.segment_length;
  const ends = !G.inhibited_ends, web = res.grain.web, gap = 0.04 * D;
  const prop = '#c8a165';
  return drawSolidMotor(container, res, handlers, {
    D, grainLength: N * L0 + (N - 1) * gap, aftGap: 0.06 * D,
    grainLabel: `Grain · ${N} BATES segment${N > 1 ? 's' : ''}`, dimLabel: `D = ${D} m · d₀ = ${d0} m`,
    chamberX: (xGrain, xAft) => (xGrain + xAft) / 2,
    grain: (k, A, xGrain, f) => {
      let body = '';
      for (let i = 0; i < N; i++) {
        const x0 = xGrain + i * (L0 + gap) * k, x1 = x0 + L0 * k;
        for (const sgn of [-1, 1]) {
          const yIn = A + sgn * d0 / 2 * k, yOut = A + sgn * D / 2 * k;
          body += `<rect class="block" data-group="srmGrain" data-label="Grain segment ${i + 1}" x="${x0}" y="${Math.min(yIn, yOut)}" width="${x1 - x0}"
            height="${Math.abs(yOut - yIn)}" fill="${prop}" stroke="var(--panel)" stroke-width="1"/>`;
          for (const fr of [1 / 3, 2 / 3]) {
            const w = fr * web, xa = x0 + (ends ? w : 0) * k, xb = x1 - (ends ? w : 0) * k, yr = A + sgn * (d0 / 2 + w) * k;
            if (xb <= xa || d0 / 2 + w >= D / 2) continue;
            body += `<path d="M${xa} ${yOut}L${xa} ${yr}L${xb} ${yr}L${xb} ${yOut}" fill="none" stroke="#7c2d12" stroke-opacity=".55" stroke-width="1.2" stroke-dasharray="4 3"/>`;
          }
        }
      }
      const marks = `<text x="${xGrain}" y="${A - D / 2 * k - 12}" font-size="${11 * f}" fill="var(--muted)">dashed: burning surface at 1/3 and 2/3 of the web (${(web * 1000).toFixed(1)} mm)</text>`;
      return { body, marks };
    },
  });
}

/* propellant colours of the layers of a cigarette grain */
const LAYER_COLORS = ['#c8a165', '#9fb38a', '#b39ac4', '#d4a59a', '#8fb3c9', '#cbb85f'];

/* Cigarette grain: layers stacked from the head end (left) to the nozzle side; layer 1 burns first */
function renderEndBurnerSchematic(container, cfg, res, handlers) {
  const D = cfg.components.grain.diameter;
  const phases = res.phases;
  const total = phases.reduce((a, p) => a + p.length, 0);
  return drawSolidMotor(container, res, handlers, {
    D, grainLength: total, aftGap: 0.3 * D, foreGap: 0,
    grainLabel: `Cigarette grain · ${phases.length} layer${phases.length > 1 ? 's' : ''} (layer 1 burns first)`,
    dimLabel: `D = ${D} m · A<tspan baseline-shift="sub" font-size="8">b</tspan> = πD²/4`,
    chamberX: (xGrain, xAft) => xAft - 0.15 * D * (70 / (D / 2)),
    grain: (k, A, xGrain, f) => {
      let body = '', marks = '';
      let x1 = xGrain + total * k;                      // aft face of layer 1
      phases.forEach((p, i) => {
        const x0 = x1 - p.length * k;
        body += `<rect class="block" data-group="ebLayers.layer${p.layer}" data-label="Layer ${p.layer}" x="${x0}" y="${A - D / 2 * k}"
          width="${x1 - x0}" height="${D * k}" fill="${LAYER_COLORS[i % LAYER_COLORS.length]}" stroke="var(--panel)" stroke-width="1.5"/>`;
        if (x1 - x0 > 40 * f) {
          marks += `<text x="${(x0 + x1) / 2}" y="${A - 8}" text-anchor="middle" font-size="${12 * f}" font-weight="650" fill="#1f2937">${p.layer}</text>
            <text x="${(x0 + x1) / 2}" y="${A + 10 * f}" text-anchor="middle" font-size="${10 * f}" fill="#1f2937">${(p.pressure / 1e6).toFixed(2)} MPa</text>`;
        }
        x1 = x0;
      });
      // burning face: the aft face of layer 1, facing the nozzle
      const xb = xGrain + total * k;
      body += `<line x1="${xb}" x2="${xb}" y1="${A - D / 2 * k}" y2="${A + D / 2 * k}" stroke="#f97316" stroke-width="4"/>`;
      marks += `<text x="${xb}" y="${A - D / 2 * k - 12}" text-anchor="middle" font-size="${11 * f}" fill="var(--muted)">burning face →</text>`;
      return { body, marks };
    },
  });
}

function renderSchematic(container, engine, cfg, res, handlers) {
  if (engine === 'solidRocket') return renderSolidSchematic(container, cfg, res, handlers);
  if (engine === 'endBurner') return renderEndBurnerSchematic(container, cfg, res, handlers);
  if (ENGINES[engine].family === 'rocket') return renderRocketSchematic(container, res, handlers);
  const L = engineLayout(engine, cfg, res);
  const temps = res.stations.map(s => s.temperature).filter(isFinite);
  const Tmin = Math.min(...temps), Tmax = Math.max(...temps);
  const col = T => heatColor((T - Tmin) / Math.max(1, Tmax - Tmin));
  const T = name => (L.st[name] ? L.st[name].temperature : Tmin);

  const rMax = Math.max(...L.blocks.map(b => Math.max(b.hIn, b.hOut)), ...L.bands.map(b => b.rOut0), ...L.extras.map(e => e.h + 8));
  const A = rMax + 24, H = 2 * rMax + 70;
  let defs = '', body = '', labels = '', marks = '';
  let gid = 0;
  const grad = (t0, t1) => {
    const id = `hg${gid++}`;
    defs += `<linearGradient id="${id}" x1="0" x2="1" y1="0" y2="0"><stop offset="0" stop-color="${col(t0)}"/><stop offset="1" stop-color="${col(t1)}"/></linearGradient>`;
    return `url(#${id})`;
  };

  // bypass ducts (top and bottom)
  for (const b of L.bands) {
    const fill = grad(T(b.inSt), T(b.outSt));
    for (const sgn of [-1, 1]) {
      const yIn = A + sgn * b.rIn, y0 = A + sgn * b.rOut0, y1 = A + sgn * b.rOut1;
      body += `<path class="block" data-group="${b.group}" data-label="Bypass duct" d="M${b.x0} ${yIn}L${b.x1} ${yIn}L${b.x1} ${y1}L${b.x0} ${y0}Z" fill="${fill}" stroke="var(--panel)" stroke-width="1.5"/>`;
    }
  }

  // extras (propeller)
  for (const e of L.extras) {
    if (e.kind === 'propeller') {
      const fill = col(T('Air at entrance'));
      body += `<g class="block" data-group="${e.group}" data-label="Propeller">
        <rect x="${e.x + 8}" y="${A - 5}" width="${L.blocks[0].x0 - e.x - 8}" height="10" rx="3" fill="var(--shaft)" opacity=".55"/>
        <ellipse cx="${e.x}" cy="${A - e.h / 2 - 8}" rx="9" ry="${e.h / 2}" fill="${fill}" opacity=".9"/>
        <ellipse cx="${e.x}" cy="${A + e.h / 2 + 8}" rx="9" ry="${e.h / 2}" fill="${fill}" opacity=".9"/>
        <circle cx="${e.x}" cy="${A}" r="15" fill="var(--shaft)"/>
      </g>`;
      labels += `<text x="${e.x}" y="${H - 8}" text-anchor="middle" font-size="12" fill="var(--muted)">Propeller</text>`;
    }
  }

  // core blocks
  for (const b of L.blocks) {
    const fill = grad(T(b.inSt), T(b.outSt));
    let d;
    if (b.kind === 'nozzle' && b.conDiv) {
      const xm = b.x0 + (b.x1 - b.x0) * 0.55, ht = Math.min(b.hIn, b.hOut) * 0.72;
      d = `M${b.x0} ${A - b.hIn}L${xm} ${A - ht}L${b.x1} ${A - b.hOut}L${b.x1} ${A + b.hOut}L${xm} ${A + ht}L${b.x0} ${A + b.hIn}Z`;
    } else if (b.kind === 'burner') {
      const bulge = 10;
      d = `M${b.x0} ${A - b.hIn}C${b.x0 + 25} ${A - b.hIn - bulge} ${b.x1 - 25} ${A - b.hOut - bulge} ${b.x1} ${A - b.hOut}` +
          `L${b.x1} ${A + b.hOut}C${b.x1 - 25} ${A + b.hOut + bulge} ${b.x0 + 25} ${A + b.hIn + bulge} ${b.x0} ${A + b.hIn}Z`;
    } else {
      d = `M${b.x0} ${A - b.hIn}L${b.x1} ${A - b.hOut}L${b.x1} ${A + b.hOut}L${b.x0} ${A + b.hIn}Z`;
    }
    body += `<g class="block" data-group="${b.group || ''}" data-label="${b.label}">
      <path d="${d}" fill="${fill}" stroke="var(--panel)" stroke-width="1.5"/>`;
    if (b.kind === 'comp' || b.kind === 'turb') {
      body += `<path d="${bladeLines(b.x0, b.x1, b.hIn, b.hOut, A, b.kind === 'comp' ? 13 : 15)}" stroke="#fff" stroke-opacity=".35" stroke-width="2"/>`;
    }
    if (b.kind === 'burner') {
      const cx = (b.x0 + b.x1) / 2;
      body += `<path d="M${cx} ${A - 16}c8 8 10 14 4 20c-2-6-6-6-6-6c0 6-6 8-6 14c-6-6-4-14 0-18c-2 6 2 6 2 6c2-6 6-10 6-16z" fill="#fff" opacity=".75" transform="translate(-2 2)"/>`;
    }
    if (b.kind === 'ab') {
      body += `<path d="${bladeLines(b.x0 + 18, b.x0 + 26, b.hIn, b.hIn, A, 8)}" stroke="#fff" stroke-opacity=".5" stroke-width="3" stroke-dasharray="6 5"/>`;
    }
    body += `</g>`;
    labels += `<text x="${(b.x0 + b.x1) / 2}" y="${H - 8}" text-anchor="middle" font-size="12" fill="var(--muted)">${b.label}</text>`;
  }

  // nozzle exit annotations
  const nozBlock = L.blocks.find(b => b.kind === 'nozzle');
  const annot = (noz, xx, yy, label) => {
    if (!noz || noz.mach == null) return '';
    const kind = noz.onlyConvergent ? (noz.mach < 0.999 ? 'convergent, not choked' : 'convergent, choked')
      : (noz.mach > 1.01 ? 'con-div required' : 'convergent ok');
    return `<text x="${xx}" y="${yy}" font-size="12" fill="var(--text)" font-weight="650">${label} M = ${noz.mach.toFixed(2)}</text>
            <text x="${xx}" y="${yy + 15}" font-size="11" fill="var(--muted)">${kind}</text>`;
  };
  if (nozBlock) marks += annot(nozBlock.noz, nozBlock.x1 + 8, A - nozBlock.hOut - 22, '');
  for (const b of L.bands) if (b.noz) marks += annot(b.noz, b.x1 + 8, A - b.rOut1 - 6, 'Bypass');

  // jet plume hint
  if (nozBlock) {
    const h = nozBlock.hOut;
    defs += `<linearGradient id="plume" x1="0" x2="1"><stop offset="0" stop-color="${col(T(nozBlock.outSt))}" stop-opacity=".55"/><stop offset="1" stop-color="${col(T(nozBlock.outSt))}" stop-opacity="0"/></linearGradient>`;
    body += `<path d="M${nozBlock.x1} ${A - h}L${nozBlock.x1 + 100} ${A - h * 0.6}L${nozBlock.x1 + 100} ${A + h * 0.6}L${nozBlock.x1} ${A + h}Z" fill="url(#plume)"/>`;
  }

  // station markers
  for (const m of L.markers) marks += stationMarker(m.s, m.x, A + m.y, col(m.s.temperature));

  container.innerHTML = `<svg viewBox="0 0 ${L.width} ${H}" role="img" aria-label="Engine schematic">
    <defs>${defs}</defs>
    <line x1="10" x2="${L.width - 10}" y1="${A}" y2="${A}" stroke="var(--muted)" stroke-opacity=".35" stroke-dasharray="6 6"/>
    ${body}${marks}${labels}
  </svg>`;
  bindSchematic(container, L.st, handlers);

  return { Tmin, Tmax };
}
