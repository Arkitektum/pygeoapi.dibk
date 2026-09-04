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
End-to-end tests for the OGC API - Styles routes, driven through the Starlette
app with the stub provider in tests/dibk/styleprovider.py.

These are the only tests that cover the request path as a whole: routing, the
api handlers, stylesheet format negotiation and serialization. See
"OGC API - Styles" and "Style formats in FORMAT_TYPES" in FORK.md.
"""

import sys

import pytest

import pygeoapi
from pygeoapi.formats import FORMAT_TYPES, F_GZIP
from pygeoapi.starlette_styles import style_routes

from ..util import mock_starlette

CONFIG = 'dibk/pygeoapi-test-config-styles.yml'


@pytest.fixture(scope='module')
def client():
    # `mock_starlette` drops pygeoapi.starlette_app from sys.modules on
    # teardown but leaves the attribute on the package, so its own
    # `reload()` raises the next time it is used in the same session.
    # Clearing the stale attribute makes that a fresh import instead.
    if ('pygeoapi.starlette_app' not in sys.modules
            and hasattr(pygeoapi, 'starlette_app')):
        delattr(pygeoapi, 'starlette_app')

    # `API.__init__` adds F_GZIP to the module level FORMAT_TYPES when a
    # config enables gzip and never removes it, so whether responses here
    # are compressed depends on which tests ran first. Take it out for the
    # duration of this module and put back whatever was there.
    gzip_mimetype = FORMAT_TYPES.pop(F_GZIP, None)

    try:
        with mock_starlette(CONFIG) as client_:
            yield client_
    finally:
        if gzip_mimetype is not None:
            FORMAT_TYPES[F_GZIP] = gzip_mimetype


def test_routes_are_registered(client):
    """The routes must be in the app, before the /collections catch-all"""

    from pygeoapi import starlette_app

    paths = [route.path for route in starlette_app.api_routes]
    style_paths = [route.path for route in style_routes]

    for path in style_paths:
        assert path in paths

    catch_all = paths.index('/collections/{collection_id:path}')

    for path in style_paths:
        assert paths.index(path) < catch_all, f'{path} is shadowed'


def test_get_styles(client):
    response = client.get('/styles')
    content = response.json()

    assert response.status_code == 200
    assert [style['id'] for style in content['styles']] == [
        'kommune', 'bygning', 'observasjon']
    assert [link['rel'] for link in content['links']] == ['alternate', 'self']


def test_get_style(client):
    response = client.get('/styles/kommune')

    assert response.status_code == 200
    assert response.json() == {'id': 'kommune', 'title': 'Kommunegrenser'}


def test_get_style_not_found(client):
    response = client.get('/styles/nope')

    assert response.status_code == 404
    assert response.json()['code'] == 'NotFound'


def test_get_style_metadata(client):
    response = client.get('/styles/kommune/metadata')
    content = response.json()

    assert response.status_code == 200
    assert content['id'] == 'kommune'
    assert content['description'] == 'Stilsett for Bærum og Ålesund'

    hrefs = [link['href'] for link in content['links']]

    assert 'http://localhost:5000/styles/kommune/metadata?f=json' in hrefs
    assert 'http://localhost:5000/styles/kommune/metadata?f=html' in hrefs


def test_get_style_metadata_keeps_non_ascii(client):
    """Our to_json divergence must hold on a real response."""

    response = client.get('/styles/kommune/metadata')

    assert 'Bærum' in response.text
    assert '\\u' not in response.text


def test_get_style_metadata_not_found(client):
    response = client.get('/styles/nope/metadata')

    assert response.status_code == 404


def test_get_collection_styles(client):
    response = client.get('/collections/obs/styles')
    content = response.json()

    assert response.status_code == 200
    assert [style['id'] for style in content['styles']] == ['observasjon']

    hrefs = [link['href'] for link in content['links']]

    assert 'http://localhost:5000/collections/obs/styles?f=json' in hrefs


def test_get_collection_styles_collection_not_found(client):
    response = client.get('/collections/nope/styles')

    assert response.status_code == 404
    assert response.json()['description'] == 'Collection not found'


def test_collections_route_still_works(client):
    """The style routes must not shadow the /collections routes."""

    assert client.get('/collections').status_code == 200
    assert client.get('/collections/obs').json()['id'] == 'obs'


@pytest.mark.parametrize('query,content_type,root', [
    ['?f=sld10', 'application/vnd.ogc.sld+xml;version=1.0.0', 'sld10'],
    ['?f=se11', 'application/vnd.ogc.se+xml;version=1.1.0', 'se11'],
])
def test_get_stylesheet_by_query_param(client, query, content_type, root):
    response = client.get(f'/styles/kommune{query}')

    assert response.status_code == 200
    assert response.headers['content-type'].startswith(content_type)
    assert response.text.startswith(f'<?xml version="1.0"?><{root} ')


@pytest.mark.parametrize('accept,content_type,root', [
    ['application/vnd.ogc.sld+xml;version=1.0.0',
     'application/vnd.ogc.sld+xml;version=1.0.0', 'sld10'],
    ['application/vnd.ogc.se+xml;version=1.1.0',
     'application/vnd.ogc.se+xml;version=1.1.0', 'se11'],
])
def test_get_stylesheet_by_accept_header(client, accept, content_type, root):
    """The whole point of the FORMAT_TYPES entries: negotiation by Accept."""

    response = client.get('/styles/kommune', headers={'accept': accept})

    assert response.status_code == 200
    assert response.headers['content-type'].startswith(content_type)
    assert f'<{root} ' in response.text


def test_get_stylesheet_missing_for_style(client):
    """bygning has no se11 stylesheet, though another style does."""

    response = client.get('/styles/bygning?f=se11')

    assert response.status_code == 404


def test_get_style_html_is_unsupported(client):
    response = client.get('/styles/kommune?f=html')

    assert response.status_code == 415


def test_get_style_invalid_format(client):
    response = client.get('/styles/kommune?f=bogus')

    assert response.status_code == 400
    assert response.json()['code'] == 'InvalidParameterValue'
