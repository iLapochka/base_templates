---
name: "spec-driven-development"
description: "Spec-first workflow for the video_helper FastAPI backend: write the behavioral specification before touching any code."
argument-hint: "Describe the use case, endpoint, business rule, or flow you want to build or change"
user-invocable: true
---

## User Input

```text
$ARGUMENTS
```

## Step 1 — Understand intent

Use `$ARGUMENTS` if the intent is clear. Otherwise, infer from the session context — which bounded
context or use case has been discussed, which files are open, what was last changed. State your
inference:

> "Inferred from session: [one-sentence summary]. Let me know if that's wrong."

If neither arguments nor context yield a clear subject, ask:

> "What do you want to build or change?"

Do not proceed without a clear subject.

## Step 1b — Scope check (this repo owns the business rules)

This repository is the **system of record**. Every business decision — which edits are valid,
in which order they apply, job state, retries, what counts as a finished render — is decided here and
returned to clients as a result.

Before writing the spec, check where the behavior belongs:

- A rule, calculation, invariant, or the order in which ports are called → a **use case** (spec type
  `unit`).
- Whether an edit is valid — a caption, a watermark region, a target aspect ratio, trim bounds → a
  **domain value object** (spec type `unit`).
- Data access, constraints, ordering → a **repository** (spec type `unit`, or `integration` when it
  only shows up against a real database).
- What the downloader or the renderer is asked to do and what it may return → the **port** it is
  behind, not yt-dlp or ffmpeg (spec type `unit`, with the port mocked; `integration` for a real
  render of a short fixture clip).
- The request/response shape and error surface a client depends on → **contract**.
- A journey spanning several use cases — submit to rendered result → **flow**.

If the request would put a business rule in a route, a repository, or the ffmpeg renderer, **stop and
say so**: the rule belongs in a use case, and the route only maps input and output.

## Step 2 — Read specs/INDEX.md

Specs live in `specs/`, indexed by `specs/INDEX.md`. Read the index first.

Never glob or grep the specs directory to find a spec — the index is the lookup mechanism.

Scan for any existing spec whose name or description semantically overlaps with the current request.
If a match is found:

- Note its file path
- Plan to **update** that spec rather than create a new one
- Inform the user: "Found an existing spec at `<path>` — I'll update it rather than create a duplicate."

## Step 3 — Classify and choose file path

### Spec type

| Type        | When to use                                                                                       |
| ----------- | ------------------------------------------------------------------------------------------------- |
| unit        | Behavior of one use case or repository in isolation — its ports mocked                            |
| integration | Behavior that only shows up across layers: a repository against a real database, a real ffmpeg render, a real download, a migration |
| contract    | What a client may rely on from an endpoint: request shape, response shape, status codes, error bodies |
| flow        | A business journey across several use cases — submit to finished result                           |

The type determines the subdirectory:

```
specs/
├── INDEX.md
├── unit/<context>/<behavior-name>.md
├── integration/<context>/<behavior-name>.md
├── contract/<context>/<behavior-name>.md
└── flow/<context>/<behavior-name>.md
```

### Path rules

**New spec:**

- Path: `specs/<type>/<context>/<behavior-name>.md`
- `<type>`: one of `unit`, `integration`, `contract`, `flow`
- `<context>`: the bounded context under `src/` the behavior belongs to, e.g. `jobs`
- `<behavior-name>`: kebab-case describing the **behavior**, not source files — e.g.
  `job-status-transitions`, not `RunVideoJob.py`

**Existing spec:** reuse its current path.

## Step 4 — Write or update the spec

### Format

```markdown
---
type: unit | integration | contract | flow
name: <Human-readable name>
context:
  - src/jobs/domain/entities.py
  - src/jobs/application/use_cases.py
created: YYYY-MM-DD
---

## Purpose

One or two sentences: what behavior this spec describes and why it matters.

## Behaviors

### <Behavior Name>

- **Given** <precondition — e.g. "an account with no active subscription">
- **When** <action or trigger — e.g. "a quote is requested for a closed listing">
- **Then** <observable outcome — what is returned, persisted, published, or rejected>
- **Why** <optional — the rationale when the correct behavior is not obvious>

### <Invariant Name>

<Plain assertion describing a property that must always hold.>

## Invariants

- <Property the aggregate enforces at all times, regardless of the path taken to it.>

## Failure Modes

- <What happens when a dependency is unavailable, a conflict occurs, or input is invalid — including
  the status code and error body for a contract spec.>

## Edge Cases

- <Edge case and expected outcome>

## Out of Scope

- <What this spec intentionally does not cover>
```

