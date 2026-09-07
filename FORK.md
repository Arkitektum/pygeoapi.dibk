# Fork divergences

One section per divergence from upstream. See `CLAUDE.md` for the rules that
govern how a divergence may be implemented.

Every divergence below is pinned by a test in `tests/dibk/` — a new directory,
so it never conflicts on rebase. If a rebase drops one of our hooks, a test
there fails instead of the loss going unnoticed. Run them with the rest of our
subset (`pytest -c pytest-dibk.ini`) or on their own
(`pytest -c pytest-dibk.ini tests/dibk`).

`tests/dibk/test_starlette_styles.py` drives the whole request path through
the Starlette app, using the style provider stub in
`tests/dibk/styleprovider.py` and the config in
`tests/dibk/pygeoapi-test-config-styles.yml`. Two pieces of upstream global
state leak between tests and had to be neutralised in its fixture rather than
in upstream's `tests/util.py`:

- `API.__init__` writes `FORMAT_TYPES[F_GZIP]` when a config enables gzip and
  never removes it, so whether responses are gzip encoded depends on which
  tests ran first. Worth knowing beyond the tests: on the invalid-format path
  `execute_from_starlette` sets `Content-Encoding: gzip` via
  `get_response_headers` but never calls `apply_gzip`, so with gzip enabled a
  bad `?f=` value returns a response no client can decode.
- `mock_starlette` deletes `pygeoapi.starlette_app` from `sys.modules` on
  teardown but leaves the attribute on the package, so its own `reload()`
  raises on the second use in a session.

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

**Routes** — `pygeoapi/starlette_app.py`, 2 lines:

```python
from pygeoapi.starlette_styles import style_routes  # DIBK
...
    *style_routes,  # DIBK
```

The async handlers live in `pygeoapi/starlette_styles.py`, a new file, so
registering four routes costs `starlette_app.py` two lines rather than the
forty a handler per route would take. That file imports
`execute_from_starlette` inside each handler, because `starlette_app` imports
it at module level and the import would otherwise be circular.

The unpack sits before `Route('/collections/{collection_id:path}', ...)`. That
route uses the `:path` converter, so anything after it would swallow
`/collections/{collectionId}/styles`; `tests/dibk/test_starlette_styles.py`
asserts the ordering rather than trusting it.

**Routes** — `pygeoapi/flask_app.py`, 2 lines:

```python
from pygeoapi.flask_styles import register_style_routes  # DIBK
...
register_style_routes(BLUEPRINT)  # DIBK: must precede the registration below
```

`pygeoapi/flask_styles.py` mirrors `starlette_styles.py`: the same four
endpoints over the same api handlers, kept out of the app module for the same
reason, with `execute_from_flask` imported inside each handler to avoid the
import loop.

Two differences, both Flask's:

- Rules are added with `blueprint.add_url_rule()` rather than
  `@BLUEPRINT.route`, because the blueprint is created in `flask_app` and this
  module must not import it.
- The call has to precede `APP.register_blueprint(BLUEPRINT)`. Flask rejects
  rules added to an already registered blueprint. `mock_flask` reloads the
  module, which rebuilds `BLUEPRINT`, so this runs again on a fresh blueprint
  and does not double-register.

Route order does not matter here the way it does under Starlette: Werkzeug
matches on rule specificity rather than declaration order, which is why
upstream's `/collections/<path:collection_id>/schema` already coexists with
`/collections/<path:collection_id>`. `tests/dibk/test_flask_styles.py` asserts
the collection routes still resolve anyway.

Django is deliberately not wired up: `pygeoapi/django_/urls.py` would need the
same treatment and nothing here uses it. `CLAUDE.md` records that scope.

`get_oas_30()` returns an empty fragment when no style resource and no
collection style provider is configured, matching how the other api modules
behave, so a deployment without styles gets no `/styles` paths, no `styles`
tag and no style components.

## Styles on the landing page

**File:** `pygeoapi/api/__init__.py`, `landing_page()` — 5 lines, all marked
`# DIBK`.

