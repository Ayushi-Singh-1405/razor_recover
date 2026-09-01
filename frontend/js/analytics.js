/* Analytics page: simulated benchmark detection stats + Agent Evaluation
   (agent vs deterministic benchmark) — data from /dashboard/summary. */

import { getMe, getSummary } from "./api.js";
import { setMe, setSummary } from "./state.js";
import { renderNav } from "./navigation.js";
import { esc, fmtLakhs, fmtPct } from "./utils.js";

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
  }
}

function render(summary) {
  const d = summary.detection;
  document.getElementById("detection-stats").innerHTML = `
    <span><strong>${d.total_events.toLocaleString("en-IN")}</strong> transactions</span>
    <span>· <strong>${d.at_risk.toLocaleString("en-IN")}</strong> at risk</span>
    <span>· <strong>${esc(fmtLakhs(d.revenue_at_risk_paise))}</strong> at-risk value</span>
    <span class="provenance-tag provenance-simulated">SIMULATED</span>`;

  const ae = summary.agent_evaluation;
  document.getElementById("eval-agent-candidates").textContent = ae.agent.candidate_decisions;
  document.getElementById("eval-bench-candidates").textContent = ae.benchmark.candidate_decisions;
  document.getElementById("eval-agent-recovered").textContent = ae.agent.successful_recoveries;
  document.getElementById("eval-bench-recovered").textContent = ae.benchmark.successful_recoveries;
  document.getElementById("eval-agent-recovered-l").textContent = fmtLakhs(ae.agent.recovered_paise);
  document.getElementById("eval-bench-recovered-l").textContent = fmtLakhs(ae.benchmark.recovered_paise);
  document.getElementById("eval-agent-bad").textContent = ae.agent.bad_interventions;
  document.getElementById("eval-bench-bad").textContent = ae.benchmark.bad_interventions;
  document.getElementById("eval-agent-net").textContent = fmtLakhs(ae.agent.net_recovered_paise);
  document.getElementById("eval-bench-net").textContent = fmtLakhs(ae.benchmark.net_recovered_paise);
  document.getElementById("eval-agent-precision").textContent = fmtPct(ae.agent.targeting_precision);
  document.getElementById("eval-bench-precision").textContent = fmtPct(ae.benchmark.targeting_precision);
  document.getElementById("verdict-callout").textContent = ae.verdict_text;

  document.getElementById("attribution").textContent =
    "Agent decisions produced by OPENROUTER_MODEL routing (openrouter/free auto-router) "
    + "across the full 662-event run; ground truth is evaluation-only and never shown to the agent.";
}

load();