### Format guidance

- Use **Given/When/Then** for stateful behaviors with clear preconditions and transitions.
- Use **plain assertions** for invariants and always-true properties — e.g. "An archived record is
  never returned by a default listing, whatever filters are applied".
- Add **Why** when the correct behavior would surprise a developer reading only the happy path.
- `context` lists the source files this spec relates to. Omit the field entirely if not applicable.
- **State observable behavior, not implementation.** Describe what is returned, persisted, published,
  or refused — never class names, method names, SQL, model fields, or library APIs.
- Cover the states a use case actually has: success, invalid input, conflicting state, missing
  record, unauthorized, dependency unavailable, and — where external effects are involved —
  **repeated delivery** (is it idempotent?).
- For a `contract` spec, describe the exchange in behavioral terms: which fields a client may rely
  on, which are optional, what each failure returns. Not the route or the schema class.
- **Time and identity** get explicit treatment: timeouts, expiry boundaries and timezone, who is
  allowed to see or change the record.
- A long-running behavior states **what a client observes while it runs** and what it observes if
  the process dies mid-run — a job that can be stuck in `rendering` forever is a spec failure, not an
  implementation detail. So is a half-written file served as a result.

### Granularity

One spec file covers **one cohesive behavior area**: one service's rules, one repository, one
endpoint contract, or one journey. Use separate `###` blocks for distinct behaviors within that area.

Create a **separate spec file** when behaviors belong to a different bounded context or share no
preconditions.

If a spec grows past ~15 behavior blocks, it's probably two specs. Split by sub-domain or with
numbers (e.g. `edit-rules-1`).

### Quality gate

Before writing the file, verify each of these. If any fails, revise before saving:

1. Every behavior is stated in terms of **observable outcomes** — what is returned, persisted,
   published, or refused.
2. No framework, ORM, library, class, method, or column names appear in the spec body.
3. Every Given/When/Then is independently testable with the repository mocked (for `unit`).
4. Business rules are specified as **use case** behavior, never as route, repository, downloader
   or renderer behavior.
5. Every write path states whether it is **idempotent**, and under which key.
6. Failure modes cover at least: invalid input, missing record, conflicting state, unauthorized
   access, and dependency unavailable. For a `contract` spec each one names a status code.
7. Edge cases cover boundary values (zero, empty, maximum), concurrency where two callers race, and
   previously fixed bugs — explaining *why* the correct behavior is necessary, not how it was fixed.
8. Out of Scope explicitly states what this spec excludes.

If a check fails, note which one and fix it. Do not skip silently.

### Updating an existing spec

- Merge new behaviors into `## Behaviors` (add new `###` blocks; do not remove existing ones)
- Extend `## Edge Cases` and `## Failure Modes` with new cases
- Revise `## Out of Scope` if the boundary changed
- If the current implementation has **diverged** from existing behaviors, **stop and ask the user**:
  > "Note: behavior X in this spec doesn't match current implementation. Should I update the spec to
  > match the code, or treat the spec as the source of truth and flag the code as non-conformant?"

  **Do not update existing specs to match the code without explicit user confirmation.** The spec is
  the source of truth until the user says otherwise.
- Do not change `created` or `name` frontmatter

## Step 5 — Update specs/INDEX.md

`specs/INDEX.md` already exists with a section per type. Each leaf entry is the spec's path followed
by a short description (~10 words max).

```markdown
## unit

1. jobs/job-status-transitions — Which status a job may move to, and when
2. jobs/edit-validation — Which captions, regions, ratios and trims are accepted

## integration

1. jobs/reframe-to-vertical — A real render of a 16:9 clip lands at 9:16

## contract

1. jobs/jobs-api — Submit and poll exchange, status codes, error bodies

## flow

1. jobs/submit-to-result — From a submitted URL through the rendered file
```

