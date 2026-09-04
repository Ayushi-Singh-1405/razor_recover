# Repechage — UI/UX Design & Version 2 Implementation Plan

**Project:** Repechage  
**Product:** Agentic Payment Recovery  
**Version:** 2.0  
**Status:** UI redesign specification

---

## 1. Design Direction

Repechage should look like a serious fintech/payment-infrastructure product, **not an AI dashboard**.

### Primary visual references

- The provided Fingoals financial dashboard for dashboard composition, cards, charts, spacing, and whitespace.
- Stripe for public landing-page structure, developer experience, and resource presentation.
- Razorpay for the overall fintech/infrastructure feel and restrained blue accent language.
- The existing Repechage application and already-built functionality.

### Design keywords

**Clean · Fintech · Structured · Precise · Professional · Light · Technical · Trustworthy**

### Avoid

- Generic AI aesthetics
- Dark-blue AI themes
- Neon/glowing interfaces
- Excessive rounded cards
- Chatbot-like UI
- Glassmorphism
- Futuristic 3D effects
- Unnecessary animations
- Decorative UI that does not communicate product functionality

---

# 2. Core Visual Principle

> **Clean fintech infrastructure, not AI aesthetics.**

The interface should feel like something a merchant could realistically use to monitor payment recovery.

The product should communicate:

- Reliability
- Transparency
- Financial control
- Operational maturity
- Developer friendliness
- Human oversight

---

# 3. Color System

## Primary

Use a predominantly white interface.

```text
Background:        #FFFFFF
Surface:           #FFFFFF
Secondary surface: #F7F8FA
Border:            #E5E7EB
```

## Text

Use:

- Near-black for primary text
- Muted gray for secondary text
- Light gray for tertiary information

Avoid making everything pure black.

## Ocean Blue

Blue is the primary brand/action accent.

Approximate direction:

```text
Primary blue: #2563EB
Deep blue:    #1D4ED8
Light blue:   #EFF6FF
Blue border:  #BFDBFE
```

Exact values may be adjusted slightly for visual harmony.

### Blue should be used for

- Primary buttons
- Links
- Active navigation
- Selected states
- Important metrics
- Flow-chart connectors
- Interactive elements
- Landing-page decorative accents

### Blue should not dominate

The interface should remain predominantly white and neutral.

---

# 4. Branding & Typography

## Product name

**Repechage**

The wordmark should have a distinctive font that differs from the main UI font.

The goal is:

> **repechage** feels like a recognizable product brand.

The rest of the interface should use a highly readable modern UI font.

## Developer/resource page naming

When inside developer or resource areas:

**repechage Developers**

or

**repechage Docs**

Where:

- `repechage` = black
- `Developers` / `Docs` = ocean blue

The Repechage wordmark should consistently use the distinctive brand font.

## UI font

Use a clean modern sans-serif.

Suitable directions:

- Inter
- Geist
- Manrope
- IBM Plex Sans

Do not use an overly futuristic font.

---

# 5. Landing Page

The landing page is the public-facing Repechage website.

It should feel like a fintech infrastructure company website rather than a generic SaaS or AI landing page.

## Header

```text
REVОCO                         Product   Developers   Resources

                                      Log in   [ Get started ]
```

### Header requirements

- Repechage logo/name at top-left
- Product / Developers / Resources navigation
- Login at top-right
- Get Started primary CTA
- White/light background
- Minimal border or separator where appropriate

---

# 6. Landing Page Hero

The hero should be **static**.

### Do not use

- Video hero
- Constantly moving dashboard
- WebGL
- 3D AI objects
- Glowing AI orb
- Particle fields
- Excessive motion

### Hero structure

```text
                     REVОCO

             Recover failed payments.
                    Automatically.

       AI-powered payment recovery that detects,
       diagnoses and recovers failed transactions
       while keeping merchants in control.

           [ Get started ]   [ View GitHub ]

                     ↓

        ┌───────────────────────────────┐
        │                               │
        │       REVОCO DASHBOARD        │
        │          PREVIEW              │
        │                               │
        └───────────────────────────────┘
```

The dashboard preview should represent the actual Repechage product rather than a generic finance dashboard.

---

# 7. Landing Page Flow Visualization

Include the core Repechage flow prominently:

```text
Detect → Diagnose → Decide → Policy Gate → Act → Audit
```

A more detailed static flow can be:

