/* Holystyl — brique data-viz réutilisable.
 * - Jauge DTI (compte-tours SVG 270°, A→D)
 * - Graphiques d'aires avec dégradé/glow (Chart.js)
 * Auto-initialisation : tout `.dti-gauge` et tout `[data-chart]` du DOM.
 */
(function () {
  const SCORE = {
    A: { color: '#22c55e', label: 'Excellent' },
    B: { color: '#f59e0b', label: 'Bon' },
    C: { color: '#f97316', label: 'Moyen' },
    D: { color: '#ef4444', label: 'Critique' },
  };

  function polar(cx, cy, r, deg) {
    const a = (deg * Math.PI) / 180;
    return [cx + r * Math.cos(a), cy + r * Math.sin(a)];
  }
  function arc(cx, cy, r, start, end) {
    const [x1, y1] = polar(cx, cy, r, start);
    const [x2, y2] = polar(cx, cy, r, end);
    const large = end - start > 180 ? 1 : 0;
    return `M ${x1} ${y1} A ${r} ${r} 0 ${large} 1 ${x2} ${y2}`;
  }

  function renderGauge(el) {
    const score = (el.dataset.score || 'A').toUpperCase();
    const numeric = Math.max(0, Math.min(100, parseFloat(el.dataset.numeric || '0')));
    const kwh = el.dataset.kwh;
    const size = parseInt(el.dataset.size || '200', 10);
    const cfg = SCORE[score] || SCORE.A;
    const cx = size / 2, cy = size / 2, r = (size / 2) * 0.78, sw = (size / 2) * 0.1;
    const START = 135, SWEEP = 270;
    const fillEnd = START + (numeric / 100) * SWEEP;
    const dark = document.documentElement.classList.contains('dark');
    const track = dark ? 'rgba(255,255,255,0.08)' : 'rgba(0,0,0,0.08)';
    const txt = dark ? '#eafafa' : '#0f2a2a';
    const sub = dark ? '#7c8a8a' : '#5b6b6b';
    const [nx, ny] = polar(cx, cy, r - sw, fillEnd);

    el.innerHTML =
      `<svg viewBox="0 0 ${size} ${size}" width="${size}" height="${size}">
        <path d="${arc(cx, cy, r, START, START + SWEEP)}" fill="none" stroke="${track}" stroke-width="${sw}" stroke-linecap="round"/>
        <path d="${arc(cx, cy, r, START, Math.max(START + 0.1, fillEnd))}" fill="none" stroke="${cfg.color}" stroke-width="${sw}" stroke-linecap="round"
              style="filter: drop-shadow(0 0 6px ${cfg.color})"/>
        <line x1="${cx}" y1="${cy}" x2="${nx}" y2="${ny}" stroke="${cfg.color}" stroke-width="3" stroke-linecap="round"/>
        <circle cx="${cx}" cy="${cy}" r="${size*0.04}" fill="${cfg.color}"/>
        <text x="${cx}" y="${cy - size*0.06}" text-anchor="middle" font-size="${size*0.26}" font-weight="800" fill="${cfg.color}">${score}</text>
        <text x="${cx}" y="${cy + size*0.13}" text-anchor="middle" font-size="${size*0.085}" fill="${txt}">${kwh != null && kwh !== '' ? kwh + ' kWh/m³' : ''}</text>
        <text x="${cx}" y="${cy + size*0.27}" text-anchor="middle" font-size="${size*0.07}" fill="${sub}">${cfg.label}</text>
      </svg>`;
  }

  // Jauge de pourcentage générique (compte-tours 270°), teintée du bleu d'action
  // (celui des boutons primaires) : lue sur les tokens CSS, donc suit le thème.
  // Usage : <div class="pct-gauge" data-pct="72" data-size="80" data-label="remplis"></div>
  let pctSeq = 0;
  function token(nom, defaut) {
    const v = getComputedStyle(document.documentElement).getPropertyValue(nom).trim();
    return v || defaut;
  }
  function renderPctGauge(el) {
    const pct = Math.max(0, Math.min(100, parseFloat(el.dataset.pct || '0')));
    const size = parseInt(el.dataset.size || '120', 10);
    const label = el.dataset.label || '';
    const cx = size / 2, cy = size / 2, r = (size / 2) * 0.82, sw = (size / 2) * 0.12;
    const START = 135, SWEEP = 270;
    const fillEnd = START + (pct / 100) * SWEEP;
    const dark = document.documentElement.classList.contains('dark');
    const track = dark ? 'rgba(255,255,255,0.08)' : 'rgba(0,0,0,0.07)';
    const action = token('--action', dark ? '#5A8AB8' : '#335E8A');
    const actionHover = token('--action-hover', dark ? '#6E9BC6' : '#28496B');
    const txt = action;
    const sub = dark ? '#7c8a8a' : '#5b6b6b';
    const uid = 'pctgrad-' + (pctSeq++);

    el.innerHTML =
      `<svg viewBox="0 0 ${size} ${size}" width="${size}" height="${size}">
        <defs>
          <linearGradient id="${uid}" x1="0" y1="0" x2="1" y2="1">
            <stop offset="0%" stop-color="${actionHover}"/>
            <stop offset="100%" stop-color="${action}"/>
          </linearGradient>
        </defs>
        <path d="${arc(cx, cy, r, START, START + SWEEP)}" fill="none" stroke="${track}" stroke-width="${sw}" stroke-linecap="round"/>
        <path d="${arc(cx, cy, r, START, Math.max(START + 0.1, fillEnd))}" fill="none" stroke="url(#${uid})" stroke-width="${sw}" stroke-linecap="round"/>
        <text x="${cx}" y="${label ? cy + size*0.02 : cy + size*0.09}" text-anchor="middle" font-size="${size*0.26}" font-weight="800" fill="${txt}">${Math.round(pct)}%</text>
        ${label ? `<text x="${cx}" y="${cy + size*0.22}" text-anchor="middle" font-size="${size*0.1}" fill="${sub}">${label}</text>` : ''}
      </svg>`;
  }

  function renderChart(canvas) {
    if (typeof Chart === 'undefined') return;
    const dataEl = document.getElementById(canvas.dataset.chart);
    if (!dataEl) return;
    let conf;
    try { conf = JSON.parse(dataEl.textContent); } catch (e) { return; }
    const ctx = canvas.getContext('2d');
    const h = canvas.height || 180;
    const mkFill = (color) => {
      const g = ctx.createLinearGradient(0, 0, 0, h);
      g.addColorStop(0, color + '66');
      g.addColorStop(1, color + '05');
      return g;
    };
    // Multi-séries (conf.datasets) ou série unique (conf.data)
    const series = conf.datasets || [{ label: conf.label || '', data: conf.data || [], color: conf.color || '#0891b2' }];
    const type = conf.type === 'bar' ? 'bar' : 'line';
    const datasets = series.map((s) => {
      const color = s.color || '#0891b2';
      return type === 'bar'
        ? { label: s.label || '', data: s.data || [], backgroundColor: color, borderRadius: 6 }
        : { label: s.label || '', data: s.data || [], borderColor: color, backgroundColor: mkFill(color),
            fill: true, tension: 0.4, pointRadius: 0, borderWidth: 2 };
    });
    new Chart(ctx, {
      type: type,
      data: { labels: conf.labels || [], datasets: datasets },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: { legend: { display: (conf.datasets && conf.datasets.length > 1), labels: { color: '#7c8a8a' } } },
        scales: {
          x: { grid: { display: false }, ticks: { color: '#7c8a8a', maxRotation: 0, autoSkip: true } },
          y: { grid: { color: 'rgba(127,138,138,0.12)' }, ticks: { color: '#7c8a8a' } },
        },
      },
    });
  }

  function init() {
    document.querySelectorAll('.dti-gauge').forEach(renderGauge);
    document.querySelectorAll('.pct-gauge').forEach(renderPctGauge);
    document.querySelectorAll('canvas[data-chart]').forEach(renderChart);
  }

  window.Holystyl = { renderGauge, renderChart, init };
  if (document.readyState !== 'loading') init();
  else document.addEventListener('DOMContentLoaded', init);
})();
