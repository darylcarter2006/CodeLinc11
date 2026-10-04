# Handoff: Coverage Compass front end

Coverage Compass is a conversational life insurance needs analyzer built for the codeLinc 11 coding challenge (Path 2: right-size life insurance coverage). This folder holds a working single-file prototype and the design tokens. Your job is to rebuild it inside this repository's existing front end, following the repo's conventions.

## Files in this folder

| File | What it is |
| --- | --- |
| `HANDOFF.md` | This spec. It is the source of truth for behavior. |
| `prototype.html` | The working prototype. Open it in a browser to see every screen. Use it as a visual and behavioral reference, not as code to paste in. |
| `design-tokens.json` | Colors, type, spacing and radius tokens, each with a usage note. |

## Step 0: inspect the repo and plan before you write code

1. Find the framework, router, styling approach (CSS modules, Tailwind, styled-components…), state management, test runner and folder conventions.
2. Find what already exists: auth, an API client, a backend that can call an LLM, existing pages that overlap with these screens.
3. Reply with a short plan: files you'll add or change, how each screen maps to a route and component, and where the needs calculation and the parser will live. **Wait for my OK before you implement.**
4. Ask me if anything below conflicts with what's in the repo. Prefer the repo's existing patterns over the prototype's.

## Ground rules

