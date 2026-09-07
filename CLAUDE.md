# pygeoapi fork — DIBK

Fork of pygeoapi. Branch `dibk/0.24.0`, based on upstream tag `0.24.0`.
Upstream remote is `upstream` (https://github.com/geopython/pygeoapi).
We rebase our branch onto each upstream release rather than merging.

Written in English so commits and comments are PR-ready for upstream.

## The prime directive

The diff against tag `0.24.0` must stay as small as possible. Every line we add
to an existing upstream file is a future rebase conflict.

- New functionality goes in NEW files. New files never conflict on rebase.
- Existing upstream files get only the minimum hook lines needed to reach our code.
- Mark every line we add to an upstream file with a trailing `# DIBK` comment,
  so `git grep -n "# DIBK"` lists our entire hook surface.
- Never reformat, reorder imports, or tidy upstream code — not even obvious
  improvements. Leave it exactly as upstream has it.

## Scope

Starlette and Flask. Django is out of scope — leave `pygeoapi/django_/` and
`pygeoapi/django_app.py` alone.

Handlers go in the framework-agnostic api layer (take an `APIRequest`, return
`(headers, status, content)`). Registering them is per framework: routes for
Starlette in `pygeoapi/starlette_app.py`, for Flask in
`pygeoapi/flask_app.py`. Anything added to one must be added to the other, and
tested against both — `tests/util.py` has `mock_starlette` and `mock_flask`.

## Verify

```sh
python3 -m pytest -c pytest-dibk.ini    # our runnable subset
git diff --stat 0.24.0..HEAD            # this should stay small
```

`pytest-dibk.ini` is ours, not upstream's. Never edit upstream's pytest config
or `pyproject.toml` to change test settings — add them there instead.

Before treating a failure as a regression, check the pre-existing failure list
in `FORK.md`.

## Record a test baseline

Do this on the unmodified upstream tag, and re-record after each rebase onto a
new release:

1. `git worktree add /tmp/pygeoapi-<tag> <tag>` so the working tree stays on
   our branch and the baseline run cannot pick up our changes.
2. In that worktree, run pytest with `--continue-on-collection-errors` and `-rf`.
   Without the former, one missing dependency aborts collection and the run
   tells us nothing.
3. Extract the failing and erroring test IDs.
4. Add or replace the "Pre-existing test failures at tag <tag>" section in
   `FORK.md` with that list, the date, and a one-line note on why they fail.
5. Group by cause (missing service vs missing optional dependency) where the
   output makes that clear.
6. Include pytest's summary counts, so a truncated or aborted run is obvious.
7. Remove the worktree. Commit `FORK.md` only.

Most failures are provider tests needing live PostGIS, Elasticsearch, MongoDB
or Oracle. Check `.github/workflows/` for which services upstream CI starts
before concluding a test is unrunnable.

The api and openapi tests must stay in the runnable subset — that is where our
hooks land.

## Build

```sh
python3 -m build --wheel        # → dist/pygeoapi-0.24.0+dibk1-py3-none-any.whl
```

Deploy image is `FROM geopython/pygeoapi:0.24.0` plus
`pip install --no-deps --force-reinstall` of that wheel.

## Dev loop

The source tree is bind-mounted over the installed package in compose.
Restart the container after edits — no wheel rebuild needed.

## Never commit

Connection strings, credentials, `local.config.yml`, or any environment-specific
config. Ask before adding any file containing a hostname or password.

## Commits

One commit per concern. The message explains why the hook is needed and what
upstream would have to change for us to drop the commit entirely.

Per-divergence detail lives in `FORK.md`, not here — keep this file short.