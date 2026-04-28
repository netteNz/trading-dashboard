---
name: doc-handoff
description: >
  Generate or refresh a compact AI handoff document (HANDOFF.md) for any project.
  The document is the single source of truth an AI agent reads at conversation start
  to orient itself with zero redundant exploration. Use whenever starting a new
  conversation on an existing project, onboarding a new agent, or after a significant
  code change that makes the previous handoff stale.
  Triggers on: "generate handoff", "refresh handoff", "update handoff",
  "create handoff", "minimize tokens", "source of truth", "agent context".
argument-hint: 'Path to the project root. If omitted, use the current workspace root.'
user-invocable: true
---

# Doc Handoff Skill

Generate a dense, token-efficient `HANDOFF.md` that lets an AI agent orient itself
in one file read instead of exploring dozens of files. The document is optimized for
**minimum tokens, maximum signal** — it is not human documentation.

---

## Objectives

1. **Single read-in** — one file gives the agent everything needed to work on the project.
2. **Token budget discipline** — every line earns its place. No prose padding.
3. **Freshness** — the file is regenerated (not edited) after meaningful structural changes.
4. **Contract-first** — APIs, data shapes, and file boundaries are documented explicitly.
5. **Gotcha capture** — non-obvious constraints, env quirks, and known issues go in here.

---

## Phase 0 — Pre-flight

Before generating, collect the following. Use tools (list_dir, view_file, grep_search)
to discover — do NOT ask the user unless a critical value is truly unknowable.

```
□ Project root path
□ Tech stack (languages, frameworks, runtimes)
□ Entry points (how to start each process)
□ Key environment variables (names + purpose, never values)
□ File tree depth-2 (collapse node_modules, venv, __pycache__, .git, dist, build)
□ API surface (routes, methods, params, response shape)
□ Data flow (request → processing → response, named with actual function/file references)
□ Key abstractions (classes, hooks, modules that recur everywhere)
□ Non-obvious constraints (version pins, OS quirks, ordering requirements)
□ Known issues / gotchas discovered during setup or past work
□ What is explicitly OUT OF SCOPE (don't implement, don't touch)
```

---

## Phase 1 — Gather

Run these discovery steps in order. Record raw findings — do not write the handoff yet.

### 1.1 Project tree

Produce a depth-2 tree, skipping noise dirs. Format as a flat indented list. Example:

```
backend/
  app.py
  requirements.txt
  .env.example
  indicators/
  data/
  ws/
frontend/
  src/
  index.html
  vite.config.js
  package.json
docker-compose.yml
README.md
```

### 1.2 Stack fingerprint

Read `package.json`, `requirements.txt`, `pyproject.toml`, `Cargo.toml`, `go.mod`,
or equivalent. Extract: runtime version, key deps (pinned versions matter), build tool.

### 1.3 Entry points

Find how each process starts. Check: `package.json scripts`, `Makefile`, `Dockerfile`,
`docker-compose.yml`, `app.py`/`main.py`/`index.ts`/`main.go`, `README` ENTRYPOINTS
section.

### 1.4 Environment

Read `.env.example` or equivalent. For each variable: name, required/optional, purpose.
Never record actual values.

### 1.5 API surface

For backend: grep for route decorators (`@app.route`, `router.get`, `app.get`, etc.).
Extract method + path + key params + response shape. One line per route if possible.

For frontend: grep for fetch/axios/useQuery calls or API client files to confirm
what the frontend actually calls.

### 1.6 Data flow

Trace one complete request end-to-end using actual function and file names.
Keep it under 15 lines. Name each hop.

### 1.7 Key abstractions

Identify 3–8 core modules/classes/hooks that an agent must know exist before
writing any code. For each: name, file path, one-sentence purpose.

### 1.8 Constraints and gotchas

Capture anything non-obvious:
- Version incompatibilities (e.g., "numpy >=2.0 required — 1.x breaks on Python 3.13")
- Ordering requirements ("backend must be up before frontend fetches")
- OS-specific behaviour ("posix module missing on Windows — use X instead")
- Known broken things ("feature Y is stubbed, not implemented")
- Things that look wrong but are intentional

---

## Phase 2 — Write HANDOFF.md

Write the file to `{project_root}/HANDOFF.md`.

Use the exact template below. Sections marked `<!-- required -->` must always be present.
Sections marked `<!-- if applicable -->` are omitted when not relevant.

