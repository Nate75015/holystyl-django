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

  function renderChart(canvas) {
    if (typeof Chart === 'undefined') return;
    const dataEl = document.getElementById(canvas.dataset.chart);
    if (!dataEl) return;
    let conf;
    try { conf = JSON.parse(dataEl.textContent); } catch (e) { return; }
    const color = conf.color || '#2abfbf';
    const ctx = canvas.getContext('2d');
    const grad = ctx.createLinearGradient(0, 0, 0, canvas.height || 180);
    grad.addColorStop(0, color + '66');
    grad.addColorStop(1, color + '05');
    new Chart(ctx, {
      type: 'line',
      data: {
        labels: conf.labels || [],
        datasets: [{
          label: conf.label || '',
          data: conf.data || [],
          borderColor: color,
          backgroundColor: grad,
          fill: true,
          tension: 0.4,
          pointRadius: 0,
          borderWidth: 2,
        }],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: { legend: { display: false } },
        scales: {
          x: { grid: { display: false }, ticks: { color: '#7c8a8a', maxRotation: 0, autoSkip: true } },
          y: { grid: { color: 'rgba(127,138,138,0.12)' }, ticks: { color: '#7c8a8a' } },
        },
      },
    });
  }

  function init() {
    document.querySelectorAll('.dti-gauge').forEach(renderGauge);
    document.querySelectorAll('canvas[data-chart]').forEach(renderChart);
  }

  window.Holystyl = { renderGauge, renderChart, init };
  if (document.readyState !== 'loading') init();
  else document.addEventListener('DOMContentLoaded', init);
})();
