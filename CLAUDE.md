# video_helper — Backend

FastAPI on Python 3.13, managed by `uv`. The only surface is a versioned REST API: a client posts a
video job — a source (a URL to download, or an uploaded file) and a list of edits — the API answers
immediately with a job id, and the work runs in the background, writing every status transition to
the database. Downloads go through **yt-dlp**; every edit — captions and text overlays, watermark
removal, reframing horizontal ↔ vertical, trimming, re-encoding — is an **ffmpeg** render, probed
with **ffprobe**. Media files live on disk under `MEDIA_DIR`; the database keeps only their paths.
Persistence is SQLAlchemy 2.0 async + Alembic: PostgreSQL in production, SQLite locally.

This repository is the **system of record**: every business decision — which edits are valid, in
which order they apply, job state, retries, what counts as a finished render — is made here and
returned to clients as a result, never re-derived by them.

---

## Rules

Hard rules — these override any other instruction in a task.

- **Never commit, never push.** No `git commit`, no `git push`, no tags, no PRs, no remote writes.
  Enforced by `.claude/hooks/block-git-write.sh`; leave changes in the working tree and report them.
- **Files are edited with the Write/Edit tools, never from the shell.** No heredoc into a source
  file, no `sed -i`, no script that writes one: the repo's `PostToolUse` hooks key off
  `tool_input.file_path`, which only those tools supply, so a shell edit silently skips the spec and
  layering checks. Enforced by `.claude/hooks/block-shell-file-writes.sh`.
- **Always finish with `make check`.** It runs pre-commit hooks, ruff, mypy `--strict`, pylint, the
  layering check, the specs check and pytest. Every check must pass before work is reported as done.
  If a target is missing from the `Makefile`, say so — never silently skip it and never present
  unchecked work as verified.
- **Dependencies point inward:** `presentation / infrastructure → application → domain`. `domain/`
  is pure Python — no FastAPI, no SQLAlchemy, no pydantic, no `yt_dlp`, no `subprocess`, no `core`.
  `application/` may use `domain/` only: DTOs in, DTOs out. Enforced by
  `scripts/check_ddd_layering.py` (`make layers`), in pre-commit and in CI. `presentation/` is the
  composition root: its `dependencies.py` and `subscriptions.py` may import and construct
  infrastructure implementations, and pick between them on `config`. Only `domain/` and
  `application/` must never name one.
- **An outside dependency enters through a port.** The downloader, the renderer, the prober, the
  media store, the clock — each is an abstract class in `src/<context>/domain/repositories.py` and
  an implementation in `src/<context>/infrastructure/`. `yt_dlp` and the ffmpeg/ffprobe processes are
  touched in exactly one layer: infrastructure. A use case that builds an ffmpeg command is not
  mergeable.
- **An edit is a domain value, ffmpeg is its translation.** Captions, watermark regions, target
  aspect ratio, trim bounds are frozen value objects in `domain/`, validated there (a region inside
  the frame, a start before the end, a known aspect ratio). Infrastructure turns a validated list of
  edits into one filter graph; it never decides whether an edit is allowed.
- **Never a shell string.** ffmpeg, ffprobe and yt-dlp run with an argument list
  (`asyncio.create_subprocess_exec`), never `shell=True`, `create_subprocess_shell` or `os.system`.
  Caption text reaches ffmpeg through `drawtext=textfile=` or proper filter escaping — never
  interpolated raw into a filter graph, where `:` `'` `\` `,` `;` rewrite the command. A URL is passed
  to yt-dlp as a value, never concatenated into options.
- **A source is fetched only from where it is allowed to be.** Only `http`/`https` URLs are
  accepted; `file://`, local paths and private network addresses are refused in the schema or the
  use case — yt-dlp's generic extractor will otherwise read the server's own disk. A download stops
  at `VIDEO_MAX_DOWNLOAD_MEGABYTES`.
- **The server names every file.** A path under `MEDIA_DIR` is built from the job id, never from a
  client-supplied filename or title (`../` escapes the directory). A render writes to a temporary
  path and is renamed into place when complete, so a half-written file is never served as a
  result. A failed job removes its partial files.
- **Every endpoint is authenticated.** A route carries the API-key dependency from
  `src/shared/presentation/`, or it is not mergeable — FastAPI's default is open, so silence means
  the whole internet can render on your machine. `/health` is the one exception, and it returns
  nothing but liveness. Serving a result file is an endpoint too.