```text
┌─────────┐      ┌──────────┐      ┌────────┐
│ Detect  │ ───→ │ Diagnose │ ───→ │ Decide │
└─────────┘      └──────────┘      └────────┘
                                      │
                                      ↓
                              ┌──────────────┐
                              │  Policy Gate │
                              └──────────────┘
                                      │
                           ┌──────────┴──────────┐
                           ↓                     ↓
                      Recover              Escalate
                           │                     │
                           └──────────┬──────────┘
                                      ↓
                                 ┌─────────┐
                                 │  Audit  │
                                 └─────────┘
```

### Visual treatment

- Thin ocean-blue connectors
- White cards
- Subtle gray borders
- Minimal shadows
- Small-radius corners
- No glowing effects

This should communicate the architecture in a few seconds.

---

# 8. Landing Page Content Sections

Keep the landing page concise and purposeful.

## Section 1 — Hero

Answer:

> What is Repechage?

## Section 2 — Recovery Flow

Show:

**Detect → Diagnose → Decide → Policy Gate → Act → Audit**

## Section 3 — Agent Intelligence

Explain that Repechage evaluates permitted signals such as:

- Transaction context
- Customer history
- Payment failure information
- Recovery history
- Other permitted recovery signals

## Section 4 — Human Control

Show:

```text
AI decides
     ↓
Policy Gate
     ↓
 ┌───┴────┐
 ↓        ↓
Act    Escalate
          ↓
      Merchant
       Review
```

Emphasize that uncertain/high-risk decisions can be escalated to the merchant.

## Section 5 — Results

Show actual evaluation metrics.

**Never fabricate metrics.**

## Section 6 — Developer Integration

Example:

```text
Built for developers.

Connect payment events to Repechage
and let the recovery engine handle
the decision pipeline.

[ View developer docs ]
[ View GitHub ]
```

## Footer

Include:

- Documentation
- Developers
- Resources
- GitHub
- Data & Security
- Login

---

# 9. Authentication

Top-right public navigation:

```text
Log in
[ Get started ]
```

Authentication should lead into the merchant workspace.

Keep login/signup visually simple.

---

# 10. Authenticated Merchant Application

After login, Repechage changes from a marketing website into an operational merchant dashboard.

The application uses a persistent sidebar.

---

# 11. Sidebar

### Navigation structure

```text
REVОCO

Overview

WORKSPACE
Recovery
Analytics
Audit Trail

DEVELOPMENT
Developers

RESOURCES
Resources

────────────

Settings
```

### Principles

- Persistent desktop sidebar
- White background
- Very subtle right border
- Simple line icons
- Minimal active-state treatment
- No large black floating navigation pills
- No excessive rounded navigation buttons

### Active item

Use a subtle blue highlight or indicator.

---

# 12. Top Bar

Recommended structure:

```text
Search       ?       Notifications       [A] Merchant ▾
```

Keep it minimal.

Merchant identity should be visible without consuming excessive space.

---

# 13. Overview = Main Merchant Workspace

The Overview page is the operational heart of Repechage.

It should reorganize the already-built functionality rather than replace it.

### Overview header

```text
Overview

Monitor payment recovery and review decisions
that require your attention.
```

---

# 14. KPI Summary

Place a small KPI row near the top.

Example:

```text
┌─────────────────┐ ┌─────────────────┐ ┌─────────────────┐
│ At-risk amount  │ │ Recovered       │ │ Recovery rate   │
│                 │ │                 │ │                 │
│ ₹1.24L          │ │ ₹86K            │ │ 69.4%           │
└─────────────────┘ └─────────────────┘ └─────────────────┘
```

Use actual values from the system.

Avoid fake/demo numbers unless explicitly labelled as illustrative.

---

# 15. Main Workspace — Agent Decisions

This is the core Repechage functionality.

### Section

**Agent Decisions**

Use the existing backend decisions.

Example:

```text
Agent Decisions                         View all →

┌─────────────────────────────────────────────────────────┐
│ Payment    Failure          AI Action       Confidence   │
├─────────────────────────────────────────────────────────┤
│ #4821      Insufficient    Recover now       94%        │
│            funds                                      │
│                                                         │
│ #4819      Bank decline    Payment link      87%        │
│                                                         │
│ #4817      High value      Escalate          72%        │
└─────────────────────────────────────────────────────────┘
```

The actual decisions are the product.

Do not replace them with decorative AI cards.

---

# 16. Merchant Approval / Escalations

Make merchant actions highly visible.