```python
    from . import styles as styles_api  # DIBK: import loop at module level
    if styles_api.has_styles(api.config):  # DIBK
        fcm['links'].append(styles_api.get_landing_page_link(  # DIBK
            api.base_url, request.locale))  # DIBK
...
        fcm['styles'] = styles_api.has_styles(api.config)  # DIBK
```

**Why:** nothing pointed clients at `/styles`. The link uses the
`http://www.opengis.net/def/rel/ogc/1.0/styles` relation type, and
`fcm['styles']` is the flag the HTML template needs to show a styles section.

The link object itself is built in `pygeoapi/api/styles.py`
(`get_landing_page_link()`), so the rel type, media type, title and href live
in our own file and the hook stays at four lines. The import is inside the
function for the same reason `all_apis()` defers its imports.

**Both are gated on `has_styles()`** — a style resource or a collection style
provider being configured. Two reasons beyond not advertising what an instance
cannot serve: it matches the `get_oas_30()` gate, and
`tests/api/test_api.py::test_root` asserts an exact landing page link count
for the stock test config. An unconditional link breaks that test, and
deselecting it would blind us to landing page regressions in the one function
we have hooked.

Note that upstream's `landing_page.html` has no `data['styles']` section, so
the flag does nothing until a template override adds one. The JSON link works
today.

## Provider supplied collection schemas

**Files:** `pygeoapi/api/provider_schema.py` — a new file. Hooked from
`pygeoapi/api/__init__.py` with 3 lines, all marked `# DIBK`: the import and

```python
    schema = apply_provider_schema(  # DIBK
        p, schema, api.config['resources'][dataset], request.locale)  # DIBK
```

**Why:** `get_collection_schema()` only ever derives a schema from the
provider's field list, so a provider that already has a real JSON Schema — one
of ours reads them from disk — has no way to serve it. `/schema` then
advertises a flat property list instead of the actual schema, losing
`required`, nested objects, enumerations and per-property documentation.

A provider opts in by implementing `get_collection_schema()`. Providers
without the method, which is all of upstream's, are unaffected.

**Who owns which keyword:**

| keyword | comes from | why |
| --- | --- | --- |
| `$schema` | the provider, when it declares one | the dialect belongs to whoever wrote the schema; a 2020-12 document must not be served as 2019-09 |
| `$id` | always the server | it is the endpoint the schema is served from, not something a provider may claim |
| `title` | the collection configuration | one collection, one title, however the schema was produced |
| `description` | the collection configuration | see below |

Providers without a `$schema` fall back to pygeoapi's draft 2019-09, so the
derived path is unchanged.

**The collection description is now in the schema** for both paths — derived
and provider supplied. Upstream puts `title` in the schema but not
`description`. No upstream test asserted its absence.

**Keyword order is `$schema`, `$id`, `title`, `description`**, then whatever
else the schema carries in its own order. Upstream emitted the derived schema
as `type`, `title`, `properties`, `$schema`, `$id`, which reads oddly with
`$id` buried at the end. This is presentation only; JSON object member order
carries no meaning, and `to_json` preserves insertion order.

**The derived schema is still computed** even when the provider supplies its
own, and then discarded. That is deliberate: the alternative is either
indenting upstream's thirty-line derivation under a conditional, or
duplicating the HTML and JSON response tail in our module to return early.
Three hook lines and one wasted field walk is the cheaper trade. If a
provider's `fields` is expensive, revisit it.

Keeping upstream's derivation in place also preserves the `p.properties`
whitelist filter:

```python
        if p.properties:
            if k not in p.properties:
                continue
```

which a rewrite of the function into a helper is easy to lose — that would
silently expose fields a collection deliberately hides.
`tests/dibk/test_provider_schema.py` covers it.

## Formatter-only provider properties

**Files:** `pygeoapi/api/synthetic_properties.py` — a new file. Hooked from
`pygeoapi/api/itemtypes.py::get_collection_items()` with 4 lines, all marked
`# DIBK`: the import and

```python
    formatter_formats = [df.f for df in dataset_formatters.values()]  # DIBK
    if request.format not in formatter_formats:  # DIBK
        strip_synthetic_properties(content.get('features', []), p)  # DIBK
```

