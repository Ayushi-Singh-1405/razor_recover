/* Audit page: full chronological audit trail across all demo transactions,
   built from /dashboard/summary real_execution.transactions[].audit_chain.
   Read-only; no backend calls beyond the existing summary. */

import { getMe, getSummary } from "./api.js";
import { setMe, setSummary } from "./state.js";
import { renderNav } from "./navigation.js";
import { esc, fmtINR, fmtTime } from "./utils.js";

let transactions = [];
let entries = []; // flattened chronological {timestamp, event, details, scenario, txnId}

async function load() {
  if (window.location.protocol === "file:") {
    document.getElementById("status").textContent =
      "This page was opened as a local file. Start the backend (from backend/: "
      + "../venv/bin/uvicorn main:app --reload) and open http://localhost:8000/audit instead.";
    return;
  }

  try {
    const me = await getMe();
    setMe(me);
    renderNav("audit", me);
  } catch (err) {
    document.getElementById("status").textContent =
      "Could not load session. Is the backend running?";
    return;
  }

  try {
    const summary = await getSummary();
    setSummary(summary);
    prepare(summary.real_execution.transactions);
    render();
  } catch (err) {
    document.getElementById("audit-error").textContent =
      "Could not load audit data. Is the backend running?";
  }
}

function prepare(txns) {
  transactions = txns;
  entries = [];
  for (const t of txns) {
    for (const e of t.audit_chain) {
      entries.push({
        timestamp: e.timestamp,
        event: e.event,
        details: e.details || {},
        scenario: t.scenario || "(unnamed)",
        txnId: t.transaction_id,
        amount_paise: t.amount_paise,
        recovered: t.recovered,
      });
    }
  }
  entries.sort((a, b) => a.timestamp.localeCompare(b.timestamp));

  const scenarios = [...new Set(entries.map(e => e.scenario))].sort();
  const events = [...new Set(entries.map(e => e.event))].sort();
  document.getElementById("filter-scenario").innerHTML =
    `<option value="">All scenarios</option>` +
    scenarios.map(s => `<option value="${esc(s)}">${esc(s)}</option>`).join("");
  document.getElementById("filter-event").innerHTML =
    `<option value="">All events</option>` +
    events.map(v => `<option value="${esc(v)}">${esc(v)}</option>`).join("");

  document.getElementById("filter-scenario").addEventListener("change", render);
  document.getElementById("filter-event").addEventListener("change", render);
}

function render() {
  const scenario = document.getElementById("filter-scenario").value;
  const event = document.getElementById("filter-event").value;

  const filtered = entries.filter(e =>
    (!scenario || e.scenario === scenario) && (!event || e.event === event));

  document.getElementById("audit-count").textContent =
    `${filtered.length} entries (${entries.length} total) across ${transactions.length} transactions`;

  document.getElementById("audit-table").innerHTML = filtered.slice().reverse().map(e => `
    <tr>
      <td class="text-muted text-xs">${esc(fmtTime(e.timestamp))}</td>
      <td>${esc(e.scenario)}</td>
      <td><strong>${esc(e.event)}</strong></td>
      <td class="audit-details">${Object.entries(e.details)
        .map(([k, v]) => `${esc(k)}=${esc(String(v))}`).join(" · ") || "—"}</td>
      <td class="text-muted text-xs">${esc(fmtINR(e.amount_paise))}${e.recovered ? " · recovered" : ""}</td>
    </tr>`).join("") || `<tr><td colspan="5" class="text-muted">No entries match the filters.</td></tr>`;
}

load();
