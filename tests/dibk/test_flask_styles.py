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
End-to-end tests for the OGC API - Styles routes under Flask.

The Starlette twin is tests/dibk/test_starlette_styles.py; both drive the same
api handlers and the same stub provider, so the two frameworks are asserted to
behave the same. See "OGC API - Styles" in FORK.md.
"""

import sys

import pytest

import pygeoapi
from pygeoapi.flask_styles import STYLE_ROUTES
from pygeoapi.formats import FORMAT_TYPES, F_GZIP

from ..util import mock_flask

CONFIG = 'dibk/pygeoapi-test-config-styles.yml'


@pytest.fixture(scope='module')
def client():
    # Same two pieces of upstream global state as the Starlette tests work
    # around: `mock_flask` leaves a stale pygeoapi.flask_app attribute behind
    # after deleting the module from sys.modules, and F_GZIP stays in
    # FORMAT_TYPES once any config has enabled gzip.
    if ('pygeoapi.flask_app' not in sys.modules
            and hasattr(pygeoapi, 'flask_app')):
        delattr(pygeoapi, 'flask_app')

    gzip_mimetype = FORMAT_TYPES.pop(F_GZIP, None)

    try:
        with mock_flask(CONFIG) as client_:
            yield client_
    finally:
        if gzip_mimetype is not None:
            FORMAT_TYPES[F_GZIP] = gzip_mimetype


def test_routes_are_registered(client):
    """Every rule must be on the app's URL map, once."""

    from pygeoapi import flask_app

    rules = [str(rule.rule) for rule in flask_app.APP.url_map.iter_rules()]

    for rule, _ in STYLE_ROUTES:
        assert rules.count(rule) == 1


def test_get_styles(client):
    response = client.get('/styles')
    content = response.json

    assert response.status_code == 200
    assert [style['id'] for style in content['styles']] == [
        'kommune', 'bygning', 'observasjon']
    assert [link['rel'] for link in content['links']] == ['alternate', 'self']


def test_get_style(client):
    response = client.get('/styles/kommune')

    assert response.status_code == 200
    assert response.json == {'id': 'kommune', 'title': 'Kommunegrenser'}


def test_get_style_not_found(client):
    response = client.get('/styles/nope')

    assert response.status_code == 404
    assert response.json['code'] == 'NotFound'


def test_get_style_metadata(client):
    response = client.get('/styles/kommune/metadata')
    content = response.json

    assert response.status_code == 200
    assert content['description'] == 'Stilsett for Bærum og Ålesund'
    assert 'http://localhost:5000/styles/kommune/metadata?f=json' in \
        [link['href'] for link in content['links']]


def test_get_collection_styles(client):
    response = client.get('/collections/obs/styles')

    assert response.status_code == 200
    assert [style['id'] for style in response.json['styles']] == \
        ['observasjon']


def test_get_collection_styles_collection_not_found(client):
    response = client.get('/collections/nope/styles')

    assert response.status_code == 404
    assert response.json['description'] == 'Collection not found'


def test_collections_routes_still_work(client):
    """The path converter on /collections/<path:collection_id> is greedy."""

    assert client.get('/collections').status_code == 200
    assert client.get('/collections/obs').json['id'] == 'obs'


@pytest.mark.parametrize('query,content_type,root', [
    ['?f=sld10', 'application/vnd.ogc.sld+xml;version=1.0.0', 'sld10'],
    ['?f=se11', 'application/vnd.ogc.se+xml;version=1.1.0', 'se11'],
])
def test_get_stylesheet_by_query_param(client, query, content_type, root):
    response = client.get(f'/styles/kommune{query}')

    assert response.status_code == 200
    assert response.headers['Content-Type'].startswith(content_type)
    assert response.text.startswith(f'<?xml version="1.0"?><{root} ')


@pytest.mark.parametrize('accept,content_type,root', [
    ['application/vnd.ogc.sld+xml;version=1.0.0',
     'application/vnd.ogc.sld+xml;version=1.0.0', 'sld10'],
    ['application/vnd.ogc.se+xml;version=1.1.0',
     'application/vnd.ogc.se+xml;version=1.1.0', 'se11'],
])
def test_get_stylesheet_by_accept_header(client, accept, content_type, root):
    response = client.get('/styles/kommune', headers={'accept': accept})

    assert response.status_code == 200
    assert response.headers['Content-Type'].startswith(content_type)
    assert f'<{root} ' in response.text


def test_get_stylesheet_missing_for_style(client):
    response = client.get('/styles/bygning?f=se11')

    assert response.status_code == 404


def test_get_style_html_is_unsupported(client):
    response = client.get('/styles/kommune?f=html')

    assert response.status_code == 415


def test_get_style_invalid_format(client):
    response = client.get('/styles/kommune?f=bogus')

    assert response.status_code == 400
    assert response.json['code'] == 'InvalidParameterValue'


def test_landing_page_advertises_styles(client):
    """The landing page hook is framework independent, but assert it here."""

    rels = [link['rel'] for link in client.get('/').json['links']]

    assert 'http://www.opengis.net/def/rel/ogc/1.0/styles' in rels