Keep the entire file under **150 lines**. If it grows past 150 lines, compress prose,
merge rows, or move deep detail into inline code comments instead.

---

## HANDOFF.md Template

````markdown
# {Project Name} — Agent Handoff
> Generated: {ISO-8601 datetime}  ·  Stack: {one-line stack summary}

<!-- required -->
## Quick Start
```bash
# {Process 1 name}
{start command}

# {Process 2 name — if applicable}
{start command}
```
URLs: {service} → {url}  ·  {service} → {url}

<!-- required -->
## File Map
```
{depth-2 tree, noise dirs collapsed}
```

<!-- required -->
## Stack
| Layer | Tech | Version | Notes |
|-------|------|---------|-------|
| {layer} | {tech} | {version} | {one-line note} |

<!-- required -->
## Environment — `{env file path}`
| Var | Required | Purpose |
|-----|----------|---------|
| `VAR_NAME` | yes/no | {one-line purpose} |

<!-- required -->
## API Surface
| Method | Route | Key Params | Returns |
|--------|-------|-----------|---------|
| {METHOD} | `{/path}` | `{param}` | `{shape}` |

<!-- required -->
## Data Flow
```
{Step 1: file.fn()}  →  {Step 2: file.fn()}  →  ...  →  {Response}
```
{One paragraph if the arrows aren't self-explanatory — otherwise omit.}

<!-- required -->
## Key Abstractions
| Name | File | Purpose |
|------|------|---------|
| `{Name}` | `{path}` | {one sentence} |

<!-- if applicable -->
## Extend — {Extension Point Name}
{Numbered list of touch points. Mirror the README pattern if one exists.}
1. Create `{file path pattern}`
2. Register in `{file}` — {what to add}
3. Wire in `{file}` — {what to add}

<!-- if applicable -->
## Constraints & Gotchas
- **{Topic}**: {one-line constraint or workaround}
- **{Topic}**: {one-line constraint or workaround}

<!-- if applicable -->
## Known Issues
- `{component/file}`: {symptom} — {status: open/workaround/wontfix}

<!-- if applicable -->
## Out of Scope
- {Thing that looks like it should exist but doesn't / shouldn't be touched}
````

---

## Phase 3 — Validate

Before saving, check:

```
□ File is under 150 lines
□ No section contains prose longer than 3 sentences
□ All file paths are actual paths that exist in the repo
□ All route paths were verified against source (not copied from README alone)
□ All version numbers were read from lock/requirements files, not guessed
□ No actual secret values are present (only variable names)
□ Quick Start commands are copy-paste runnable on the target OS
□ Constraints section captures everything non-obvious discovered during Phase 1
```

If any check fails, fix the handoff before writing it.

---

## Phase 4 — Report to User

After writing the file, respond with:

1. **Path** to the written file (as a clickable link)
2. **Line count** and token estimate (`line_count × 8 ≈ tokens`)
3. **Top 3 gotchas** captured — so the user can verify they're correct
4. **What's missing** — any section you could not populate because the data wasn't
   discoverable (ask the user only for these)

Do NOT reproduce the full HANDOFF.md in the chat response. The file is the output.

---

## Refresh Protocol

When the user asks to **refresh** an existing handoff:

1. Read the current `HANDOFF.md`
2. Run only the Phase 1 steps that are likely stale (new deps? new routes? new files?)
3. Overwrite the file — do not append or create a diff
4. Report what changed (added/removed/updated rows)

A handoff should be refreshed after:
- Adding or removing routes
- Changing the stack (new major dep, runtime upgrade)
- Completing a feature that adds new key abstractions
- Fixing a gotcha that was previously documented as an issue

---

## Token Discipline Rules

These rules are non-negotiable. Violating them defeats the purpose of the handoff.

| Rule | Rationale |
|------|-----------|
| No intro paragraphs | Agents don't need motivation — they need facts |
| Tables over prose | Scannable in fewer tokens |
| Paths over descriptions | "see `backend/indicators/engine.py`" > "the indicator engine module" |
| One-line per concept | If it needs two lines, it needs its own file |
| No "this project is..." preamble | The project name + stack line is enough |
| Collapse noise dirs | `node_modules/`, `venv/`, `__pycache__/`, `.git/` never appear in file maps |
| Omit empty sections | A missing section is clearer than `N/A` rows |
| Version numbers from lockfiles | Never guess — wrong versions cause wrong advice |
