# Fork divergences

One section per divergence from upstream. See `CLAUDE.md` for the rules that
govern how a divergence may be implemented.

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
