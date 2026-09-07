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
Route level tests for custom formatters on a single item.

The api handler negotiates the collection's formatters itself, which only
works because both app modules pass `skip_valid_check=True` — otherwise the
request is rejected before the handler can read the configuration. Both
frameworks are driven here for that reason. See "Custom formatters on a single
item" in FORK.md.
"""

import sys

import pytest

import pygeoapi
from pygeoapi.formats import FORMAT_TYPES, F_GZIP

from ..util import mock_flask, mock_starlette
from .syntheticprovider import SYNTHETIC_KEY

CONFIG = 'dibk/pygeoapi-test-config-formatters.yml'
ITEM = '/collections/obs/items/1'


def _clear_stale_app_module(name: str) -> None:
    """`mock_flask` and `mock_starlette` unload the module but leave the
    attribute on the package, which breaks their own reload() next time.
    """

    if f'pygeoapi.{name}' not in sys.modules and hasattr(pygeoapi, name):
        delattr(pygeoapi, name)


@pytest.fixture(scope='module', params=['flask', 'starlette'])
def client(request):
    """The same assertions against both frameworks"""

    framework = request.param
    _clear_stale_app_module(f'{framework}_app')

    # Whether responses are gzip encoded otherwise depends on test order
    gzip_mimetype = FORMAT_TYPES.pop(F_GZIP, None)
    mock = mock_flask if framework == 'flask' else mock_starlette

    try:
        with mock(CONFIG) as client_:
            yield client_
    finally:
        if gzip_mimetype is not None:
            FORMAT_TYPES[F_GZIP] = gzip_mimetype


def _text(response) -> str:
    return response.text


def _json(response) -> dict:
    """Flask exposes `json` as a property, httpx as a method"""

    payload = response.json

    return payload() if callable(payload) else payload


def test_item_as_inline_formatter(client):
    response = client.get(f'{ITEM}?f=inlinegml')

    assert response.status_code == 200
    assert response.headers['Content-Type'] == \
        'application/gml+xml; version=3.2'
    assert response.headers['Content-Disposition'] == \
        'inline; filename="obs.gml"'
    assert '<gml:pos>10.7 59.9</gml:pos>' in _text(response)


def test_item_as_attachment_formatter(client):
    response = client.get(f'{ITEM}?f=attachmentgml')

    assert response.status_code == 200
    assert response.headers['Content-Disposition'] == \
        'attachment; filename="obs.gml"'


def test_item_accept_header_negotiation(client):
    """The formatter mimetypes are only known from the configuration."""

    response = client.get(ITEM, headers={
        'accept': 'application/gml+xml; version=3.2'})

    assert response.status_code == 200
    assert '<wfs:FeatureCollection>' in _text(response)


def test_item_default_output_is_geojson(client):
    response = client.get(ITEM)

    assert response.status_code == 200
    assert SYNTHETIC_KEY not in _text(response)
    assert 'Bærum' in _text(response)


def test_item_advertises_the_formatters(client):
    links = _json(client.get(ITEM))['links']
    hrefs = [link['href'] for link in links if link['rel'] == 'alternate']

    assert any(href.endswith('?f=inlinegml') for href in hrefs)
    assert any(href.endswith('?f=attachmentgml') for href in hrefs)


def test_item_invalid_format_is_still_rejected(client):
    """skip_valid_check moves validation into the handler, not away."""

    response = client.get(f'{ITEM}?f=bogus')

    assert response.status_code == 400


def test_item_not_found(client):
    """Upstream answers 400 for an unknown identifier; unchanged."""

    assert client.get('/collections/obs/items/999').status_code == 400