**Why:** a provider may put values into `feature['properties']` that exist
only as input for a custom formatter. Ours does: `postgresql_ext` with
`gml_passthrough` adds `_geometry_gml`, holding the GML the database produced,
which the GML formatter writes out verbatim. Without stripping, that key also
appears in the GeoJSON, JSON-LD and HTML output, where it is noise at best and
a duplicated geometry at worst.

The provider declares the keys in `synthetic_property_keys`; providers that
declare nothing are untouched, which is all of upstream's.

**Stripping is per output kind, not per formatter.** Any request whose format
belongs to a formatter keeps the keys — including the built-in CSV formatter,
so `?f=csv` shows `_geometry_gml` as a column.
`tests/dibk/test_synthetic_properties.py::test_every_formatter_gets_the_key`
pins that, because it is a consequence rather than an intention. Making it
opt-in per formatter would need a flag on the formatter definition.

**To drop this commit,** upstream would have to give providers a way to pass
data to a formatter out of band, rather than through the feature properties.

## Custom formatters on a single item

**Files:** `pygeoapi/api/dataset_formatters.py` — a new file. Hooked from
`pygeoapi/api/itemtypes.py::get_collection_item()` with 12 lines, all marked
`# DIBK`, and one line each in `pygeoapi/flask_app.py` and
`pygeoapi/starlette_app.py`.

**Why:** `get_collection_items()` negotiates a collection's configured
formatters and runs them; `get_collection_item()` does neither. A custom
format is therefore available on the item list but not on an individual
feature, which is the request a client makes when it wants one thing.

The hooks, in order through the function:

1. `negotiate_dataset_format()` — the same re-negotiation
   `get_collection_items()` does inline, because the formats a collection
   accepts are not known until its configuration is read.
2. `strip_synthetic_properties()` on the single feature, for the same reason
   as on the item list.
3. `get_alternate_links()` — one `alternate` link per formatter.
4. `write_item()` — wraps the feature in a FeatureCollection, since that is
   what a formatter takes, then writes it and sets `Content-Type` and
   `Content-Disposition`.

**`skip_valid_check=True` in both app modules.** `execute_from_flask` and
`execute_from_starlette` validate the request format before calling the
handler, using only the global `FORMAT_TYPES`, so `?f=<custom>` was rejected
with 400 before the handler could read the collection's formatters. The item
*list* call already passed `skip_valid_check=True` upstream; the single item
call did not. Validation is not lost — hook 1 rejects an unknown format with
the same 400 — and `tests/dibk/test_item_formatters.py` asserts that through
both frameworks.

**`link_request_format` had to change**, 1 line:

```python
    link_request_format = (
        request.format if request.format in FORMAT_TYPES else F_JSON  # DIBK
    )
```

Upstream tests `request.format is not None` and then indexes
`FORMAT_TYPES[link_request_format]`, so any format belonging to a formatter
raises `KeyError`. This is not only our problem: `?f=csv` on a provider whose
`get()` returns `prev` or `next` already raises it upstream, since `csv` is a
formatter format and not in `FORMAT_TYPES` either.

`write_item()` passes the provider definition already loaded in the function
as the formatter's `provider_def` option, rather than calling
`get_provider_by_type(..., 'feature')` again the way `get_collection_items()`
does. Same value for a feature collection, and it does not raise
`ProviderTypeError` on a record collection.

## Content-Disposition for inline formatters

**File:** `pygeoapi/api/itemtypes.py`, `get_collection_items()` — 3 lines, all
marked `# DIBK`.

```python
        else:  # DIBK: render inline, but still name the download
            filename = p.filename or f'{dataset}.{formatter.extension}'  # DIBK
            headers['Content-Disposition'] = f'inline; filename="{filename}"'
```

**Why:** upstream sets `Content-Disposition` only when the formatter declares
`attachment: true`. For a formatter meant to render in the browser, no header
is sent at all, so a user choosing Save As gets a filename derived from the
last path segment of the URL — `items`, with no extension.

Added as an `else` on upstream's `if formatter.attachment:` rather than by
making the block unconditional, which would have meant reindenting six
upstream lines. The attachment path is byte-identical to upstream.

