/* Dashboard page: identity, hero stats, Live Execution (rows, audit trail
   panels, escalation Approve/Dismiss), System Status. */

import { approveEscalation, dismissEscalation, getMe, getSummary } from "./api.js";
import { setMe, setSummary } from "./state.js";
import { renderNav } from "./navigation.js";
import {
  DECISION_BADGES, DECISION_BADGE_TEXT, DECISION_ICONS,
  detailsText, esc, fmtINR, fmtLakhs, fmtTime, groupChain,
  humanReason, wasCorrectedDuringDevelopment,
} from "./utils.js";

function rowHtml(t) {
  const shortId = "#" + t.transaction_id.slice(0, 8);
  const badge = `<span class="badge ${DECISION_BADGES[t.decision] || "badge-neutral"}">${DECISION_BADGE_TEXT[t.decision] || esc(t.decision)}</span>`;

  let outcome;
  if (t.decision === "action") {
    outcome = `<strong>Payment Link created → ${t.recovered ? "Recovered" : "Awaiting payment"}</strong>`;
  } else {
    outcome = `${esc(humanReason(t.reason))} · <span class="exec-not-executed">API call: NOT EXECUTED</span>`;
  }

  const escalationActions = t.decision === "escalate" ? `
    <div class="escalation-actions">
      <button class="btn btn-primary" data-escalation-action="approve">Approve</button>
      <button class="btn btn-danger-outline" data-escalation-action="dismiss">Dismiss</button>
    </div>
    <div class="alert alert-danger hidden" data-row-error></div>` : "";

  const corrected = wasCorrectedDuringDevelopment(t.audit_chain);
  const correctionCallout = corrected ? `
    <div class="callout">
      <span>Classification corrected during development (STOP → ESCALATE) — see full history</span>
      <button class="correction-toggle" data-toggle-full="1">Show full history</button>
    </div>` : "";

  return `
    <div class="exec-row" data-txn="${esc(t.transaction_id)}">
      <div class="exec-main">
        <span class="exec-icon">${DECISION_ICONS[t.decision] || ""}</span>
        <div class="exec-info">
          <div class="exec-title">
            <strong>${esc(t.scenario || "(unnamed scenario)")}</strong>
            ${badge}
            <span class="text-muted text-xs">${esc(shortId)}</span>
          </div>
          <div class="exec-outcome">${outcome}</div>
          <div class="text-muted text-xs">${esc(fmtINR(t.amount_paise))}</div>
        </div>
        <button class="audit-toggle" data-toggle-audit="1">Audit trail</button>
      </div>
      ${escalationActions}
      <div class="audit-panel hidden">
        ${correctionCallout}
        ${groupChain(t.audit_chain).map(g => `
          <div class="audit-event">
            <div>
              <strong>${esc(g.event)}</strong>
              <span class="text-muted text-xs">· latest ${esc(fmtTime(g.latest.timestamp))}</span>
            </div>
            <div class="audit-details">${detailsText(g.latest.details)}</div>
            ${g.count > 1 ? `<div class="text-muted text-xs verified-note">Verified consistent across ${g.count} runs</div>` : ""}
          </div>`).join("")}
        ${corrected ? fullHistoryHtml(t.audit_chain) : ""}
      </div>
    </div>`;
}

function fullHistoryHtml(chain) {
  return `<div class="full-history">
    <h3 class="text-xs" style="text-transform: uppercase; letter-spacing: 0.03em;">Full chronological history</h3>
    ${chain.map(e => `
      <div class="audit-event">
        <div>
          <strong>${esc(e.event)}</strong>
          <span class="text-muted text-xs">· ${esc(fmtTime(e.timestamp))}</span>
        </div>
        <div class="audit-details">${detailsText(e.details)}</div>
      </div>`).join("")}
  </div>`;
}

function renderLiveExecution(re) {
  document.getElementById("exec-summary").innerHTML = `
    <span><strong>${re.scenarios_run}</strong> scenarios</span>
    <span>· <strong>${re.actions_taken}</strong> actions</span>
    <span>· <strong>${re.stopped}</strong> stopped</span>
    <span>· <strong>${re.escalated}</strong> escalated</span>
    <span>· <strong>${esc(fmtINR(re.real_paise_recovered))}</strong> recovered</span>`;
  document.getElementById("exec-rows").innerHTML = re.transactions.map(rowHtml).join("");
}

