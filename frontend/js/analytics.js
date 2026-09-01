/* Analytics page: stat tiles, charts, agent evaluation.
   Data: /dashboard/summary (detection, real_execution, agent_evaluation). */

import { getMe, getSummary } from "./api.js";
import { setMe, setSummary } from "./state.js";
import { renderNav } from "./navigation.js";
import { esc, fmtLakhs, fmtINR, fmtPct } from "./utils.js";
import { lineChart, barChart, donutChart, compareChart, stackedBarChart, CHART_COLORS } from "./charts.js";

const OUTCOME_COLORS = { action: CHART_COLORS.SUCCESS, stop: CHART_COLORS.WARNING, escalate: CHART_COLORS.ACCENT_HOVER };

async function load() {
  if (window.location.protocol === "file:") {
    document.getElementById("status").textContent =
      "This page was opened as a local file. Start the backend (from backend/: "
      + "../venv/bin/uvicorn main:app --reload) and open http://localhost:8000/analytics instead.";
    return;
  }

  try {
    const me = await getMe();
    setMe(me);
    renderNav("analytics", me);
  } catch (err) {
    document.getElementById("status").textContent =
      "Could not load session. Is the backend running?";
    return;
  }

  try {
    const summary = await getSummary();
    setSummary(summary);
    render(summary);
  } catch (err) {
    document.getElementById("analytics-error").textContent =
      "Could not load analytics data. Is the backend running?";
    document.getElementById("analytics-error").classList.remove("hidden");
  }
}

function render(summary) {
  renderTiles(summary);
  renderTrend(summary.real_execution);
  renderFailureReasons(summary.real_execution);
  renderOutcomes(summary.real_execution);
  renderAgentPerformance(summary.agent_evaluation);
  renderExposure(summary.real_execution);
}

function renderTiles(summary) {
  const d = summary.detection;
  const re = summary.real_execution;
  const ae = summary.agent_evaluation;
  const tiles = [
    { value: fmtLakhs(d.revenue_at_risk_paise), label: "At-risk amount", tag: "SIMULATED" },
    { value: fmtINR(re.real_paise_recovered), label: "Recovered · Test Mode", tag: "REAL" },
    { value: fmtPct(ae.agent.targeting_precision), label: "Agent recovery rate", tag: "SIMULATED" },
    { value: d.at_risk.toLocaleString("en-IN"), label: "At-risk payments", tag: "SIMULATED" },
  ];
  document.getElementById("tiles").innerHTML = tiles.map(t => `
    <div class="tile">
      <div class="metric-value">${esc(t.value)}</div>
      <div class="metric-label">${esc(t.label)}</div>
      <div style="margin-top: var(--space-1);"><span class="provenance-tag ${t.tag === "REAL" ? "provenance-real" : "provenance-simulated"}">${t.tag}</span></div>
    </div>`).join("");
}

/* Recovery trend: cumulative executions + webhook-confirmed recoveries
   per day, derived from the per-transaction audit chains. */
function renderTrend(re) {
  const days = new Map();
  for (const t of re.transactions) {
    for (const e of t.audit_chain) {
      const day = e.timestamp.slice(0, 10);
      const d = days.get(day) || { exec: 0, recovered: 0 };
      if (e.event.startsWith("execution_")) d.exec += 1;
      if (e.event === "revenue_recovered") d.recovered += 1;
      days.set(day, d);
    }
  }
  const sorted = [...days.entries()].sort((a, b) => a[0].localeCompare(b[0]));
  let cumExec = 0, cumRec = 0;
  const execPoints = [], recPoints = [];
  for (const [day, d] of sorted) {
    cumExec += d.exec; cumRec += d.recovered;
    const label = day.slice(5).replace("-", "/");
    execPoints.push({ label, value: cumExec });
    recPoints.push({ label, value: cumRec });
  }
  if (!sorted.length) {
    execPoints.push({ label: "—", value: 0 });
    recPoints.push({ label: "—", value: 0 });
  }

  // Two cumulative series rendered as bars for recoveries behind the line
  // for executions — one shared x-axis.
  const W = 460, H = 190, P = { l: 44, r: 16, t: 14, b: 26 };
  const max = Math.max(1, ...execPoints.map(p => p.value));
  const iw = W - P.l - P.r, ih = H - P.t - P.b;
  const step = execPoints.length > 1 ? iw / (execPoints.length - 1) : 0;
  const xy = execPoints.map((p, i) => [
    P.l + (execPoints.length > 1 ? i * step : iw / 2),
    P.t + ih - (p.value / max) * ih,
  ]);
  const grid = [0, 0.5, 1].map(f => {
    const y = P.t + ih - f * ih;
    return `<line x1="${P.l}" y1="${y}" x2="${W - P.r}" y2="${y}" stroke="${CHART_COLORS.GRID}" stroke-width="1"/>
      <text x="${P.l - 6}" y="${y + 3}" text-anchor="end" font-size="9" fill="${CHART_COLORS.MUTED}">${Math.round(max * f)}</text>`;
  }).join("");
  const line = xy.map((p, i) => `${i ? "L" : "M"}${p[0].toFixed(1)},${p[1].toFixed(1)}`).join(" ");
  const dots = xy.map((p, i) =>
    `<circle cx="${p[0].toFixed(1)}" cy="${p[1].toFixed(1)}" r="3.2" fill="#fff" stroke="${CHART_COLORS.ACCENT}" stroke-width="2"/>`).join("");
  const xlabels = execPoints.map((p, i) =>
    `<text x="${xy[i][0].toFixed(1)}" y="${H - 8}" text-anchor="middle" font-size="9" fill="${CHART_COLORS.MUTED}">${esc(p.label)}</text>`).join("");
  const recDots = recPoints.map((p, i) => {
    if (!p.value) return "";
    const y = P.t + ih - (p.value / max) * ih;
    return `<circle cx="${xy[i][0].toFixed(1)}" cy="${y.toFixed(1)}" r="3" fill="${CHART_COLORS.SUCCESS}" stroke="#fff" stroke-width="1.4"/>
      <text x="${xy[i][0].toFixed(1)}" y="${(y - 7).toFixed(1)}" text-anchor="middle" font-size="9" fill="${CHART_COLORS.SUCCESS}" font-weight="600">${p.value}</text>`;
  }).join("");

  document.getElementById("chart-trend").innerHTML = `
    <svg viewBox="0 0 ${W} ${H}" role="img" aria-label="Cumulative executions and recoveries over time">
      ${grid}
      <path d="${line}" fill="none" stroke="${CHART_COLORS.ACCENT}" stroke-width="2.2" stroke-linejoin="round" stroke-linecap="round"/>
      ${dots}${recDots}${xlabels}
    </svg>
    <div class="chart-legend-row-flex">
      <span class="chart-legend-inline"><span class="chart-legend-dot" style="background:${CHART_COLORS.ACCENT}"></span>Cumulative executions</span>
      <span class="chart-legend-inline"><span class="chart-legend-dot" style="background:${CHART_COLORS.SUCCESS}"></span>Cumulative webhook recoveries</span>
    </div>`;
}

