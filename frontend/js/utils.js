/* Repechage — shared helpers. No framework, ES module. */

export const esc = s => String(s).replace(/[&<>"']/g,
  c => ({"&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"}[c]));

export const fmtINR = paise =>
  "₹" + (paise / 100).toLocaleString("en-IN", { maximumFractionDigits: 2 });

export const fmtLakhs = paise => "₹" + (paise / 100 / 100000).toFixed(1) + "L";

export const fmtPct = p => Math.round(p * 100) + "%";

export const fmtINRWhole = paise =>
  "₹" + Math.round(paise / 100).toLocaleString("en-IN");

export const fmtTime = iso =>
  new Date(iso).toLocaleString("en-IN",
    { day: "2-digit", month: "short", hour: "2-digit", minute: "2-digit" });

export const REASON_TEXT = {
  attempts_at_cap: "Attempt limit reached",
  already_recovered: "Already recovered",
  amount_above_cap: "Above automated cap",
  low_recoverability: "Low recoverability",
  tier_none: "Not recoverable",
  max_real_recovery_actions_reached: "Action cap reached",
};

export const humanReason = reason =>
  REASON_TEXT[reason] ||
  (reason ? reason.charAt(0).toUpperCase() + reason.slice(1).replace(/_/g, " ") : "—");

export const DECISION_ICONS = {
  action: '<svg viewBox="0 0 24 24" fill="none"><circle cx="12" cy="12" r="10" fill="#16A34A"/><path d="m8.5 12.2 2.4 2.4 4.6-4.9" stroke="#fff" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/></svg>',
  stop: '<svg viewBox="0 0 24 24" fill="none"><circle cx="12" cy="12" r="10" fill="#DC2626"/><path d="M9 9l6 6M15 9l-6 6" stroke="#fff" stroke-width="2" stroke-linecap="round"/></svg>',
  escalate: '<svg viewBox="0 0 24 24" fill="none"><path d="M12 3 22 20H2L12 3z" fill="#D97706"/><path d="M12 9.5v4.5" stroke="#fff" stroke-width="2" stroke-linecap="round"/><circle cx="12" cy="16.8" r="1.1" fill="#fff"/></svg>',
};

export const DECISION_BADGES = { action: "badge-success", stop: "badge-danger", escalate: "badge-warning" };
export const DECISION_BADGE_TEXT = { action: "ACTION", stop: "STOP", escalate: "ESCALATE" };

export function detailsText(details) {
  return Object.entries(details || {})
    .filter(([k]) => k !== "phase")
    .map(([k, v]) => `${esc(k)}=${esc(String(v))}`)
    .join(" · ") || "—";
}

// Group audit entries by event type; keep only the most recent entry
// per type (chain arrives chronological).
export function groupChain(chain) {
  const order = [];
  const groups = new Map();
  for (const e of chain) {
    if (!groups.has(e.event)) {
      groups.set(e.event, { count: 0, latest: null });
      order.push(e.event);
    }
    const g = groups.get(e.event);
    g.count += 1;
    g.latest = e;
  }
  return order.map(ev => ({ event: ev, ...groups.get(ev) }));
}

// SPECIAL CASE (amount_above_cap): both an execution_stopped AND a later
// execution_escalated for the same reason = classification corrected
// during development. Genuine bug-fix trail — shown deliberately.
export function wasCorrectedDuringDevelopment(chain) {
  const stopped = chain
    .filter(e => e.event === "execution_stopped" && e.details && e.details.reason === "amount_above_cap")
    .map(e => e.timestamp);
  if (!stopped.length) return false;
  return chain.some(e =>
    e.event === "execution_escalated" &&
    e.details && e.details.reason === "amount_above_cap" &&
    stopped.some(t => e.timestamp > t));
}