// Expand/collapse + escalation actions via delegation
document.addEventListener("click", (ev) => {
  const auditToggle = ev.target.closest("[data-toggle-audit]");
  if (auditToggle) {
    const panel = auditToggle.closest(".exec-row").querySelector(".audit-panel");
    panel.classList.toggle("hidden");
    auditToggle.textContent = panel.classList.contains("hidden") ? "Audit trail" : "Hide audit trail";
    return;
  }
  const correctionToggle = ev.target.closest("[data-toggle-full]");
  if (correctionToggle) {
    const panel = correctionToggle.closest(".audit-panel").querySelector(".full-history");
    panel.classList.toggle("hidden");
    correctionToggle.textContent = panel.classList.contains("hidden")
      ? "Show full history" : "Hide full history";
    return;
  }
  handleEscalationAction(ev);
});

async function handleEscalationAction(ev) {
  const btn = ev.target.closest("[data-escalation-action]");
  if (!btn) return;
  const row = btn.closest(".exec-row");
  const action = btn.dataset.escalationAction; // approve | dismiss
  const txnId = row.dataset.txn;
  const errEl = row.querySelector("[data-row-error]");
  const buttons = row.querySelectorAll("[data-escalation-action]");

  if (action === "approve" &&
      !confirm("Approve manual recovery? A real Razorpay payment link will be created.")) {
    return;
  }

  buttons.forEach(b => b.disabled = true);
  errEl.classList.add("hidden");
  try {
    const body = action === "approve"
      ? await approveEscalation(txnId)
      : await dismissEscalation(txnId);

    const outcomeEl = row.querySelector(".exec-outcome");
    const badgeEl = row.querySelector(".badge");
    if (action === "approve") {
      outcomeEl.innerHTML =
        `<strong>✓ MERCHANT APPROVED → Payment Link Created</strong> ` +
        `<span class="text-muted text-xs">triggered_by: merchant_manual_approval</span> · ` +
        `<a href="${esc(body.short_url)}" target="_blank" rel="noopener">Open payment link</a>`;
      badgeEl.className = "badge badge-success";
      badgeEl.textContent = "ACTION";
    } else {
      outcomeEl.innerHTML =
        `<strong>Dismissed by ${esc(body.dismissed_by)}</strong> ` +
        `<span class="exec-not-executed">API call: NOT EXECUTED</span>`;
      badgeEl.className = "badge badge-neutral";
      badgeEl.textContent = "DISMISSED";
    }
    buttons.forEach(b => b.remove());
  } catch (err) {
    errEl.textContent = "Action failed: " + err.message;
    errEl.classList.remove("hidden");
    buttons.forEach(b => b.disabled = false);
  }
}

async function load() {
  // file:// can't reach the API or same-origin cookies — show instructions.
  if (window.location.protocol === "file:") {
    document.getElementById("status").textContent =
      "This page was opened as a local file. Start the backend (from backend/: "
      + "../venv/bin/uvicorn main:app --reload) and open http://localhost:8000/dashboard instead.";
    return;
  }

  try {
    const me = await getMe();
    setMe(me);
    renderNav("dashboard", me);
    document.getElementById("merchant-name").textContent =
      me.name ? "Welcome, " + me.name.split(" ")[0] : "Welcome";
    document.getElementById("merchant-email").textContent = me.email;
    document.getElementById("avatar").textContent =
      (me.name || me.email || "?").trim()[0].toUpperCase();
  } catch (err) {
    document.getElementById("status").textContent =
      "Could not load session. Is the backend running?";
    return;
  }

  try {
    const summary = await getSummary();
    setSummary(summary);

    // Hero stats (simulated benchmark detection)
    const detection = summary.detection;
    document.getElementById("hero-stats").innerHTML =
      `<strong>${esc(fmtLakhs(detection.revenue_at_risk_paise))}</strong> at risk · ` +
      `<strong>${detection.total_events.toLocaleString("en-IN")}</strong> transactions ` +
      `<span class="provenance-tag provenance-simulated">SIMULATED</span>`;

    // System Status: LLM Execution Authority from the live API response
    // (never hardcoded — reflects whatever the policy currently grants).
    const reAuth = summary.real_execution.llm_execution_authority;
    document.getElementById("llm-auth-dot").className =
      "status-dot " + (reAuth ? "status-dot-active" : "status-dot-disabled");
    document.getElementById("llm-auth-value").textContent = reAuth
      ? "Granted"
      : "Disabled — benchmark did not justify autonomous authority";

    renderLiveExecution(summary.real_execution);
  } catch (err) {
    document.getElementById("exec-summary").textContent =
      "Could not load execution data. Is the backend running?";
  }
}

load();