- **The math is deterministic code. The AI never calculates the coverage number.** The AI only (a) pulls fields out of free text during onboarding and (b) explains the math in the Chat tab.
- **No LLM API keys in the browser.** The prototype calls Claude through a sandbox-only `window.claude.use("sample")` API. Replace every one of those calls with a call to a backend endpoint (existing or new; propose one in your plan).
- **Prototype auth is fake.** It stores name and email in `localStorage` and never stores passwords. If the repo has real auth, use it. If not, keep the sign-up/log-in UI behind an `auth` service interface so a real provider can be dropped in later, and **never store passwords on the client**.
- **Persistence behind an interface.** The prototype uses `localStorage` keys `cc-account`, `cc-session`, `cc-profile`, `cc-log` and `cc-steps`. Put profile reads and writes behind a `profileStore` (or the repo's equivalent) so it can move to the backend.
- **Light theme only.** No dark mode.
- **Lincoln Financial branding.** The team has been given permission to use the Lincoln Financial logo and name in the UI (updated October 3, 2026; this replaces the earlier "original brand only" rule). Use only official logo files, unaltered: no redrawing, recoloring or stretching. The browser-tab icons in `frontend/public/` are cut from the official portrait mark. The palette is inspired by the challenge materials. The footer note stays.
- Keep code minimal: no features beyond this spec. Comments go on major sections only, one to two sentences each.

## User flow

```
Sign up / Log in ──► Onboarding chat ──► (confirm) ──► App tabs
        │                                               ├─ Dashboard   (default)
        └─ "Explore with example data" ───────────────► ├─ Breakdown
                                                        ├─ My info
                                                        └─ Chat
```

Routing logic (prototype `route()`):

- Not signed in, and not in example mode → **Auth**.
- Signed in, profile not confirmed → **Onboarding** (resumes if partially answered).
- Signed in and confirmed, or in example mode → **App tabs**. The tabs and the account button (avatar initial + "Sign out", or "Exit example" in example mode) sit at the right of the navy top bar. Tabs only show inside the app.
- Each tab should be deep-linkable (`#dashboard`, `#breakdown`, `#info`, `#chat` in the prototype; use real routes if the repo has a router).

## Data model

```ts
type Dep = "partner" | "kids" | "relative" | "none";
type College = "public" | "half" | "none";

interface Profile {
  deps: Dep[];            // ["none"] is exclusive
  children: number;       // only meaningful if deps includes "kids"
  youngest: number;       // age of youngest child, in years
  age: number;
  income: number;         // yearly, before taxes, USD
  years: number;          // years of income support (0 if deps is ["none"])
  mortgage: number;       // balance left, USD
  mortgageYears: number;  // 0 if mortgage is 0
  otherDebt: number;      // USD total
  college: College;       // "none" if no kids
  group: number;          // life insurance through work, USD
  policies: number;       // policies they own, USD total
  savings: number;        // savings they want counted, USD
}

interface SavedProfile {
  p: Profile;
  known: (keyof Profile)[];   // fields the user has actually given
  confirmed: boolean;         // true after "Looks right" at the end of onboarding
  updated: number | null;     // epoch ms of the last save
}

interface ChangeLogEntry { at: number; text: string } // e.g. "Yearly income: $85,000 → $95,000"
```

Example profile ("Maya", used for "Explore with example data"):
`{ deps:["partner","kids"], children:2, youngest:3, age:34, income:78000, years:19, mortgage:240000, mortgageYears:26, otherDebt:18000, college:"public", group:156000, policies:0, savings:20000 }`

## Needs calculation (port exactly; prototype `compute()`)

Assumptions: `REPLACE = 0.75`, `FINAL = 15000`, `COLLEGE = { public: 100000, half: 50000, none: 0 }`.

```
kids     = deps has "kids" ? children : 0
entered  = deps has "none" ? 0 : years
years    = max(entered, kids > 0 ? max(0, 18 − youngest) : 0)   # support reaches the youngest's 18th birthday
lines:
  c1 Income replacement = income × 0.75 × years        how: "75% of $X × N years"
                                                        (+ " (until your youngest turns 18; you entered E)" when years > entered)
  c2 Debts to clear      = mortgage + otherDebt
  c3 College             = kids × COLLEGE[college]
  c4 Final expenses      = 15,000
total     = sum of lines
existing  = group + policies + savings
gap       = max(0, total − existing)
suggested = ceil(gap / 25,000) × 25,000
low       = floor(gap × 0.85 / 25,000) × 25,000
high      = ceil(gap × 1.15 / 25,000) × 25,000
termNeed  = max(years, mortgage > 0 ? mortgageYears : 0)
term      = first of [10, 15, 20, 25, 30] that is ≥ termNeed, else 30
```

**Years floor (added October 3, 2026).** If children rely on the person, income support always lasts at least until the youngest turns 18, even when fewer years were entered. The extra years are never hidden: the "how" text, the Dashboard's "Your situation" and My info all say when the estimate uses more years than entered. The backend's `app/domain/compass.py` mirrors this rule. The three test vectors below are unchanged, since each already reaches the youngest's 18th birthday.

When `gap === 0`, the Breakdown headline says what they have already covers the estimate. Don't show a number in that case.

### Test vectors (write unit tests for these)

| Case | Input | total | existing | gap | suggested | low–high | term |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Maya example | profile above | 1,584,500 | 176,000 | 1,408,500 | 1,425,000 | 1,175,000–1,625,000 | 30 |
| Half college | partner+kids, 2 kids, youngest 4, income 85,000, years 18, mortgage 210,000 / 22 yrs, other 12,000, college half, group 170,000, policies 0, savings 15,000 | 1,484,500 | 185,000 | 1,299,500 | 1,300,000 | — | 25 |
| Already covered | deps none, income 60,000, mortgage 0, other 20,000, group 50,000, rest 0 | 35,000 | 50,000 | 0 | 0 | — | 10 |

## Screens

### 1. Sign up / Log in

- Two-column layout (stacks on phones). Left: eyebrow "Life insurance, right-sized", headline "Find the coverage that fits your life, in a short conversation.", one paragraph, and three numbered steps (create account, chat for about three minutes, see your dashboard and update it as life changes).
- Right: card with a Sign up / Log in toggle. Sign up fields: first name, email, password (min 8). Log in: email, password.
- Errors appear inline, one at a time, and say how to fix the problem (see the prototype's copy).
- "Explore with example data instead" link → app tabs with the Maya profile and an example banner.
- After sign-up → Onboarding. After log-in → Onboarding if not confirmed, else Dashboard.

### 2. Onboarding chat (the conversational intake)

Layout: chat card (left, wide) + "Saved so far" card (right) with a progress bar, "N of M saved" in the chat header, and one row per needed field ("Not yet" until filled). Footer note: "You can change any of this later in My info."

Behavior:

- Greeting uses their first name. If some fields are already known, say "Welcome back… let's pick up where we left off."
- Ask **one short question at a time**, in this order, skipping fields whose condition is false or that are already known:

| Field | Condition | Question | Quick replies |
| --- | --- | --- | --- |
| deps | always | First, who depends on your income? For example a partner, kids, or a parent. | My partner · Partner and kids · Just my kids · A parent · No one |
| children | has kids | How many children do you have? | 1 · 2 · 3 |
| youngest | has kids | How old is your youngest? | — |
| age | always | How old are you? | — |
| income | always | What's your yearly income before taxes? A rough number is fine. | $50k · $75k · $100k |
| years | deps not none | (kids) How many years should your income keep supporting them? Many families choose until the youngest is 22, which is N years. / (else) For how many years should your income keep supporting them? | Until my youngest is 22 (kids only) · 10 years · 15 years · 20 years |
| mortgage | always | Do you have a mortgage? If so, about how much is left on it? | No mortgage |
| mortgageYears | mortgage > 0 | About how many years are left on it? | — |
| otherDebt | always | Any other debts, like car loans, student loans or cards? A total is fine. | None |
| college | has kids | Should coverage help pay for college? Fully, about half, or not part of the plan? | Yes, public in-state · About half · Not part of the plan |
| group | always | Do you have life insurance through work? If so, how much? It's often 1 or 2 times salary. | None · 1x salary · 2x salary |
| policies | always | Any life insurance policies you own yourself? If so, the total amount. | None |
| savings | always | Last one: how much savings would you want counted toward your family's needs? | None · $10k · $25k |

- On each user message:
  1. Call the **extraction endpoint** (below). It may return several fields at once and may correct earlier ones ("actually I make 82k").
  2. If the field being asked about wasn't extracted, run the **local parser** on the message as a backstop. When the AI is unavailable, the local parser is the only path, and the flow must still work end to end.
  3. Validate everything (see `clean()` below), merge, mark the fields known, save right away (partial progress persists).
  4. Reply with a short acknowledgement (the AI's `ack`, else "Got it, saved."), plus the AI's `answer` if they asked a question, then the next question.
  5. If nothing usable came back: "I didn't quite catch that. Could you put it another way? A rough number is fine." Show the quick replies again.
- Derived rules when merging: deps `["none"]` → years = 0. mortgage = 0 → mortgageYears = 0 and marked known. Deps without kids → children = 0, youngest = 0, college = "none".
- When nothing is left to ask: "That's everything I need. Here's what I saved:", a summary list, and two buttons: **Looks right, show my dashboard** (→ Dashboard) and **Change something** (→ My info). Either one sets `confirmed = true` and logs "Created your profile in the onboarding chat".

**Extraction endpoint contract** (fast/cheap model tier is fine):

Request: `{ askedField, question, profile, message }`. The prompt the prototype uses:

```
You help fill in a life insurance needs profile from a casual chat.
Extract every field the person states or corrects in their latest message. Fields: deps (array of "partner","kids","relative", or ["none"]), children (count), youngest (age in years), age, income (yearly USD), years (years of income support), mortgage (USD balance left), mortgageYears, otherDebt (USD total), college ("public","half","none"), group (USD life insurance through work; a multiple of salary means multiply by income {income or "unknown"}), policies (USD of policies they own), savings (USD to count). "None" or "no" for a dollar field means 0.
We just asked about "{askedField}": "{question}"
Current profile: {profile JSON}
Latest message: """{message, max 500 chars}"""
Reply with only JSON: {"updates": {only fields clearly stated}, "ack": "a warm acknowledgement of at most 8 words", "answer": "if they asked a question, a calm plain answer under 45 words; otherwise an empty string"}
```

Response: `{ updates: Partial<Profile>, ack: string, answer: string }`. Treat all of it as untrusted: validate on the server and again on the client.

**`clean(updates)`**: keep deps only if every entry is allowed (and collapse to `["none"]` if "none" is present). Keep college only if it's a known value. For number fields, keep finite values ≥ 0, round them, and cap age-like integers (children, youngest, age, years, mortgageYears) at 120. Drop unknown keys.

**Local parser** (prototype `parseLocal`; port it and unit-test it):

- Money: `$240,000`, `85k`, `1.2m`, `2 million`. Words like none / no / nothing / zero → 0.
- Integers: digits, or the number words zero–ten.
- deps keywords: partner|spouse|wife|husband|fiancé → partner. kid|child|son|daughter|baby → kids. parent|mom|dad|mother|father|relative|grand|sibling → relative. "no one / nobody / none / just me / single" → ["none"].
- years: "until … 22" → 22 − youngest. A bare "until" with kids → max(5, 22 − youngest).
- college: half|partial|some → half. no|not|none|skip → none. yes|public|full|all|sure|yeah → public.
- group: "2x / 2× / 2 times" → multiple × income.
- mortgage: rent / no mortgage / paid off → 0.

### 3. Dashboard (default tab)

- Header: eyebrow "Welcome back, {name}" (or "Example dashboard"), title "Your coverage at a glance", "Last updated {date}", buttons **Edit my info** and **Ask about my coverage**.
- Example mode shows a banner: "You're viewing an example for Maya, 34…"
- Four tiles, each with a colored top border: Coverage in place (teal; "N% of the estimated need"), Estimated need (dark blue), Left to cover (orange value; "Starting point $X"), Suggested term (blue; "Matches your longest need (N yrs)").
- Left column:
  - **Your coverage today**: a meter bar (in place = teal, left to cover = orange) with a legend, then three source rows. Coverage through work gets the pill "Tied to your job" (orange), plus "It usually ends if you change jobs." Policies you own: "Stays with you" (teal) or "None yet". Savings you counted: "Counted" / "Not counted".
  - **What the need is made of**: a stacked bar of c1–c4 with a legend, plus a "See the math" link → Breakdown.
  - **Tradeoffs to weigh**: the first two tradeoff cards, plus a "See all" link.
- Right column:
  - **Next steps** checklist. Checked state is per user (rules below).
  - **Your situation** (who relies on you, children, income, years of support, mortgage, other debts) with an Edit link → My info.
  - A teal note: "This dashboard is an educational estimate built from your answers. It isn't a quote or a record of your actual policies."

Next-steps rules: if gap > 0, "Compare term quotes for about {suggested} over {term} years". If group > 0, "Ask HR whether your work coverage can be converted or kept if you leave". If group or policies > 0, "Check the beneficiaries on your existing coverage". If mortgage > 0, years > 0 and |mortgageYears − years| ≥ 5, "Price one policy vs. two shorter, laddered policies". Always: "Update My info after a new child, home or job".

### 4. Breakdown

- **Headline card**: eyebrow "A reasonable starting point" (prefixed "Example result · " in example mode), the big figure (`suggested`), "Comfortable range low – high", and on the right: Suggested term, Total need, Already in place. Below that, a teal note: "You're not starting from zero. What you already have covers about N% of the need. This estimate is a starting point you can adjust, not a verdict."
- **How we got here**: two bars on the same scale ("What the need is made of" c1–c4, and "How it's covered" in place vs. left to cover), each direct-labeled, with hover tooltips. Then a table with each line, its "how" formula, its amount, and a **Why?** button (→ Chat tab with "Why is "{line}" in my estimate, and how was it calculated?"). After that: Total need, minus what's already in place (work + personal + savings), left to cover ("Rounded up to the nearest $25,000: $X"). An orange assumptions note sits below the table.
- **Tradeoffs for your situation**: cards generated from rules (port prototype `tradeoffs()` exactly):
  - Term vs. whole (always): the share of the need that is income + debt, why term fits that shape, and that whole life costs much more. Add a different last sentence when a relative depends on them. Shows a Term/Whole mini comparison.
  - Term length (years > 0 and term > 10): this term vs. the next shorter one, and what age the youngest would be when each ends.
  - Laddering (mortgage > 0, years > 0, |mortgageYears − years| ≥ 5): two policies with amounts and lengths.
  - Work coverage (group > 0): what the starting point would be if work coverage weren't counted.
  - Savings (savings > 0): the tradeoff of counting it.
  - College (kids and college = public): what the starting point would be with "about half".
  - Fewer dependents (deps none).

### 5. My info (edit what the chat saved)

- Subtitle: "Fix anything that was saved wrong, or update it when life changes."
- Four cards in a 2×2 grid (one column on phones):
  - Household: deps as checkbox pills; "No one right now" is exclusive. Children, youngest's age.
  - You: age, income, years of support.
  - Debts: mortgage, years left, other debts.
  - Goals and coverage: college select, work coverage, policies, savings.
- A sticky save bar with a status message and **Save changes**. Validate with inline messages: at least one deps option, every number ≥ 0, and children ≥ 1 if Children is checked.
- On save: diff against the stored profile and write one log entry per changed field ("{Label}: {old} → {new}"). Mark all fields known, save, re-render everything, reset the Chat conversation, and show "Saved N change(s). Your dashboard and breakdown are updated." If nothing changed, show "Nothing changed."
- **Recent changes** card: the last 10 log entries with short dates.
- In example mode, edits apply in memory only and aren't logged.

### 6. Chat (free-form Q&A grounded in their saved coverage)

- Left: a "What I know about your coverage" card (through work, policies, savings, in place (teal), estimated need, left to cover (orange), suggested term) and an "Edit my info" link.
- Right: chat with "New chat", input, and suggested questions built from their data: "What happens to my $156K work coverage if I change jobs?" (if group), "Is $176K enough for my family?", "Term or whole life for me?", "Should I split this into two policies?" (if laddering applies), "Should I count my savings?" (if savings).
- Opening message summarizes their coverage in one sentence.
- Send the last 8 turns plus this standing instruction to the **chat endpoint** and stream the reply:

```
You are the assistant inside Coverage Compass, an educational life insurance needs tool.
Tone: calm, warm, plain language. Define jargon in a few words. Never alarming; avoid words like "shortfall" or "at risk".
Keep answers under 120 words in short paragraphs. No headings or tables. Use the person's own coverage and numbers below and show simple math.
Do not recommend companies or specific products, and do not quote prices. If asked about something unrelated to life insurance planning, gently steer back.
If they mention a life change or a correction, explain the likely effect and tell them they can update it in the My info tab.
Method: income need = 75% of income × years of support; debts = mortgage + other debts; college = $100,000 per child (public) or $50,000 (half); final expenses $15,000; minus coverage in place; rounded up to the nearest $25,000.
Coverage in place: work group life {group} (usually ends when leaving the job), policies they own {policies}, savings counted {savings}; total {existing}.
Profile: {profile JSON}
Calculation: {lines, total, gap, suggested, termYears}
{example mode: "These are example numbers for a sample person named Maya…" | "The person's first name is {name}."}
```

- If the AI is unavailable, fall back to the canned answers in prototype `FALLBACK` (keyword-matched) with the note "Standard answer. Live answers aren't available in this view." Errors: on rate limiting, show "That's a lot of questions at once. Try again in a minute."; otherwise "I couldn't finish that answer. Try asking again." Never retry automatically.

## Design

Use `design-tokens.json`. Key values:

- Ground and cards: white (`#ffffff`). Quiet wells and assistant bubbles: `#f2f5f9`. Hairlines: `#dfe4ec`. Ink: `#1b2433`. Muted text: `#5a6475`.
- Top bar: navy `#142640` with a 4px orange `#c2541a` bottom rule. Wordmark in white. Tagline in `#f6a36b`.
- Headings and the headline figure: dark blue `#1f3a5f`. User chat bubbles: `#e8eef6`.
- Orange `#c2541a`: primary buttons (white text), the selected tab, the "left to cover" bar, the top edge of tradeoff cards. Orange text `#b04e1a`: eyebrows and "Why?" links. Orange tint `#fdf0e6`: assumptions note, example banner, selected chips.
- Teal `#1f6f6a` / tint `#e3f1ef`: "already covered" and reassurance. Teal is also the focus ring.
- Chart series, in fixed order: income `#e07b34`, debts `#2f5597`, college `#a83a5e`, final expenses `#13958b`. This set was checked for color-blind separation. The income color is under 3:1 on white, so always keep the direct labels and the table.
- Type: Newsreader (display serif) for headings and big figures. Public Sans for everything else. Money uses tabular numerals.
- Radius: 6px inputs, 12px cards and bubbles, pill chips and buttons. Tabs are bordered 6px-radius buttons, placed right in the top bar.
- Copy tone: calm, short sentences, "starting point" not "you need", no alarm words. Every number appears next to its reasoning.

## Accessibility and responsiveness

- Works at 400px wide with no horizontal scroll. Two-column layouts stack below about 900px.
- Visible focus states. `aria-live="polite"` on chat logs. Tabs use proper tab semantics (or nav links if the repo routes them). Charts have an `aria-label` summary, plus the table as the text alternative.
- Respect `prefers-reduced-motion`.

## Tests to add

- `compute()`: the three test vectors above, plus rounding edges.
- `parseLocal()`: a table of phrases → values (for example "about 85k" → 85000, "2x salary" with income 90,000 → 180,000, "me and my wife plus our kids" → ["partner","kids"], "until my youngest is 22" with youngest 4 → 18, "not part of the plan" → "none").
- `clean()`: rejects bad enums, negatives and unknown keys.
- One flow test: sign up → answer every onboarding question with the local parser only → confirm → dashboard tiles match `compute()` → edit income in My info → tiles update and a log entry appears.

## Open questions to raise with me during Step 0

1. Is there an existing backend and auth system to wire into, or should this stay client-only for the demo?
2. Which LLM provider and endpoint should extraction and chat use?
3. Should the onboarding replace any existing intake screen in the repo, or live alongside it?
