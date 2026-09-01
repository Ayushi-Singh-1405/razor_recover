/* Minimal hand-rolled SVG charts — no chart library, matches theme tokens.
   Every builder returns an SVG string; callers insert into the DOM. */

const ACCENT = "#3395FF";
const ACCENT_HOVER = "#1F7AE0";
const MUTED = "#9CA3AF";
const SUCCESS = "#16A34A";
const WARNING = "#D97706";
const TEXT = "#0C2451";
const GRID = "#E5E7EB";

const esc = s => String(s).replace(/[&<>"']/g,
  c => ({"&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"}[c]));

/* Recovery trend — cumulative line with dots.
   points: [{label, value}] in chronological order. */
export function lineChart({ points, yLabel = "", height = 190 }) {
  const W = 460, H = height, P = { l: 44, r: 16, t: 14, b: 26 };
  const max = Math.max(1, ...points.map(p => p.value));
  const iw = W - P.l - P.r, ih = H - P.t - P.b;
  const step = points.length > 1 ? iw / (points.length - 1) : 0;
  const xy = points.map((p, i) => [
    P.l + (points.length > 1 ? i * step : iw / 2),
    P.t + ih - (p.value / max) * ih,
  ]);

  const grid = [0, 0.5, 1].map(f => {
    const y = P.t + ih - f * ih;
    return `<line x1="${P.l}" y1="${y}" x2="${W - P.r}" y2="${y}" stroke="${GRID}" stroke-width="1"/>
            <text x="${P.l - 6}" y="${y + 3}" text-anchor="end" font-size="9" fill="${MUTED}">${Math.round(max * f)}</text>`;
  }).join("");

  const line = xy.map((p, i) => `${i ? "L" : "M"}${p[0].toFixed(1)},${p[1].toFixed(1)}`).join(" ");
  const dots = xy.map((p, i) =>
    `<circle cx="${p[0].toFixed(1)}" cy="${p[1].toFixed(1)}" r="3.2" fill="#fff" stroke="${ACCENT}" stroke-width="2"/>
     <text x="${p[0].toFixed(1)}" y="${(p[1] - 8).toFixed(1)}" text-anchor="middle" font-size="9" fill="${TEXT}" font-weight="600">${points[i].value}</text>`).join("");
  const xlabels = points.map((p, i) =>
    `<text x="${xy[i][0].toFixed(1)}" y="${H - 8}" text-anchor="middle" font-size="9" fill="${MUTED}">${esc(p.label)}</text>`).join("");

  return `<svg viewBox="0 0 ${W} ${H}" role="img" aria-label="${esc(yLabel)}">
    ${grid}
    <path d="${line}" fill="none" stroke="${ACCENT}" stroke-width="2.2" stroke-linejoin="round" stroke-linecap="round"/>
    ${dots}${xlabels}
  </svg>`;
}

/* Vertical bars — counts by category. items: [{label, value}] */
export function barChart({ items, height = 190 }) {
  const W = 460, H = height, P = { l: 10, r: 10, t: 20, b: 34 };
  const max = Math.max(1, ...items.map(i => i.value));
  const iw = W - P.l - P.r, ih = H - P.t - P.b;
  const slot = iw / items.length;
  const bw = Math.min(46, slot * 0.55);

  const bars = items.map((it, i) => {
    const x = P.l + i * slot + (slot - bw) / 2;
    const h = (it.value / max) * ih;
    return `<rect x="${x.toFixed(1)}" y="${(P.t + ih - h).toFixed(1)}" width="${bw.toFixed(1)}" height="${h.toFixed(1)}" rx="3" fill="${ACCENT}"/>
      <text x="${(x + bw / 2).toFixed(1)}" y="${(P.t + ih - h - 6).toFixed(1)}" text-anchor="middle" font-size="10" fill="${TEXT}" font-weight="600">${it.value}</text>
      <text x="${(x + bw / 2).toFixed(1)}" y="${H - 12}" text-anchor="middle" font-size="9" fill="${MUTED}">${esc(it.label)}</text>`;
  }).join("");

  return `<svg viewBox="0 0 ${W} ${H}" role="img" aria-label="Bar chart">
    <line x1="${P.l}" y1="${P.t + ih}" x2="${W - P.r}" y2="${P.t + ih}" stroke="${GRID}"/>
    ${bars}
  </svg>`;
}

/* Donut — outcome split. segments: [{label, value, color}] */
export function donutChart({ segments, centerLabel = "", centerValue = "" }) {
  const total = segments.reduce((s, x) => s + x.value, 0) || 1;
  const R = 56, C = 2 * Math.PI * R;
  let offset = 0;
  const arcs = segments.map(s => {
    const frac = s.value / total;
    const arc = `<circle cx="75" cy="75" r="${R}" fill="none" stroke="${s.color}"
      stroke-width="20" stroke-dasharray="${(frac * C).toFixed(1)} ${C.toFixed(1)}"
      stroke-dashoffset="${(-offset * C).toFixed(1)}" transform="rotate(-90 75 75)"/>`;
    offset += frac;
    return arc;
  }).join("");

  const legend = segments.map(s => `
    <div class="chart-legend-row">
      <span class="chart-legend-dot" style="background:${s.color}"></span>
      <span>${esc(s.label)}</span>
      <span class="chart-legend-value">${s.value}</span>
    </div>`).join("");

  return `<div class="chart-donut">
    <svg viewBox="0 0 150 150" role="img" aria-label="Donut chart">
      ${arcs}
      <text x="75" y="72" text-anchor="middle" font-size="20" font-weight="700" fill="${TEXT}">${esc(centerValue)}</text>
      <text x="75" y="88" text-anchor="middle" font-size="9" fill="${MUTED}">${esc(centerLabel)}</text>
    </svg>
    <div class="chart-legend">${legend}</div>
  </div>`;
}

/* Horizontal paired comparison — agent vs benchmark.
   metrics: [{label, agent, benchmark, fmt}] — values are display strings
   plus normalized magnitude 0..1 via `scale`. */
export function compareChart({ metrics }) {
  return metrics.map(m => {
    const aW = Math.max(2, Math.min(100, m.agentScale * 100)).toFixed(1);
    const bW = Math.max(2, Math.min(100, m.benchScale * 100)).toFixed(1);
    return `
    <div class="chart-compare-metric">
      <div class="chart-compare-label">${esc(m.label)}</div>
      <div class="chart-compare-bars">
        <div class="chart-compare-row">
          <div class="chart-bar-track"><div class="chart-bar" style="width:${aW}%;background:${ACCENT}"></div></div>
          <span class="chart-compare-value">${esc(m.agent)}</span>
        </div>
        <div class="chart-compare-row">
          <div class="chart-bar-track"><div class="chart-bar" style="width:${bW}%;background:${MUTED}"></div></div>
          <span class="chart-compare-value">${esc(m.benchmark)}</span>
        </div>
      </div>
    </div>`;
  }).join("");
}

/* Horizontal stacked bars — groups: [{label, parts:[{value,color,label}]}] */
export function stackedBarChart({ groups, legend }) {
  const totals = groups.map(g => g.parts.reduce((s, p) => s + p.value, 0));
  const max = Math.max(1, ...totals);
  const rows = groups.map(g => {
    const total = g.parts.reduce((s, p) => s + p.value, 0);
    const segs = g.parts.filter(p => p.value > 0).map(p =>
      `<div class="chart-seg" style="width:${(p.value / total * 100).toFixed(1)}%;background:${p.color}" title="${esc(p.label)}: ${p.value}"></div>`).join("");
    return `
      <div class="chart-stack-row">
        <div class="chart-stack-label">${esc(g.label)}</div>
        <div class="chart-bar-track">${total ? segs : `<div class="chart-seg-empty"></div>`}</div>
        <div class="chart-stack-value">${total}</div>
      </div>`;
  }).join("");
  const legendHtml = legend ? `
    <div class="chart-legend-row-flex">${legend.map(l =>
      `<span class="chart-legend-inline"><span class="chart-legend-dot" style="background:${l.color}"></span>${esc(l.label)}</span>`).join("")}</div>` : "";
  return `<div>${rows}${legendHtml}</div>`;
}

export const CHART_COLORS = { ACCENT, ACCENT_HOVER, MUTED, SUCCESS, WARNING, TEXT, GRID };
