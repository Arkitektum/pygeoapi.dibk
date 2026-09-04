# Fork divergences

One section per divergence from upstream. See `CLAUDE.md` for the rules that
govern how a divergence may be implemented.

Every divergence below is pinned by a test in `tests/dibk/` — a new directory,
so it never conflicts on rebase. If a rebase drops one of our hooks, a test
there fails instead of the loss going unnoticed. Run them with the rest of our
subset (`pytest -c pytest-dibk.ini`) or on their own
(`pytest -c pytest-dibk.ini tests/dibk`).

## to_json separators and ensure_ascii

**File:** `pygeoapi/util.py`, `to_json()` — 2 lines, both marked `# DIBK`.

```python
json_dump = json.dumps(dict_, default=json_serial, indent=indent,
                       separators=(', ', ': '),  # DIBK
                       ensure_ascii=False)  # DIBK
```

**Why:** upstream serializes with `ensure_ascii` at its default of `True`, so
every non-ASCII character is emitted as a `\uXXXX` escape: the value
Bærum serializes as `"B\u00e6rum"` instead of `"Bærum"`. That is valid JSON
and any conforming parser reads it back correctly, but it makes responses
unreadable for humans inspecting them
directly, which is most of how we and our users look at this API. Norwegian
place and person names contain æ, ø and å throughout.

The `separators` change is separate and cosmetic: it puts a space after each
comma and colon in non-pretty output as well.

**To drop this commit,** upstream would have to pass `ensure_ascii=False` in
`to_json()` (and, for the second half, stop using compact separators for
non-pretty output).

**Test fallout:** two upstream tests assert upstream's compact separators
byte-for-byte and therefore fail with this change. Rather than edit upstream
test files, they are deselected in `pytest-dibk.ini`:

- `tests/other/test_util.py::test_to_json` — expects `{"foo":"bar"}`
- `tests/api/test_processes.py::test_get_job_result` — expects
  `JSON.stringify({"id":"echo","value":"Hello Sync Test!"}` inside the HTML
  job-result page

Neither test covers `ensure_ascii`, so nothing about the escaping behaviour is
left untested by accident — it simply is not tested upstream at all. If the
`separators` half is ever dropped, remove both deselects.

## get_choice_from_headers tolerates media-type parameters

**File:** `pygeoapi/util.py`, `get_choice_from_headers()` — the parse loop and
the return annotation, marked `# DIBK`.

**Why:** upstream matches each comma-separated part against

```python
re.match(r'^([^;]+)(?:;q=([\d.]+))?$', part.strip())
```

which is anchored, so a part only matches when it is a bare media type or a
media type whose *sole* parameter is `q`. Any other parameter makes `match`
`None` and the part is dropped from the choice list entirely. That hits real
`Accept` headers:

- `application/vnd.ogc.sld+xml;version=1.1.0` — the OGC SE/SLD style types
  carry a `version` parameter
- `text/html;charset=utf-8` — routinely sent by clients
- `text/html;version=1.1.0;q=0.2` — `q` present, but not as the only parameter

Dropped parts do not degrade gracefully. When *every* part carries a
parameter, `choices` ends up empty and the `all=False` branch raises
`IndexError` on `sorted_choices[0]`, so content negotiation fails with a 500
instead of falling back to a default format.

Our version splits the media type off at the first `;` and finds the `q`
weight with `re.search` wherever it appears in the part, so parameterised
types are ranked instead of discarded. Media-type parameters are not part of
the returned value — callers (`pygeoapi/api/__init__.py:287`, `:320`) negotiate
on the media type alone, as upstream also intended.

**To drop this commit,** upstream would have to parse `Accept` per RFC 9110 —
media type plus arbitrary parameters, with `q` as one of them — rather than
with an anchored `type[;q=x]` regex.

**Test fallout:** none. `tests/other/test_util.py::test_get_choice_from_headers`
passes unchanged; it only exercises bare types and sole-`q` parts.

See also the `q=0` divergence below, which touches the same function.

## get_choice_from_headers handles q=0 and empty results

**File:** `pygeoapi/util.py`, `get_choice_from_headers()` — the range guard and
the final return, marked `# DIBK`.

**Why:** upstream admits `q=0` with `if 0 <= q_value <= 1:` and then computes
`1 / q_value` as the heap sort key, so `Accept: text/html;q=0` raises
`ZeroDivisionError`. Per RFC 9110 a weight of zero means "not acceptable", so
the part must be skipped, not ranked. The guard is now `0 < q_value <= 1`.

Excluding parts makes an empty result reachable — `Accept: text/html;q=0` is a
header where nothing is acceptable, and an out-of-range weight such as
`q=1.5` was already excluded upstream. Upstream's
`sorted_choices if all else sorted_choices[0]` raises `IndexError` in that
case, so the `all=False` branch now returns `None`, matching the early return
for a missing header.

`all=True` still returns `[]` rather than `None`: both callers
(`pygeoapi/api/__init__.py:287`, `:320`) pass `all=True` and treat the result
as an iterable — `if loc_strs:` and `if types_ is None: return` respectively —
so an empty list is the value that keeps them working.

**To drop this commit,** upstream would have to treat `q=0` as a rejection and
return a sentinel instead of indexing an assumed-non-empty list.

**Test fallout:** none.