## Style links on collections

**File:** `pygeoapi/api/collection.py`, `gen_collection()` — 3 lines, all
marked `# DIBK`.

```python
    from pygeoapi.api import styles as styles_api  # DIBK: import loop
    data['links'].extend(styles_api.get_collection_links(  # DIBK
        config, api.get_collections_url(), dataset, locale_))  # DIBK
```

**Why:** a collection with a style provider gave no way to discover its
styles. `get_collection_links()` returns the two link objects — JSON and
HTML, both with the
`http://www.opengis.net/def/rel/ogc/1.0/styles` relation type — or an empty
list when the collection has no `style` provider, so collections without
styles are untouched and the upstream collection tests stay green.

Building the links in `pygeoapi/api/styles.py` avoids adding
`filter_providers_by_type` to `collection.py`'s import list, which would mean
changing an upstream line rather than adding ones. The import is inside the
function because `pygeoapi/api/__init__.py` imports `collection` at module
level, so a module level import of `styles` here would close an import loop.

Note the HTML link points at `/collections/{collectionId}/styles` with no
`f=html`, because that endpoint answers 415 for HTML until a template exists.
Its `type` therefore claims `text/html` for what is currently a JSON
response. Adding `?f=html` would make it an explicit 415 instead.

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

## Pre-existing test failures at tag 0.24.0

Recorded 2026-09-07 by running our subset (`pytest -c pytest-dibk.ini`) in a
clean worktree at tag `0.24.0`, so nothing of ours could affect it. Re-record
after each rebase onto a new release.

```
49 failed, 283 passed, 3 deselected, 25 warnings, 14 errors
```

These fail on the unmodified tag. Before treating a failure as a regression,
check it against this list — and note that the counts move with the
environment: the same tag gave 46 failures on an older virtualenv in this
container, so compare failing test IDs rather than totals.

### Missing optional dependency

`osgeo` (GDAL), `xarray`, `owslib`, `geopandas`, `geoalchemy2`, `sodapy` and
`pygeometa` are not installed. The 14 collection errors are all of this kind,
which is why the subset must run with `--continue-on-collection-errors`:

```
ERROR tests/other/test_ogr_capabilities.py
ERROR tests/provider/test_csw_provider.py
ERROR tests/provider/test_csw_provider_live.py
ERROR tests/provider/test_ogr_csv_provider.py
ERROR tests/provider/test_ogr_esrijson_provider.py
ERROR tests/provider/test_ogr_gpkg_provider.py
ERROR tests/provider/test_ogr_shapefile_provider.py
ERROR tests/provider/test_ogr_sqlite_provider.py
ERROR tests/provider/test_ogr_wfs_provider.py
ERROR tests/provider/test_ogr_wfs_provider_live.py
ERROR tests/provider/test_parquet_provider.py
ERROR tests/provider/test_socrata_provider.py
ERROR tests/provider/test_socrata_provider_live.py
ERROR tests/provider/test_sql_pool_options.py
```

Failures from the same cause:

```
FAILED tests/api/test_coverages.py::test_get_collection_coverage      # xarray
FAILED tests/api/test_processes.py::test_describe_processes           # pygeometa
FAILED tests/other/test_openapi.py::test_get_oas                     # xarray
FAILED tests/other/test_openapi.py::test_get_oas_ogc_service_contact # pygeometa
FAILED tests/provider/test_api_ogr_provider.py::test_get_collection_items_bbox_crs
FAILED tests/provider/test_api_ogr_provider.py::test_get_collection_items_crs
FAILED tests/api/test_api.py::test_describe_collections               # 7 of 10 collections load
```

### No network access

This container reaches the internet through an allowlisting proxy, so tests
against live services fail with `ProxyError` or `socket.gaierror`:

