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

## OGC API - Styles

**Files:** `pygeoapi/api/styles.py` — a new file, no upstream surface.

**Why:** upstream has no OGC API - Styles implementation. The handlers follow
the api-layer contract (take an `APIRequest`, return
`(headers, status, content)`) and expect a provider plugin of type `style`
implementing the `BaseStyleProvider` interface declared in the same file.

**Registration** — `pygeoapi/api/__init__.py`, 2 lines in `all_apis()`:

```python
    from . import styles  # DIBK
    ...
        'style': styles,  # DIBK
```

A separate `from . import styles` line rather than an entry in the existing
import tuple, so a rebase sees an added line instead of a changed one.
`all_apis()` is the single dispatch table for both `openapi.py` (which calls
`get_oas_30()` on every registered module) and `conformance()`, so this one
hook covers the OpenAPI document and the conformance declaration. The module
exposes `CONFORMANCE_CLASSES` as an alias of `CONFORMANCE_CLASSES_STYLES`,
because `conformance()` looks up that exact name.

**Still not wired up:** the routes in `pygeoapi/starlette_app.py`. Until they
land, the OpenAPI document advertises `/styles` and the handlers are
unreachable.

`get_oas_30()` returns an empty fragment when no style resource and no
collection style provider is configured, matching how the other api modules
behave, so a deployment without styles gets no `/styles` paths, no `styles`
tag and no style components.

## Component definitions from api modules

**File:** `pygeoapi/openapi.py` — 2 lines, both marked `# DIBK`.

```python
            for name, defs in sub_paths.get('components', {}).items():  # DIBK
                oas['components'].setdefault(name, {}).update(defs)  # DIBK
```

**Why:** `get_oas_30()` merges only `sub_paths['paths']` and `sub_tags` from
each api module, so a module cannot contribute the components its own paths
reference. Every component in the served document is hardcoded in
`openapi.py`, extended in place for tiles and queryables.

Our styles fragment refs `#/components/parameters/styleId`,
`#/components/parameters/collectionIdStyles`, `#/components/schemas/styles`
and `#/components/schemas/stylemetadata`. Without this hook those refs dangle
and the document fails `validate_openapi_document()`.

Merging a `components` key lets the definitions live in
`pygeoapi/api/styles.py` next to the paths that use them, which keeps the
upstream surface at two lines instead of a block of schema literals in
`openapi.py`. The merge is per component group (`parameters`, `schemas`, …)
and `setdefault` means a module may introduce a group `openapi.py` does not
already define.

**To drop this commit,** upstream would have to let api modules return their
own component definitions — worth proposing regardless of styles, since it is
what the `get_oas_30()` per-module contract is missing.

## conformance() for resource types without providers

**File:** `pygeoapi/api/__init__.py` — 3 lines, all marked `# DIBK`.

```python
        elif value['type'] in apis_dict:  # DIBK
            conformance_list.extend(  # DIBK
                apis_dict[value['type']].CONFORMANCE_CLASSES)  # DIBK
```

**Why:** `conformance()` special-cases `type: process` and then assumes every
other resource has a `providers` list:

```python
        else:
            for provider in value['providers']:
```

A global style resource is `type: style` with a single `provider` key (the
shape `pygeoapi/api/styles.py::_get_provider_defs` reads), so `/conformance`
raised `KeyError: 'providers'` as soon as one was configured — a 500 on a core
endpoint, from configuration alone.

Resolving the conformance classes from the resource type when that type maps
to an api module fixes it and is how a resource-level api module should be
handled in general. Collection-level style providers keep going through the
`else` branch. No existing resource type is affected: `collection` and
`stac-collection` are not keys of `all_apis()`.

**To drop this commit,** upstream would have to stop assuming `providers` is
present on every non-process resource.

## Style formats in FORMAT_TYPES

**File:** `pygeoapi/formats.py` — 6 lines, all marked `# DIBK`.

```python
F_MAPBOX = 'mapbox'
F_SE11 = 'se11'
F_SLD10 = 'sld10'
```

mapped to `application/vnd.mapbox.style+json`,
`application/vnd.ogc.se+xml;version=1.1.0` and
`application/vnd.ogc.sld+xml;version=1.0.0`.

**Why:** `APIRequest._get_format()` resolves an `Accept` header only against
`FORMAT_TYPES`, so without these entries a request for a stylesheet
(`Accept: application/vnd.ogc.sld+xml;version=1.0.0`) resolves to `None` and
`pygeoapi/api/styles.py` falls back to the JSON style document. This is the
other half of the parameter-tolerant `get_choice_from_headers` above:
`_get_format()` compares `m.split(';')[0]`, so both sides of the comparison
now ignore media-type parameters and the versioned style types match.

**Consequences to be aware of:**

- `FORMAT_TYPES` is global, so `?f=se11` is accepted by *every* endpoint.
  `GET /collections?f=se11` returns a JSON body with
  `Content-Type: application/vnd.ogc.se+xml;version=1.1.0`. Upstream's
  `is_valid()` checks membership in `FORMAT_TYPES` and nothing narrows it
  per-resource. Endpoint-scoped formats would need the `extra_formats`
  argument of `_get_format()` instead, which is how `itemtypes.py` handles
  dataset formatters.
- Media-type parameters are dropped when matching, so *any*
  `application/vnd.ogc.sld+xml` request resolves to `sld10`, whatever version
  it asks for. SLD 1.1 is served as `se11` (Symbology Encoding), matching the
  `sld-11` conformance class.
- `pygeoapi/api/styles.py::_has_stylesheet` compares the negotiated format
  against `stylesheet['type']` in the provider config, so those entries must
  use these short names (`se11`, `sld10`, `mapbox`), not the MIME types.

**To drop this commit,** upstream would have to ship OGC API - Styles with its
stylesheet media types registered, or expose a per-resource format hook that
does not require touching the global table.