### Section

**Merchant Action Required**

Example:

```text
3 decisions require your review

┌────────────────────────────────────────────────────────┐
│ Payment #4817                              ₹12,400     │
│                                                        │
│ Bank decline                                           │
│                                                        │
│ AI recommendation: ESCALATE                            │
│                                                        │
│ Reason: High-value transaction with uncertain          │
│ recovery probability.                                  │
│                                                        │
│ [ Review ]                       [ Approve ] [ Reject ]│
└────────────────────────────────────────────────────────┘
```

This should clearly demonstrate:

> **AI acts autonomously when safe, escalates when uncertain, and keeps the merchant in control.**

---

# 17. System Status Widget

Keep the existing System Status functionality, but make it a compact right-side widget.

Example:

```text
SYSTEM STATUS

● Razorpay Test Mode       Connected
● Policy Gate              Active
● Audit Logging            Active
● AI Decision Engine       Active

Last updated
2 min ago
```

## Desktop placement

Use a main workspace + right-side status rail:

```text
┌──────────────────────────────┬──────────────┐
│                              │ SYSTEM       │
│      Agent Decisions         │ STATUS       │
│                              │              │
├──────────────────────────────┤              │
│                              │              │
│ Merchant approvals           │              │
│                              │              │
└──────────────────────────────┴──────────────┘
```

The status rail should provide quick situational awareness without dominating the page.

---

# 18. Analytics

Analytics should be a dedicated page because recovery/evaluation data deserves more space.

Do not build an excessive analytics system.

## Analytics header

```text
Analytics

Understand recovery performance and
the value generated by Repechage.
```

## KPI row

Examples:

```text
Recovered Revenue
₹86,420

Recovery Rate
69.4%

Successful Recoveries
127

Bad Interventions
4
```

Use actual system/evaluation values.

---

# 19. Analytics — Primary Visualization

Use a **bar chart** for:

### Revenue recovered by failure reason

Concept:

```text
Recovered Revenue

₹
│
│       ███
│ ███   ███
│ ███   ███ ███
│ ███   ███ ███ ███
└────────────────────
  Funds Network Bank Timeout
```

Use actual evaluation data.

The chart should answer:

> **Which failure categories generate the most recovered value?**

---

# 20. Analytics — Secondary Visualization

A line chart may be used for:

### Recovery value over time

Only use it if the existing dataset supports meaningful time-series data.

Do not create a time-series chart simply for visual decoration.

---

# 21. Agent vs Benchmark

This is a high-value evaluation view.

Example:

```text
                  RECOVERY AGENT    BENCHMARK

₹ Recovered          ₹86,420          ₹64,100

Precision              91%              78%

Bad interventions       4                11
```

Use the actual evaluation methodology and values.

The analytics page should demonstrate **business value**, not just model performance.

---

# 22. Audit Trail

The Audit Trail page should emphasize traceability and accountability.

Example:

```text
Audit Trail

Every recovery decision is recorded
for transparency and review.

┌──────────────────────────────────────────────────────┐
│ TIME       EVENT             ACTION          STATUS   │
├──────────────────────────────────────────────────────┤
│ 21:14      Payment #4821     Recover         ✓        │
│ 21:11      Payment #4819     Payment link    ✓        │
│ 20:58      Payment #4817     Escalated       ⚠        │
└──────────────────────────────────────────────────────┘
```

Clicking an event can reveal:

- Decision
- Diagnosis
- Recovery probability
- Recommended action
- Policy result
- Execution result
- Timestamp

Connect this to the existing audit functionality.

---

# 23. Developers

The Developers area should feel like a developer portal rather than another dashboard.

### Header

```text
repechage Developers

Integrate payment recovery into your
existing payment workflow.

[ Quick start ]

[ API Reference ]

[ View GitHub ]
```

Remember:

- `repechage` = black
- `Developers` = ocean blue
- Repechage uses the distinctive brand font

---

# 24. Developer Integration Flow

Use a simple static diagram:

```text
Payment event
      ↓
POST /events
      ↓
Repechage
      ↓
Recovery Agent
      ↓
Policy Gate
      ↓
Recovery action
```

No unnecessary animation.

---

# 25. Resources

Resources should remain lightweight.

Do not turn this into a huge documentation platform.

Example:

```text
Resources

┌─────────────────────┐
│ Data & Security     │
│ How Repechage handles  │
│ payment data.       │
│                     │
│ Read more →         │
└─────────────────────┘

┌─────────────────────┐
│ How Repechage Works    │
│ Understand the      │
│ recovery pipeline.  │
│                     │
│ Read more →         │
└─────────────────────┘

┌─────────────────────┐
│ AI Decision Policy  │
│ How decisions are   │
│ evaluated.          │
│                     │
│ Read more →         │
└─────────────────────┘
```

---

# 26. Data & Security

This is an important page because it directly addresses merchant trust.

Clearly explain:

## Data sent to the AI layer

Only include fields that are genuinely sent by the current implementation, such as:

- Transaction context
- Payment failure information
- Customer history signals
- Recovery history
- Other permitted contextual features

## Never sent to the AI layer

Based on the current system design:

- Card numbers
- CVV
- Bank credentials
- Payment credentials
- `ground_truth_*` evaluation labels

## Policy gate

Explain truthfully that recovery decisions are checked by the deterministic policy gate before an action is executed.

Only make claims that the implementation actually guarantees.

---

# 27. GitHub

Include a GitHub button in at least two locations.

## Landing page

```text
[ View GitHub ↗ ]
```

## Developers

```text
View GitHub ↗
```

Use the actual project repository URL.

Do not create a fake GitHub link.

---

# 28. Cards, Borders & Corners

Version 2 should deliberately reduce the rounded "AI SaaS" appearance.

Recommended approximate values:

```text
Cards:      8px
Buttons:    6px–8px
Inputs:     6px–8px
Large hero: 12px maximum
```

Avoid 20–30px radius cards.

Pill shapes should primarily be used for:

- Status badges
- Tags
- Small labels

---

# 29. Shadows

Prefer borders and whitespace.

Use very subtle shadows only where they improve hierarchy.

Avoid:

- Heavy floating shadows
- Large glowing shadows
- Excessive depth effects

---

# 30. Charts

Charts should look like financial analytics.

### Good

- Bar charts
- Line charts
- Simple donut/pie charts where genuinely useful
- Small KPI sparklines

### Avoid

- 3D charts
- Neon charts
- Glowing charts
- Radar charts unless genuinely necessary
- Animated chart effects
- Decorative charts with no meaningful data

---

# 31. Landing Page Decorative Elements

The landing page is the only area where restrained visual decoration is encouraged.

If gradients are used:

> **Blue only.**

Suitable treatments:

- Very subtle blue radial gradients
- Static blurred blue shapes
- Static abstract curves
- Blue flow lines
- Soft background accents

Avoid:

- Moving flares
- Large colorful gradients
- Neon effects
- Constant animation

The visual target is sophisticated fintech infrastructure.

---

# 32. Responsive Design

## Desktop

Primary demo environment:

**Sidebar + main workspace + right-side status rail**

## Tablet

Sidebar can collapse.

## Mobile

Sidebar becomes a drawer.

Tables can use horizontal scrolling rather than breaking the layout.

---

# 33. Existing Functionality Must Not Be Broken

The UI redesign must work around the existing Repechage system.

### Do not modify unless necessary for UI integration

- Agent decision logic
- Recovery logic
- Policy gate
- Audit logic
- Database schema
- API contracts
- Authentication flow
- Evaluation methodology
- Existing working functionality

The goal is:

> **Rebuild the presentation around the existing system, not rebuild the system.**

---

# 34. Version 2 Scope — MUST HAVE

- [ ] New public landing page
- [ ] Repechage branding
- [ ] Distinctive Repechage wordmark font
- [ ] Login / Signup in header
- [ ] Static dashboard hero
- [ ] Detect → Diagnose → Decide → Policy → Act → Audit flow
- [ ] GitHub button
- [ ] Merchant dashboard sidebar
- [ ] Overview workspace
- [ ] Agent Decisions
- [ ] Merchant Escalations / Approvals
- [ ] System Status widget
- [ ] Analytics page
- [ ] Real bar chart
- [ ] Agent vs Benchmark metrics
- [ ] Audit Trail
- [ ] Developers
- [ ] Resources
- [ ] Data & Security
- [ ] Settings
- [ ] White/light visual system
- [ ] Ocean blue accents
- [ ] Reduced border radius
- [ ] Fintech-oriented typography
- [ ] Responsive layout

---

# 35. Explicitly Out of Scope

Do **not** build:

