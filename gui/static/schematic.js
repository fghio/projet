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

function renderSchematic(container, engine, cfg, res, handlers) {
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
  for (const m of L.markers) {
    const c = col(m.s.temperature);
    const label = m.s.number;
    marks += `<g class="station" data-name="${m.s.name}" transform="translate(${m.x} ${A + m.y})">
      <circle r="11" fill="${c}" stroke="var(--panel)" stroke-width="2.5"/>
      <text text-anchor="middle" dy="4" font-size="11" font-weight="700" fill="${textOn(c)}">${label}</text>
    </g>`;
  }

  container.innerHTML = `<svg viewBox="0 0 ${L.width} ${H}" role="img" aria-label="Engine schematic">
    <defs>${defs}</defs>
    <line x1="10" x2="${L.width - 10}" y1="${A}" y2="${A}" stroke="var(--muted)" stroke-opacity=".35" stroke-dasharray="6 6"/>
    ${body}${marks}${labels}
  </svg>`;

  // interactions
  container.querySelectorAll('.block').forEach(el => {
    el.addEventListener('click', () => el.dataset.group && handlers.onComponent(el.dataset.group));
    el.addEventListener('mousemove', ev => handlers.onHover(ev, `<b>${el.dataset.label}</b>${el.dataset.group ? 'click to edit inputs' : 'no inputs'}`));
    el.addEventListener('mouseleave', () => handlers.onHover(null));
  });
  container.querySelectorAll('.station').forEach(el => {
    const s = L.st[el.dataset.name];
    el.addEventListener('mousemove', ev => handlers.onHover(ev, handlers.stationTip(s)));
    el.addEventListener('mouseleave', () => handlers.onHover(null));
  });

  return { Tmin, Tmax };
}