- **Validation lives in a pydantic schema, never in a route.** A route reads a validated schema; it
  never parses the body, never checks a field by hand, never builds an error body. A domain refusal
  becomes a status code through the class it raises (`src/shared/exceptions.py`), never in the route.
- **A route never wires a use case.** Each context has `presentation/dependencies.py` that builds
  its use cases with `Depends()`, reusing `SessionDep` / `UnitOfWorkDep` from
  `src/shared/presentation/`. A use case constructed inside a route body is not mergeable.
- **Routers are declarative, use cases hold the rules.** A route maps request → DTO, awaits one use
  case, maps the result → response schema. Nothing else: no `if` on business state, no session, no
  query.
- **A download or a render never runs inside a transaction, and never inside the request.** Both
  take minutes: write the job row, commit, return `202`, then execute. Wrap only the database writes
  in a transaction — a transaction spanning a render holds a connection for its whole length and
  hides every status written inside it until commit, so a rollback erases the very row that recorded
  the failure. Each status transition is its own short transaction.
- **A background run reports its own failure.** The runner catches the exceptions a run can end
  with — a download refused, ffmpeg exiting non-zero, the timeout — writes the terminal status and
  the error to the job row (for ffmpeg, the tail of its stderr), and never lets an exception escape
  into the background-task machinery, where nobody sees it. A timed-out ffmpeg is killed, not left
  running. A bare `except Exception` that writes `failed` without the error text hides bugs.
- **Config is read in `core/config.py`.** Everything else imports `config` from there. Never call
  `os.environ` / `os.getenv` inside `src/`.
- **Time is timezone-aware.** `datetime.now(UTC)`, never `datetime.now()` or `utcnow()`; ruff's
  `DTZ` rules enforce it. Video timestamps are durations (`timedelta` or seconds as `float`), never
  datetimes.
- **A layer earns its place.** A context with one rule does not need four packages of indirection: a
  use case that forwards one call to a repository is indirection, not architecture. Add the layer
  with the first rule that needs it, and add every layer below it at the same time. A package with
  no entity of its own is not a bounded context.
- **Migrations are read before they are trusted.** Import the model in `core/alembic/env.py`, generate
  with `make migrations MSG="..."`, open the file, confirm it does what you intended.
- **Names are written out in full, and say what the thing is or does.** This holds for every name —
  variable, attribute, function, method, class, module. A value names what it holds:
  `video_renderer = FfmpegVideoRenderer()`, not `renderer = FfmpegVideoRenderer()`;
  `job_repository`, not `repo`; `job_id`, not `jid`. A function names what it does, in the words the
  domain already uses: `submit_video_job`, `download_source_video`, `render_edits`,
  `mark_job_failed` — never `run`, `do_work`, `process`, `handle_it`, `helper`, `manager`, `data`,
  or a name that says only that something happens. An abbreviation saves the writer a word and costs
  every later reader a lookup. If the honest name is vague, the thing is doing more than one job —
  split it rather than name it vaguely.
- **Arguments are keyword-only, on both sides.** Declare them so — `def __init__(self, *,
  job_repository: VideoJobRepository)` — and pass them so — `await use_case.execute(job_id=job_id)`.
  The `*` puts the rule in the interpreter instead of in review. A function that collects its
  arguments takes `**kwargs` — never `*args`, which arrive nameless. Exceptions, and no others:
  what a framework calls positionally keeps the signature the framework calls (a FastAPI path
  operation, an exception handler `(request, exc)`, a pytest fixture); a library call whose one
  argument is obvious (`Path(name)`, `UUID(value)`) stays as the library wrote it; and a
  decorator's passthrough wrapper forwards `*args, **kwargs`, because it cannot know the signature
  it wraps.
- **Every entry point is logged with `@log_call`** from `src/shared/call_logging.py`: each public
  method of a use case in `application/`, and each route and event handler in `presentation/`.
  It logs `Class.method(name=value, ...)` before the call runs. Put it directly on the function,
  under `@router.<verb>(...)`, so the route FastAPI registers is the logged one. Not in `domain/`:
  entities and ports have nothing that runs. Not on private methods, dependency builders or
  exception handlers. A value that carries a credential (site cookies, a token) hides it from
  `repr` (`field(repr=False)` on a dataclass, `Field(repr=False)` on a schema), so it never reaches
  a log line.
