/* Shared top navigation. Call renderNav(activeKey, me) after loading the
   session (me may be null on public pages — shows a Sign in link). */

import { esc } from "./utils.js";

const LINKS = [
  { key: "dashboard", label: "Dashboard", href: "/dashboard" },
  { key: "analytics", label: "Analytics", href: "/analytics" },
  { key: "audit", label: "Audit", href: "/audit" },
  { key: "developers", label: "Developers", href: "/developers" },
  { key: "resources", label: "Resources", href: "/resources" },
  { key: "security", label: "Security", href: "/security" },
];

export function renderNav(activeKey, me = null) {
  const mount = document.getElementById("nav-mount");
  if (!mount) return;

  const links = LINKS.map(l =>
    `<a class="nav-link${l.key === activeKey ? " active" : ""}" href="${l.href}">${l.label}</a>`).join("");

  const right = me
    ? `<span class="nav-email">${esc(me.email)}</span><a class="nav-link" href="/auth/logout">Sign out</a>`
    : `<a class="nav-link" href="/login">Sign in</a>`;

  mount.innerHTML = `
    <nav class="topnav">
      <a class="nav-brand" href="/dashboard">repechage<span class="accent">.</span></a>
      <div class="nav-links">${links}</div>
      <div class="nav-right">${right}</div>
    </nav>`;
}
