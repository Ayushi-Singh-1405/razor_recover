/* API layer — every backend call goes through here.
   Same-origin credentials (httpOnly session cookie), JSON bodies,
   and a single 401 -> /login redirect convention. */

async function apiFetch(path, options = {}) {
  const res = await fetch(path, { credentials: "same-origin", ...options });
  if (res.status === 401) {
    window.location.replace("/login");
    throw new Error("Not authenticated");
  }
  const body = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(body.detail || `HTTP ${res.status}`);
  return body;
}

export const getMe = () => apiFetch("/auth/me");
export const getSummary = () => apiFetch("/dashboard/summary");
export const approveEscalation = txnId =>
  apiFetch(`/dashboard/escalations/${txnId}/approve`, { method: "POST" });
export const dismissEscalation = txnId =>
  apiFetch(`/dashboard/escalations/${txnId}/dismiss`, { method: "POST" });
