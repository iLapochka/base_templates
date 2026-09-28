---
name: "spec-verify"
description: "Verify a FastAPI backend implementation against its behavioral spec. Accepts a spec path or source file paths. If source files have no spec, creates one first via /spec-driven-development."
argument-hint: "Path to spec file or source file(s)"
user-invocable: true
context: fork
agent: Explore
model: claude-haiku-4-5
allowed-tools: Read, Glob, Grep
---

## User Input

```text
$ARGUMENTS
```

## Step 1 — Resolve input mode

Check `$ARGUMENTS` for `-v` or `--verbose`. If present, strip the flag before further parsing — it
controls output in Step 5.

Examine the remaining `$ARGUMENTS` and classify:

**Mode A — Spec path:** `$ARGUMENTS` points to a `.md` file under `specs/`. Proceed directly to Step 2.

**Mode B — Source file(s):** `$ARGUMENTS` contains one or more source paths (`.py`, or a directory
under `src/`). For each file:

1. Search for an existing spec that lists the file in its `context` frontmatter. Read `specs/INDEX.md`
   first, then Grep `specs/` for the filename.
2. If a matching spec is found, use it. If multiple specs match, verify against all of them.
3. If **no spec exists**, stop and invoke `/spec-driven-development` to create one:
   > "No spec found for `<file>`. Running /spec-driven-development to create one first."

   Wait for the spec to be written and confirmed before continuing.

**Mode C — No arguments:** Infer from session context — which spec or source file was most recently
discussed. State your inference:

> "Inferred from session: verifying against `<spec-path>`. Let me know if that's wrong."

If nothing can be inferred, ask:

> "What should I verify? Provide a spec path or source file path."

Do not proceed without at least one resolved spec file.

## Step 2 — Read the spec

Read the spec file. Extract:

1. **Behaviors** — every `###` block under `## Behaviors`, both Given/When/Then blocks and plain
   assertions.
2. **Invariants** — every item under `## Invariants`, if present.
3. **Failure modes** — every item under `## Failure Modes`, if present.
4. **Edge cases** — every item under `## Edge Cases`.
5. **Context files** — the `context` list from the frontmatter.

If `context` is missing or empty, ask:

> "This spec has no `context` files listed. Which source files should I verify against?"

## Step 3 — Read the implementation

Read every file listed in `context`. If a path is a directory, read all `.py` source files in it
(skip tests, `__init__.py`, configs, and generated files).

You may additionally read a file **only** when a `context` file's behavior is unreadable without it
and it is directly imported by one — the port a use case calls, the entity a repository maps, the
base class in `src/shared/`, or the pydantic schema for a contract spec. Note in the report which
extra files you opened.

Do **not** read conversation history, `CLAUDE.md`, or unrelated project context. The isolation is
intentional — you evaluate only what the spec says should happen vs. what the code does.

## Step 4 — Verify each behavior

For every behavior, invariant, failure mode, and edge case, assign a verdict:

| Verdict     | Meaning                                                                                              |
| ----------- | ---------------------------------------------------------------------------------------------------- |
| **PASS**    | The implementation clearly satisfies this behavior, and all referenced fields/states/errors exist as described. |
| **FAIL**    | The implementation contradicts or does not implement this behavior; or a field, status code, or state named in the spec does not exist in the code. |
| **UNCLEAR** | Cannot determine from the code alone — depends on runtime state, the database, an external service, or code not in `context`. |

Rules:

- Judge **observable behavior**, not code style or structure.
- Before assigning PASS, verify that every field, status code, error body, and state the spec names
  actually exists in the code. If the spec says "a finished job is refused with 409", confirm there
  is a branch that returns that status — not just a comment or a TODO.
- A behavior is PASS only if:
  1. The code **demonstrably** handles it — not if it "probably works".
  2. **All fields, status codes, and states referenced in the spec exist** in the code as described.
  3. The mechanism the spec states (not a different one) is what drives the behavior.
- A behavior is FAIL if:
  1. No code path produces the expected outcome, or a path produces a contradictory one.
  2. A field, status code, route, or state named in the spec does not exist.
  3. The implementation uses a different mechanism than the spec describes — a value computed in a
     route when the spec places the rule in a use case, or a status recomputed on read when the spec
     says it is persisted on transition.
- For **invariants**, look for a path that can violate the property, not just for a happy path that
  upholds it. A status transition guarded in one use case but bypassed by a direct repository update
  is FAIL.
- For **idempotency claims**, confirm there is a key or a natural uniqueness constraint that makes a
  repeated call a no-op. "Repeat calls are unlikely" is FAIL.
- For a **long-running behavior**, confirm the failure path writes a terminal status. A run that can
  leave a job in `downloading` or `rendering` forever, or an ffmpeg process alive after a timeout, is
  FAIL, whatever the happy path does.
- Additionally flag, as FAIL, any layering violation you can see in the read files: `fastapi`,
  `sqlalchemy`, `pydantic`, `yt_dlp`, `subprocess` or `core` imported from `domain/`; any of them but
  pydantic from `application/`; a business rule implemented in a route or a repository; a download,
  a render or another slow call inside a session scope; a URL, caption or filename reaching a shell
  string or an unescaped filter graph; or `os.environ` read inside `src/`. Name it in the
  Failures section as a layering violation.
- Use UNCLEAR sparingly — only when the code is genuinely ambiguous or depends on something outside
  the provided files.

## Step 5 — Report

Output the results in this exact format:

```
## Spec: <spec name from frontmatter>
File: <spec path>

| # | Behavior | Verdict |
|---|----------|---------|
| 1 | <behavior name or edge case> | PASS/FAIL/UNCLEAR |
| 2 | ... | ... |

PASS: X/<total> | FAIL: Y/<total> | UNCLEAR: Z/<total>
```

If `-v` or `--verbose` was passed, add a `Reason` column with a one-line explanation for every row.

If there are any FAILs, add a section after the table:

```
### Failures

**<behavior name>**: <2-3 sentences: what the spec expects, what the code does instead, and where in
the source the mismatch is.>
```

If there are any UNCLEARs, add:

```
### Unclear

**<behavior name>**: <What additional context or files would be needed to make a determination.>
```

If you opened files beyond `context`, list them under a final `### Files read beyond context` line.

## Step 6 — Suggest next steps

- **All PASS**: Report clean and done.
- **Any FAIL**: List the failing behaviors and ask: "Want me to fix these, or update the spec to match
  the current implementation?"
- **Any UNCLEAR**: List what's missing and ask: "Should I read additional files to resolve these, or
  mark them as out of scope?"

---

## Guardrails

- **Never modify source files.** This skill is read-only. It verifies, it does not fix.
- **Never run `git commit` or `git push`.**
- **Never read files outside the spec, its `context` list, and the narrow exception in Step 3** unless
  the user explicitly provides additional paths.
- **Never invent behaviors.** Only verify what the spec explicitly states.
- **Never give a PASS verdict on assumption.** If you can't trace the behavior to a code path, it's
  UNCLEAR at best.
- **Never skip spec creation.** If source files are provided and no spec exists, always invoke
  `/spec-driven-development` first. Do not verify without a spec.
- **Always cross-check that named fields, status codes, and states exist.** A behavior cannot be PASS
  if the stated source of truth doesn't exist, even if similar behavior is implemented another way.
- **Keep reasons short.** One line per verdict in the table; details go in Failures/Unclear only.
