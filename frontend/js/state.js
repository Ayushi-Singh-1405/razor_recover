/* Shared page state — populated once per page load from the API.
   Pages read from here instead of re-fetching or passing globals around. */

const state = {
  me: null,       // { id, email, name } | null
  summary: null,  // /dashboard/summary payload | null
};

export function setMe(me) { state.me = me; }
export function setSummary(summary) { state.summary = summary; }
export function getState() { return state; }