function renderFailureReasons(re) {
  const counts = {};
  for (const t of re.transactions) {
    const key = t.failure_reason || "recovered / n-a";
    counts[key] = (counts[key] || 0) + 1;
  }
  const items = Object.entries(counts)
    .map(([label, value]) => ({ label: label.replace(/_/g, " "), value }))
    .sort((a, b) => b.value - a.value);
  document.getElementById("chart-reasons").innerHTML =
    barChart({ items });
}

function renderOutcomes(re) {
  const counts = { action: 0, stop: 0, escalate: 0 };
  for (const t of re.transactions) counts[t.decision] = (counts[t.decision] || 0) + 1;
  document.getElementById("chart-outcomes").innerHTML = donutChart({
    segments: [
      { label: "Action", value: counts.action, color: CHART_COLORS.SUCCESS },
      { label: "Escalate", value: counts.escalate, color: CHART_COLORS.ACCENT },
      { label: "Stop", value: counts.stop, color: CHART_COLORS.MUTED },
    ],
    centerValue: String(re.transactions.length),
    centerLabel: "scenarios",
  });
}

function renderAgentPerformance(ae) {
  const maxRecovered = Math.max(ae.agent.recovered_paise, ae.benchmark.recovered_paise, 1);
  const maxNet = Math.max(ae.agent.net_recovered_paise, ae.benchmark.net_recovered_paise, 1);
  const html = compareChart({
    metrics: [
      { label: "₹ Recovered", agent: fmtLakhs(ae.agent.recovered_paise), benchmark: fmtLakhs(ae.benchmark.recovered_paise),
        agentScale: ae.agent.recovered_paise / maxRecovered, benchScale: ae.benchmark.recovered_paise / maxRecovered },
      { label: "Net ₹ recovered", agent: fmtLakhs(ae.agent.net_recovered_paise), benchmark: fmtLakhs(ae.benchmark.net_recovered_paise),
        agentScale: ae.agent.net_recovered_paise / maxNet, benchScale: ae.benchmark.net_recovered_paise / maxNet },
      { label: "Targeting precision", agent: fmtPct(ae.agent.targeting_precision), benchmark: fmtPct(ae.benchmark.targeting_precision),
        agentScale: ae.agent.targeting_precision, benchScale: ae.benchmark.targeting_precision },
      { label: "Bad interventions", agent: String(ae.agent.bad_interventions), benchmark: String(ae.benchmark.bad_interventions),
        agentScale: ae.agent.bad_interventions / Math.max(1, ae.agent.bad_interventions, ae.benchmark.bad_interventions),
        benchScale: ae.benchmark.bad_interventions / Math.max(1, ae.agent.bad_interventions, ae.benchmark.bad_interventions) },
    ],
  });
  document.getElementById("chart-agent-performance").innerHTML =
    html + `<div class="chart-legend-row-flex">
      <span class="chart-legend-inline"><span class="chart-legend-dot" style="background:${CHART_COLORS.ACCENT}"></span>Recovery Agent</span>
      <span class="chart-legend-inline"><span class="chart-legend-dot" style="background:${CHART_COLORS.MUTED}"></span>Deterministic Benchmark</span>
    </div>`;
}

/* Amount exposure by decision: where the at-risk money sits right now
   (actioned / awaiting human judgment / withheld). */
function renderExposure(re) {
  const buckets = { action: 0, stop: 0, escalate: 0 };
  for (const t of re.transactions) buckets[t.decision] = (buckets[t.decision] || 0) + t.amount_paise;
  const max = Math.max(1, ...Object.values(buckets));
  const order = [
    { label: "Action", value: buckets.action, color: CHART_COLORS.SUCCESS },
    { label: "Escalate", value: buckets.escalate, color: CHART_COLORS.ACCENT },
    { label: "Stop", value: buckets.stop, color: CHART_COLORS.MUTED },
  ];
  document.getElementById("chart-methods").innerHTML = stackedBarChart({
    groups: order.map(o => ({
      label: `${o.label} · ${fmtINR(o.value)}`,
      parts: [{ value: (o.value / max) * 100, color: o.color, label: o.label }],
    })),
    legend: null,
  });
}

load();