- **Comments and docstrings are one line.** No paragraph-long docstrings, no five-line comment
  blocks justifying a decision — that reasoning belongs in the spec, not in the source. Never
  restate in a docstring what the signature already says.
- **Write the spec first** — see [Specs](#specs).

---

## Architecture

```
presentation  →  application  →  domain  ←  infrastructure
```

- **Domain** — entities (plain dataclasses), value objects (`StrEnum` or frozen dataclasses: an
  edit, a frame region, an aspect ratio), abstract repositories and ports, domain exceptions. Pure
  Python.
- **Application** — use cases, one file each, taking DTOs and returning DTOs. Owns the transaction
  boundary and the order in which ports are called.
- **Infrastructure** — SQLAlchemy models and repository implementations, the yt-dlp downloader, the
  ffmpeg renderer and ffprobe prober, the on-disk media store. The only layer that knows a library
  or a binary exists.
- **Presentation** — this context's HTTP surface: routers, pydantic schemas, `Depends()` wiring and
  the status codes of its own refusals.

### Layout

```
src/
├── main.py                       # Composition root: app, api_router (/api/v1), handlers, /health
│
├── shared/
│   ├── domain/                   # BaseEntity, DomainEvent, EventBus and UnitOfWork ports
│   ├── infrastructure/           # SQLAlchemy Base, BaseModel, SQLAlchemyRepository,
│   │                             #   InProcessEventBus, SQLAlchemyUnitOfWork
│   ├── presentation/             # SessionDep, UnitOfWorkDep, EventBusDep, api-key dependency,
│   │                             #   exception handlers, request-id middleware, StrictSchema,
│   │                             #   admin.py: /admin sign-in and mount (views live in <context>/presentation/admin.py)
│   ├── call_logging.py           # @log_call — pure stdlib, importable from every layer
│   └── exceptions.py             # BaseDomainException, UnauthorizedError, ServiceUnavailableError
│
└── <context>/                    # Not created yet. The expected first one, `jobs`:
    ├── domain/
    │   ├── entities.py           # VideoJob
    │   ├── value_objects.py      # JobStatus: pending | downloading | rendering | succeeded | failed
    │   │                         #   Edit variants: AddCaption, RemoveWatermark, Reframe, Trim;
    │   │                         #   FrameRegion, AspectRatio (16:9 | 9:16 | 1:1 | 4:5)
    │   ├── repositories.py       # VideoJobRepository, VideoDownloader, VideoRenderer, MediaStore
    │   └── exceptions.py
    ├── application/
    │   ├── use_cases.py          # SubmitVideoJob, RunVideoJob, GetVideoJob
    │   └── dto.py
    ├── infrastructure/
    │   ├── models.py             # VideoJobModel
    │   ├── repositories.py       # SQLAlchemy implementation
    │   ├── yt_dlp_downloader.py  # The only file that imports yt_dlp
    │   ├── ffmpeg_renderer.py    # The only file that starts ffmpeg/ffprobe: edits → filter graph
    │   └── media_store.py        # Paths under MEDIA_DIR, temp-then-rename, cleanup
    └── presentation/
        ├── admin.py              # VideoJobAdmin — the sqladmin view, registered in src/main.py
        ├── dependencies.py
        ├── subscriptions.py
        ├── routers.py
        └── schemas.py

# One module per layer concern, not a package per file: the version lives in the URL
# (`api_router` carries `/api/v1`), never in the tree. Split a module into a package
# only when it actually grows too large to read.

core/                             # Wiring — outside the hexagon, excluded from ruff, mypy and pylint
├── config.py                     # pydantic-settings (reads .env) — the only place env is read
├── database.py                   # async engine + get_session dependency
└── alembic/                      # env.py imports every ORM model, or the table is invisible

alembic.ini                       # script_location = core/alembic
code_quality/                     # ruff, mypy, pylint configs — passed explicitly, not discovered
scripts/                          # check_ddd_layering.py, check_specs.py — run by make check and CI
specs/                            # Behavioral specs, indexed by specs/INDEX.md
tests/                            # Mirrors src/
media/                            # MEDIA_DIR locally — git-ignored, never committed
```

`core/` is wiring and sits outside the hexagon — excluded from ruff, mypy and pylint.

### The request path

```
POST /api/v1/jobs              → validate schema → SubmitVideoJob → row written (pending) → 202 {id}
                                                                  → background: RunVideoJob
                                   downloading → rendering → succeeded | failed
GET  /api/v1/jobs/{id}         → GetVideoJob → 200 {status, edits, error, result_url}
GET  /api/v1/jobs/{id}/result  → the rendered file, only once the job has succeeded
```

The background run resolves its own session — it must not reuse the request's, which is closed by
the time it starts. Renders are capped at `VIDEO_MAX_CONCURRENT_JOBS` at once: ffmpeg takes every
core it sees.

---

## Adding a bounded context

1. Create `src/<context>/` with the structure above — only the layers the behavior actually needs.
2. Write the spec first (`/spec-driven-development`).
3. Entity and value objects in `domain/`, the abstract repository or port beside them.
4. SQLAlchemy model in `infrastructure/models.py`, then **import it in `core/alembic/env.py`** —
   otherwise Alembic will not see the table.
5. `make migrations MSG="create <context> tables"`, **read the generated migration**, then
   `make migrate`.
6. Repository implementation in `infrastructure/repositories.py`.
7. Use cases in `application/use_cases.py`, one class each.
8. `schemas.py`, `routers.py` and `dependencies.py` in `presentation/`, then mount the context
   router on `api_router` in `src/main.py` — before `app.include_router(api_router)`.
9. If an operator should see the records, a `ModelView` in `presentation/admin.py`, added to
   `model_views` in `src/main.py`. A column holding a credential is left out of every view.
10. Tests under `tests/<context>/`.
11. `/spec-verify`, then `make check`.

A new library for a context (`uv add yt-dlp`, …) is added with the first code that imports it, and
its module goes into `OUTSIDE_PACKAGES` in `scripts/check_ddd_layering.py` if it is not there yet.

---

## Specs

Behavior is specified before it is implemented.

1. Run `/spec-driven-development` to create or update the spec.
2. Do not write implementation code until a spec exists on disk and the user confirms.
3. After implementation, run `/spec-verify` and fix any FAILs before presenting the work as done.

Specs live in `specs/<type>/<context>/<behavior-name>.md` and are indexed by `specs/INDEX.md`.
Always read the index first — it is the lookup mechanism. Never glob or grep the specs directory to
find a spec. `make specs` fails when a spec is missing from the index, has no frontmatter, or points
at a file that no longer exists.

Spec types: `unit` (one use case or repository in isolation, ports mocked), `integration` (across
layers: a real database, a real ffmpeg render on a short fixture clip, a real download), `contract`
(what a client may rely on from an endpoint), `flow` (a journey across use cases — submit to
rendered result).

When a PostToolUse hook reports spec coverage for a file you changed, tell the user after completing
the current task.

---

## Testing

`pytest` with `pytest-asyncio` in auto mode, `httpx` for the API. Use-case rules and repository
behavior are tested; the database, the downloader, the renderer and the media store are mocked at
the port.

### Do write

1. **Use-case rules** — success, invalid input, conflicting state, missing record, unauthorized,
   the download or the render failing. This is where the repo's logic lives.
2. **Edit validation** — a watermark region outside the frame, a trim that ends before it starts,
   an empty caption, an unknown aspect ratio, reframing a video already in the target ratio.
3. **Status transitions** — every legal move and every refused one; a finished job never goes back
   to rendering.
4. **Contract tests** for each endpoint — status codes, response shape, the error body, and that an
   unauthenticated request gets `401`.
5. **The filter graph** — for the ffmpeg renderer, the argument list built from a list of edits
   (pure function, no process started), including a caption with `:` `'` `\` in it.
6. **Idempotency** — a repeated submit with the same client key is a no-op, proven by a test.

### Do not write

| Don't | Why |
| --- | --- |
| Tests asserting ORM structure — column types, `relationship` kwargs | Restates the model; the migration is what matters |
| Tests that mock SQLAlchemy to assert which SQL was emitted | Couples the test to the query plan, not the behavior |
| Tests that start a real ffmpeg or hit the network in the unit suite | Slow and flaky; mock the port, mark a real render `integration` |
| Tests that commit video files larger than a few seconds | Generate a fixture clip with `ffmpeg -f lavfi -i testsrc` in the test instead |
| Tests for layering, type hints, formatting, unused imports | Already enforced by ruff, mypy `--strict`, pylint and `make layers` |
| An end-to-end test through a route for a rule that lives in a use case | Test the rule where it lives; the route only maps |

### Conventions

- Mirror `src/` under `tests/`; one behavior per test, named after the observable outcome
  ("rejects a job submitted without an api key"), not after the method.
- Mock at the port — the repository, the downloader, the renderer — never a session chain, never the
  network, never `subprocess`.
- A test derived from a spec quotes the behavior name from that spec.

---

## Skills

| Skill | Use for |
| --- | --- |
| `/spec-driven-development` | Spec-first workflow: write the behavioral spec before touching code |
| `/spec-verify` | Check an implementation against its spec (read-only, reports PASS/FAIL) |

Code review uses the built-in commands — `/code-review` for the working diff, `/security-review` for
vulnerabilities. When reviewing this repo, weight findings as follows:

- **Blocker:** a layering violation — `yt_dlp`, `subprocess`, `sqlalchemy`, `fastapi`, `pydantic`
  or `core` imported from `domain/`; any of them but pydantic from `application/`; or `os.environ`
  read inside `src/`. Presentation constructing an infrastructure class is wiring, not a violation —
  do not report it. Nor is a library used inside an infrastructure class that implements a domain
  port: the port is what application sees, the library is its detail.
- **Blocker:** a new endpoint without the api-key dependency, or a route that parses the request
  body by hand, holds a business rule, or constructs a use case instead of taking it from
  `dependencies.py`.
- **Blocker:** a `/spec-verify` FAIL on a changed file covered by a spec; or a behavior change whose
  spec under `specs/` was not updated.
- **Blocker:** a URL, caption or filename reaching a shell string, `eval`, or a filter graph without
  escaping; a source URL that is not `http`/`https` or points at a private address; a path under
  `MEDIA_DIR` built from client input.
- **Major:** a download, a render or any other slow work inside a session scope, or a background run
  that reuses the request's session.
- **Major:** a background run whose failure path does not write a terminal status or leaves the
  ffmpeg process running — a job stuck in `rendering` forever is invisible to every client.
- **Major:** a render that writes the result path directly instead of temp-then-rename, or a failed
  job that leaves its partial files behind.
- **Major:** a submit path that is not idempotent where a client may retry.
- **Major:** an N+1 query — a loop over results touching a relationship without `selectinload` /
  `joinedload`.
- **Major:** a migration that drops a table or a column, or a data migration without a reverse.
- **Major:** a naive datetime.

Mechanical rules (formatting, import order, type hints, unused code) are enforced by ruff, mypy and
pylint — do not re-report them by hand.

---

## Make targets

```bash
make run                       # uvicorn src.main:app --reload
make ffmpeg                    # brew install ffmpeg (ffmpeg + ffprobe are system binaries)
make migrate                   # alembic upgrade head
make migrations MSG="..."      # alembic revision --autogenerate
make migrate-down              # alembic downgrade -1
make from-scratch              # drop local.db and every migration, regenerate one from the models
make ruff                      # lint and auto-fix, then format
make format-check              # `ruff format --check`, exactly what CI runs
make ty                        # mypy --strict (src/)
make lint                      # pylint (src/)
make layers                    # DDD dependency direction
make specs                     # specs are indexed and their context files exist
make tests                     # pytest
make hooks                     # pre-commit run --all-files
make check                     # hooks + ruff + ty + lint + layers + specs + tests
make docker / docker-down / docker-logs       # full stack: API + PostgreSQL (image ships ffmpeg)
make postgresql / postgresql-down             # the same compose file, `db` service only
```

Tool configs live in `code_quality/` and are passed explicitly (`--config=code_quality/.ruff.toml`,
`--config-file=code_quality/mypy.ini`, `--rcfile=code_quality/pylint.toml`). `core/` (config, engine
and alembic) and `tests/` are excluded from linting on purpose. Ruff enforces single quotes and a
99-column line length.

Dependencies are managed by `uv` only — `uv add <pkg>` / `uv add --dev <pkg>`, never a
`requirements.txt`. The Docker image installs from `uv.lock` with `uv sync --frozen`.

Environment variables are listed in `.env.example`; copy it to `.env`. `ENVIRONMENT=production`
turns off SQL echo and the local defaults.