```
FAILED tests/api/test_maps.py::test_get_collection_map
FAILED tests/api/test_maps.py::test_map_crs_transform
FAILED tests/api/test_processes.py::test_execute_process
FAILED tests/api/test_api.py::test_root_structured_data
FAILED tests/api/test_api.py::test_describe_collections_json_ld
FAILED tests/other/test_util.py::test_is_request_allowed[https://pygeoapi.io-False-True]
FAILED tests/other/test_util.py::test_is_request_allowed[https://pygeoapi.io-True-True]
FAILED tests/provider/test_esri_provider.py::test_query
FAILED tests/provider/test_esri_provider.py::test_no_count
FAILED tests/provider/test_esri_provider.py::test_geometry
FAILED tests/provider/test_esri_provider.py::test_query_bbox
FAILED tests/provider/test_esri_provider.py::test_query_properties
FAILED tests/provider/test_esri_provider.py::test_query_sortby_datetime
FAILED tests/provider/test_esri_provider.py::test_get
FAILED tests/provider/test_esri_provider.py::test_alternative_id_field
FAILED tests/provider/test_wms_facade_provider.py::test_crs_query
```

The two JSON-LD failures need `https://schema.org/docs/jsonldcontext.jsonld`.

### Missing test data or fixtures

```
FAILED tests/provider/test_sqlite_geopackage_provider.py::test_get_fields_sqlite
FAILED tests/provider/test_sqlite_geopackage_provider.py::test_query_sqlite
FAILED tests/provider/test_sqlite_geopackage_provider.py::test_get_fields_geopackage
FAILED tests/provider/test_sqlite_geopackage_provider.py::test_query_geopackage
FAILED tests/provider/test_sqlite_geopackage_provider.py::test_query_hits_sqlite_geopackage
FAILED tests/provider/test_sqlite_geopackage_provider.py::test_query_with_property_filter_sqlite_geopackage
FAILED tests/provider/test_sqlite_geopackage_provider.py::test_query_with_property_filter_bbox_sqlite_geopackage
FAILED tests/provider/test_sqlite_geopackage_provider.py::test_query_bbox_sqlite_geopackage
FAILED tests/provider/test_sqlite_geopackage_provider.py::test_no_count
FAILED tests/provider/test_sqlite_geopackage_provider.py::test_get_sqlite
FAILED tests/provider/test_sqlite_geopackage_provider.py::test_get_geopackage
FAILED tests/provider/test_sqlite_geopackage_provider.py::test_get_sqlite_not_existing_item_raise_exception
FAILED tests/provider/test_sqlite_geopackage_provider.py::test_get_geopackage_not_existing_item_raise_exception
FAILED tests/provider/test_sqlite_geopackage_provider.py::test_get_geopackage_skip_geometry
FAILED tests/provider/test_filesystem_provider.py::test_query
```

`sqlite.py` raises `ProviderConnectionError` — the SpatiaLite extension is not
loadable here.

### Upstream test isolation and environment

```
FAILED tests/api/test_api.py::test_apirules_inactive
FAILED tests/api/test_api.py::test_api_exception
FAILED tests/api/test_api.py::test_gzip
FAILED tests/other/test_l10n.py::test_translate_gettext
FAILED tests/other/test_crs.py::test_modify_pygeofilter[unnested-geometry-transformed-coords-explicit-input-crs-ewkt]
FAILED tests/other/test_crs.py::test_modify_pygeofilter[unnested-geometry-transformed-coords-explicit-input-crs-filter-crs]
FAILED tests/other/test_crs.py::test_modify_pygeofilter[unnested-geometry-transformed-coords-ewkt-crs-overrides-filter-crs]
FAILED tests/provider/test_base_provider.py::test_unique_subclass_query_types
FAILED tests/api/test_environmental_data_retrieval.py::test_describe_collection_edr
FAILED tests/api/test_environmental_data_retrieval.py::test_get_collection_edr_query
FAILED tests/api/test_environmental_data_retrieval.py::test_get_collection_edr_query_crs
```

The three `test_api.py` failures are `KeyError: 'pygeoapi.flask_app'` from
`mock_flask` in `tests/util.py`, the Flask twin of the `mock_starlette` reload
problem described at the top of this file. `test_translate_gettext` wants
compiled locale catalogues. The EDR failures are `KeyError:
'parameter_names'`, from the xarray provider being unavailable.
