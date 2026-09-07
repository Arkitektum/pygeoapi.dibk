# =================================================================
#
# Authors: Tor Anders Gustavsen <tor.anders@arkitektum.no>
#
# Copyright (c) 2026 Tor Anders Gustavsen
#
# Permission is hereby granted, free of charge, to any person
# obtaining a copy of this software and associated documentation
# files (the "Software"), to deal in the Software without
# restriction, including without limitation the rights to use,
# copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the
# Software is furnished to do so, subject to the following
# conditions:
#
# The above copyright notice and this permission notice shall be
# included in all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND,
# EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES
# OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND
# NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT
# HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY,
# WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING
# FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR
# OTHER DEALINGS IN THE SOFTWARE.
#
# =================================================================

"""
Regression tests for formatter support in `get_collection_items()`.

Covers the two divergences: formatter-only provider properties are stripped
from non-formatter output, and a non-attachment formatter response still
advertises a filename. See "Formatter-only provider properties" and
"Content-Disposition for inline formatters" in FORK.md.
"""

import json
from copy import deepcopy

import pytest

from pygeoapi.api import API
from pygeoapi.api.itemtypes import (get_collection_item,
                                    get_collection_items)
from pygeoapi.util import yaml_load

from ..util import get_test_file_path, mock_api_request
from .syntheticprovider import SYNTHETIC_KEY

PROVIDER = 'tests.dibk.syntheticprovider.SyntheticProvider'
INLINE_FORMATTER = 'tests.dibk.syntheticprovider.InlineFormatter'
ATTACHMENT_FORMATTER = 'tests.dibk.syntheticprovider.AttachmentFormatter'


@pytest.fixture()
def config():
    with open(get_test_file_path('pygeoapi-test-config.yml')) as fh:
        cfg = yaml_load(fh)

    obs = cfg['resources']['obs']
    obs['providers'] = [{
        'type': 'feature',
        'name': PROVIDER,
        'data': 'tests/data/obs.csv',
        'id_field': 'id'
    }]
    obs['formatters'] = [
        {'name': INLINE_FORMATTER},
        {'name': ATTACHMENT_FORMATTER}
    ]

    return cfg


def _items(config: dict, params: dict | None = None):
    return get_collection_items(
        API(config, {}), mock_api_request(params or {}), 'obs')


@pytest.mark.parametrize('params', [
    {},
    {'f': 'json'},
    {'f': 'jsonld'},
])
def test_synthetic_property_is_stripped(config, params):
    """Formatter-only keys must not reach GeoJSON, JSON-LD or HTML."""

    _, status, content = _items(config, params)

    assert int(status) == 200
    assert SYNTHETIC_KEY not in content


def test_every_formatter_gets_the_key(config):
    """Consequence worth pinning: the stripping is per output kind, not per
    formatter, so the built-in CSV formatter sees the key as a column too.
    """

    _, status, content = _items(config, {'f': 'csv'})

    assert int(status) == 200
    assert SYNTHETIC_KEY in content.decode()


def test_synthetic_property_reaches_the_formatter(config):
    """The formatter is the one consumer that needs the key."""

    headers, status, content = _items(config, {'f': 'inlinegml'})

    assert int(status) == 200
    assert '<gml:Point><gml:pos>10.7 59.9</gml:pos></gml:Point>' in content
    assert headers['Content-Type'] == 'application/gml+xml; version=3.2'


def test_other_properties_survive(config):
    _, _, content = _items(config, {'f': 'json'})
    feature = json.loads(content)['features'][0]

    assert feature['properties']['stedsnavn'] == 'Bærum'
    assert feature['geometry']['type'] == 'Point'


def test_provider_without_synthetic_keys_is_untouched(config):
    """A provider not declaring any keys must keep every property."""

    cfg = deepcopy(config)
    cfg['resources']['obs']['providers'][0]['name'] = \
        'tests.dibk.syntheticprovider.SyntheticProvider'

    from tests.dibk import syntheticprovider

    keys = syntheticprovider.SyntheticProvider.synthetic_property_keys
    syntheticprovider.SyntheticProvider.synthetic_property_keys = ()

    try:
        _, _, content = _items(cfg, {'f': 'json'})
    finally:
        syntheticprovider.SyntheticProvider.synthetic_property_keys = keys

    assert SYNTHETIC_KEY in content