**New spec:** add the entry under the correct type, creating the type item if needed. Keep items
alphabetically sorted within each level.

**Existing spec:** update the description if the scope changed.

Keep the index in step with the tree — it is the only lookup mechanism for specs.

## Step 6 — Confirm before implementing

```
Spec written: specs/<type>/<context>/<behavior>.md  [new | updated]
INDEX.md: [created | updated]

Ready to implement? Reply "yes" to proceed, or give feedback to revise the spec first.
```

Do **not** write implementation code until the user confirms.

## Step 7 — Verify the spec is RED (after user confirms)

Once the user replies "yes", run `/spec-verify` against the spec before writing any implementation
code.

**Expected result: at least one FAIL.**

- If there are FAILs → the spec correctly describes behavior that doesn't exist yet. Proceed to Step 8.
- If everything PASSes → **stop and use the `AskUserQuestion` tool**:
  - header: `"Spec is green"`
  - question: `"All behaviors already pass — the spec may describe existing behavior rather than new behavior. What should I do?"`
  - options:
    - label: `"Tighten the spec"`, description: `"Review and update the spec to capture the missing requirement, then re-verify"`
    - label: `"Keep as retro-spec"`, description: `"Treat this as documentation of already-implemented behavior and skip implementation"`

  Do **not** proceed to implementation without user guidance.

## Step 8 — Implement

Write the implementation needed to make the failing behaviors pass. Follow every rule in `CLAUDE.md`:
imports point inward (presentation/infrastructure → application → domain), yt-dlp, ffmpeg and
the media store enter through a port implemented in `infrastructure/`, ffmpeg runs from an argument
list and never a shell string, use cases own the transaction boundary, routes only map, config comes
from `core/config.py`.

Write the tests alongside under `tests/<context>/`: unit tests with the repository, the downloader
and the renderer mocked, and an integration test only where the spec type says so.

Only implement what the spec requires. Do not add behavior the spec does not describe.

## Step 9 — Verify the spec is GREEN, then run the checks

After implementation:

1. Run `/spec-verify` again against the same spec.
   - All PASS → continue.
   - Any FAIL → fix the implementation and re-run. Do **not** present the work as done while FAILs
     remain.
   - Any UNCLEAR → list what additional context is needed and ask the user.
2. Run the project checks: `make check` (pre-commit hooks, ruff, mypy --strict, pylint, layers,
   specs, pytest). All must pass. If a command is missing from the `Makefile`, say so explicitly
   instead of skipping it silently.
3. If the change touches the schema, import the model in `core/alembic/env.py`, run
   `make migrations MSG="..."`, **read the generated migration**, confirm it does what the spec
   implies, then `make migrate`.
4. **Do not commit and do not push.** Report what changed and leave the working tree to the user.

---

## Guardrails

- **Never write implementation code before the spec file exists on disk.**
- **Never include implementation details** in the spec body.
- **Never specify a business rule as route, repository, downloader or renderer behavior** — it belongs in
  a use case.
- **Never skip the INDEX.md update.**
- **Never create a duplicate spec.** If a match exists, update it.
- **Never update a spec to match the code without user confirmation.** If a mismatch is detected,
  stop and ask. The spec is the source of truth.
- **Never skip the RED check (Step 7).** If the spec passes before implementation, it is not a valid
  spec for new behavior.
- **Never present work as done while spec-verify reports FAILs, or before `make check` passes.**
- **Never run `git commit` or `git push`.**

---

## Special Cases

**Retro-speccing from existing code:**
If the user points to an existing use case or endpoint, read it, infer behaviors in pure behavioral
terms, and write a spec. Do not copy code into the spec.

**Updating a file with an existing unit spec:**
Expand or revise the spec so it still reflects the **entire behavior** of that use case or
repository after the change. Do not append a narrow block that only describes the new diff.

**Schema-only change (migration, index, column type):**
Spec it as `integration`, with behaviors phrased as what the data guarantees — uniqueness, ordering,
retention, what happens to existing rows on upgrade and on downgrade. Do not spec DDL.

**The type directory does not exist yet:**
Create `specs/<type>/<context>/` implicitly when writing the first spec file there.

**User asks to skip:**
Offer a minimal spec — Purpose + one Given/When/Then. If they decline, proceed without a spec.