- [ ] Video hero
- [ ] Animated 3D objects
- [ ] Dark AI theme
- [ ] Neon gradients
- [ ] Excessive glassmorphism
- [ ] Chatbot UI
- [ ] 3D charts
- [ ] Fake metrics
- [ ] Fake integrations
- [ ] Huge documentation platform
- [ ] Unnecessary sub-pages
- [ ] Unnecessary backend changes
- [ ] Unnecessary product functionality

---

# 36. Final Information Architecture

```text
PUBLIC
│
├── Landing
├── Developers
├── Resources
│   └── Data & Security
│
├── Login
└── Sign Up


MERCHANT APPLICATION
│
├── Overview
│   ├── KPI Summary
│   ├── Agent Decisions
│   ├── Merchant Approvals
│   └── System Status
│
├── Recovery
│   ├── At-Risk Payments
│   └── Recovery Actions
│
├── Analytics
│   ├── Recovery Metrics
│   ├── Recovered Revenue
│   └── Agent vs Benchmark
│
├── Audit Trail
│
├── Developers
│   ├── Quick Start
│   ├── API
│   └── GitHub
│
├── Resources
│   ├── How Repechage Works
│   ├── Data & Security
│   └── AI Decision Policy
│
└── Settings
```

---

# 37. Product Story

The UI should support this exact narrative:

```text
PUBLIC LANDING
      ↓
What is Repechage?
      ↓
LOGIN
      ↓
OVERVIEW
What is happening to my payments?
      ↓
RECOVERY
What is the agent doing?
      ↓
ANALYTICS
Is it creating real value?
      ↓
AUDIT TRAIL
Can I trace and trust its decisions?
      ↓
DEVELOPERS
How would I integrate it?
      ↓
RESOURCES / DATA & SECURITY
What happens to my data?
```

The result should feel like a **real payment recovery infrastructure product**, not a collection of hackathon screens.

---

# 38. Implementation Guidance for Claude Code / OpenCode

Use the following principles when handing this specification to an AI coding agent:

1. Inspect the existing Version 2 branch before modifying anything.
2. Preserve all existing backend functionality.
3. Preserve existing API contracts unless a UI integration genuinely requires a change.
4. Reuse existing components where they are structurally sound.
5. Do not introduce mock data where real data already exists.
6. Do not invent metrics.
7. Build the public landing page and authenticated merchant application as distinct experiences.
8. Use the design system in this document consistently.
9. Prefer simple reusable components over duplicated page-specific implementations.
10. Keep the UI responsive.
11. Avoid adding unnecessary dependencies.
12. Test every existing workflow after UI changes.
13. Do not "improve" backend logic while working on the frontend unless explicitly instructed.
14. Do not add animations or visual effects that contradict this specification.
15. Prioritize visual polish, hierarchy, spacing, and clarity over feature count.

---

# 39. Definition of Done — UI V2

The UI redesign is complete when:

### Public experience

- [ ] Landing page immediately explains Repechage.
- [ ] Repechage branding is visually distinctive.
- [ ] Login/Signup is accessible from the header.
- [ ] Static product/dashboard preview is visible.
- [ ] Recovery flow is understandable at a glance.
- [ ] GitHub is accessible.
- [ ] Developer/resource entry points are visible.
- [ ] Page works without unnecessary animation.

### Merchant experience

- [ ] Merchant can reach Overview after login.
- [ ] Existing Agent Decisions remain functional.
- [ ] Existing merchant approval/escalation workflow remains functional.
- [ ] System Status is visible in the right-side rail.
- [ ] Analytics displays real data.
- [ ] Audit Trail displays real events.
- [ ] Developers page is usable.
- [ ] Resources/Data & Security is accessible.
- [ ] Settings remains accessible.

### Visual quality

- [ ] White/light background dominates.
- [ ] Ocean blue is the primary accent.
- [ ] No dark-blue AI theme.
- [ ] No excessive rounded cards.
- [ ] No unnecessary gradients.
- [ ] No excessive animation.
- [ ] Typography has a clear hierarchy.
- [ ] Cards use restrained borders and radius.
- [ ] Dashboard feels like fintech infrastructure.
- [ ] Layout is responsive.

### Technical quality

- [ ] Existing backend behavior is preserved.
- [ ] Existing authentication remains functional.
- [ ] No fake data has been introduced into production-facing metrics.
- [ ] No unnecessary architecture changes were made.
- [ ] Desktop demo flow works reliably.
- [ ] Build passes successfully.
- [ ] README and pitch can be completed after UI freeze.