def test_inline_formatter_advertises_a_filename(config):
    """Not an attachment, but Save-As must still get a real name."""

    headers, _, _ = _items(config, {'f': 'inlinegml'})

    assert headers['Content-Disposition'] == 'inline; filename="obs.gml"'


def test_attachment_formatter_is_unchanged(config):
    """Upstream's attachment path must keep behaving as it did."""

    headers, _, _ = _items(config, {'f': 'attachmentgml'})

    assert headers['Content-Disposition'] == 'attachment; filename="obs.gml"'


def test_provider_filename_wins(config):
    """A provider serving a single file names it."""

    cfg = deepcopy(config)
    cfg['resources']['obs']['providers'][0]['filename'] = 'stedsnavn.gml'

    headers, _, _ = _items(cfg, {'f': 'inlinegml'})

    assert headers['Content-Disposition'] == \
        'inline; filename="stedsnavn.gml"'


# Single item: get_collection_item()

def _item(config: dict, params: dict | None = None, identifier: str = '1'):
    return get_collection_item(
        API(config, {}), mock_api_request(params or {}), 'obs', identifier)


@pytest.mark.parametrize('params', [
    {},
    {'f': 'json'},
    {'f': 'jsonld'},
])
def test_item_synthetic_property_is_stripped(config, params):
    _, status, content = _item(config, params)

    assert int(status) == 200
    assert SYNTHETIC_KEY not in content


def test_item_reaches_the_formatter(config):
    headers, status, content = _item(config, {'f': 'inlinegml'})

    assert int(status) == 200
    assert '<gml:Point><gml:pos>10.7 59.9</gml:pos></gml:Point>' in content
    assert headers['Content-Type'] == 'application/gml+xml; version=3.2'
    assert headers['Content-Disposition'] == 'inline; filename="obs.gml"'


def test_item_attachment_formatter(config):
    headers, _, _ = _item(config, {'f': 'attachmentgml'})

    assert headers['Content-Disposition'] == 'attachment; filename="obs.gml"'


def test_item_invalid_format(config):
    """The handler validates, since the app modules no longer do."""

    _, status, content = _item(config, {'f': 'bogus'})

    assert int(status) == 400
    assert json.loads(content)['code'] == 'InvalidParameterValue'


def test_item_formatter_links(config):
    _, _, content = _item(config, {'f': 'json'})
    links = json.loads(content)['links']
    hrefs = [link['href'] for link in links if link['rel'] == 'alternate']

    assert any(href.endswith('?f=inlinegml') for href in hrefs)
    assert any(href.endswith('?f=attachmentgml') for href in hrefs)


def test_item_prev_next_links_with_a_custom_format(config):
    """A custom format must not be looked up in FORMAT_TYPES.

    Upstream builds the prev/next link types from
    `FORMAT_TYPES[request.format]`, which raises KeyError for any format that
    belongs to a formatter rather than to the global table.
    """

    cfg = deepcopy(config)
    cfg['resources']['obs']['providers'][0]['name'] = \
        'tests.dibk.syntheticprovider.PagedProvider'

    _, status, content = _item(cfg, {'f': 'inlinegml'})

    assert int(status) == 200
    assert '<gml:pos>10.7 59.9</gml:pos>' in content


def test_item_prev_next_links_are_json_by_default(config):
    cfg = deepcopy(config)
    cfg['resources']['obs']['providers'][0]['name'] = \
        'tests.dibk.syntheticprovider.PagedProvider'

    _, _, content = _item(cfg, {'f': 'json'})
    links = json.loads(content)['links']

    for rel in ('prev', 'next'):
        link = [ln for ln in links if ln['rel'] == rel][0]
        assert link['type'] == 'application/json'
        assert link['href'].endswith('?f=json')
