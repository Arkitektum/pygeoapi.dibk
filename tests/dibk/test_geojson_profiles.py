# =================================================================
#
# Authors: Leif Halvor <leif.halvor@arkitektum.no>
#
# Copyright (c) 2026 Leif Halvor
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
Tests for the GeoJSON profile query parameter on items and single items.

OGC 21-045 (JSON-FG) clause 15 requires `profile` with at least `rfc7946` and
`jsonfg`; OGC API - Features - Part 5 governs its syntax and negotiation. Both
frameworks are driven, as in `test_item_formatters.py`. See "GeoJSON profiles"
in FORK.md.
"""

import json
import sys
from urllib.parse import quote

import pytest

import pygeoapi
from pygeoapi.api import API, conformance
from pygeoapi.api.geojson_profiles import get_profile_formatters
from pygeoapi.formats import FORMAT_TYPES, F_GZIP
from pygeoapi.openapi import get_oas, validate_openapi_document
from pygeoapi.util import yaml_load

from ..util import (get_test_file_path, mock_api_request, mock_flask,
                    mock_starlette)
from .profilestubs import GeoJsonFormatter

CONFIG = 'dibk/pygeoapi-test-config-profiles.yml'

ENDPOINTS = ['/collections/obs/items', '/collections/obs/items/1']

GEOJSON = 'application/geo+json'
ACCEPT_GEOJSON = {'accept': GEOJSON}

LINK_RFC7946 = '<http://www.opengis.net/def/profile/OGC/0/rfc7946>; rel="profile"'  # noqa
LINK_JSONFG = '<http://www.opengis.net/def/profile/OGC/0/jsonfg>; rel="profile"'  # noqa
LINK_JSONFG_PLUS = '<http://www.opengis.net/def/profile/OGC/0/jsonfg-plus>; rel="profile"'  # noqa

JSONFG_IN_WEB_APIS = 'http://www.opengis.net/spec/json-fg-1/1.0/conf/api'


def _clear_stale_app_module(name: str) -> None:
    """`mock_flask` and `mock_starlette` unload the module but leave the
    attribute on the package, which breaks their own reload() next time.
    """

    if f'pygeoapi.{name}' not in sys.modules and hasattr(pygeoapi, name):
        delattr(pygeoapi, name)


@pytest.fixture(scope='module', params=['flask', 'starlette'])
def client(request):
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


@pytest.fixture(params=ENDPOINTS)
def endpoint(request):
    return request.param


@pytest.fixture()
def config():
    with open(get_test_file_path(CONFIG)) as fh:
        return yaml_load(fh)


def _json(response) -> dict:
    """Flask exposes `json` as a property, httpx as a method"""

    payload = response.json

    return payload() if callable(payload) else payload


def _written_by(response) -> str | None:
    """The stub formatter that wrote the body, None for pygeoapi's GeoJSON"""

    return _json(response).get('writtenBy')


# The two abstract tests of the "JSON-FG in Web APIs" conformance class

def test_abstract_test_31_rfc7946(client, endpoint):
    response = client.get(f'{endpoint}?profile=rfc7946',
                          headers=ACCEPT_GEOJSON)

    assert response.status_code == 200
    assert response.headers['Content-Type'] == GEOJSON
    assert response.headers['Link'] == LINK_RFC7946
    assert 'conformsTo' not in _json(response)


def test_abstract_test_32_jsonfg(client, endpoint):
    response = client.get(f'{endpoint}?profile=jsonfg', headers=ACCEPT_GEOJSON)

    assert response.status_code == 200
    assert response.headers['Content-Type'] == GEOJSON
    assert response.headers['Link'] == LINK_JSONFG
    assert _written_by(response) == 'jsonfg'


# Profile negotiation when the request has no f parameter

def test_accept_geojson_without_profile_is_rfc7946(client, endpoint):
    response = client.get(endpoint, headers=ACCEPT_GEOJSON)

    assert response.headers['Content-Type'] == GEOJSON
    assert response.headers['Link'] == LINK_RFC7946
    assert _written_by(response) is None


def test_jsonfg_plus(client, endpoint):
    response = client.get(f'{endpoint}?profile=jsonfg-plus',
                          headers=ACCEPT_GEOJSON)

    assert response.headers['Link'] == LINK_JSONFG_PLUS
    assert _written_by(response) == 'jsonfg-plus'


def test_accept_ranking_json_first_keeps_application_json(client, endpoint):
    response = client.get(endpoint, headers={
        'accept': 'application/json, application/geo+json;q=0.5'})

    assert response.headers['Content-Type'] == 'application/json'
    assert response.headers['Link'] == LINK_RFC7946


def test_profile_without_an_accept_header(client, endpoint):
    response = client.get(f'{endpoint}?profile=jsonfg')

    assert response.headers['Content-Type'] == GEOJSON
    assert _written_by(response) == 'jsonfg'


def test_default_response_names_its_profile(client, endpoint):
    response = client.get(endpoint)

    assert response.headers['Link'] == LINK_RFC7946
    assert _written_by(response) is None


@pytest.mark.parametrize('value', [
    'http://www.opengis.net/def/profile/OGC/0/jsonfg',
    'https://www.opengis.net/def/profile/OGC/0/jsonfg',
    '[ogc-profile:jsonfg]'
])
def test_profile_uri_and_curie(client, value):
    response = client.get(f'/collections/obs/items?profile={quote(value)}')

    assert response.headers['Link'] == LINK_JSONFG
    assert _written_by(response) == 'jsonfg'


@pytest.mark.parametrize('value, written_by, link', [
    ('bogus,jsonfg-plus,jsonfg', 'jsonfg-plus', LINK_JSONFG_PLUS),
    ('rfc7946,jsonfg', None, LINK_RFC7946)
])
def test_first_supported_profile_in_the_list_wins(client, value, written_by,
                                                  link):
    response = client.get(f'/collections/obs/items?profile={value}')

    assert response.headers['Link'] == link
    assert _written_by(response) == written_by


def test_unknown_profile_falls_back_to_rfc7946(client, endpoint):
    response = client.get(f'{endpoint}?profile=bogus')

    assert response.status_code == 200
    assert response.headers['Link'] == LINK_RFC7946
    assert _written_by(response) is None


def test_head_request(client, endpoint):
    response = client.head(f'{endpoint}?profile=jsonfg',
                           headers=ACCEPT_GEOJSON)

    assert response.status_code == 200
    assert response.headers['Link'] == LINK_JSONFG


# An explicit f parameter wins over profile

def test_f_json_wins_over_profile(client, endpoint):
    response = client.get(f'{endpoint}?f=json&profile=jsonfg')

    assert response.headers['Link'] == LINK_RFC7946
    assert _written_by(response) is None


def test_f_jsonfg_wins_over_profile(client, endpoint):
    response = client.get(f'{endpoint}?f=jsonfg&profile=rfc7946')

    assert response.headers['Link'] == LINK_JSONFG
    assert _written_by(response) == 'jsonfg'


def test_f_serves_the_first_declared_profile(client, endpoint):
    response = client.get(f'{endpoint}?f=jsonfg-plus')

    assert response.headers['Link'] == LINK_JSONFG_PLUS


@pytest.mark.parametrize('format_', ['html', 'inlinegml'])
def test_no_profile_link_outside_geojson(client, endpoint, format_):
    response = client.get(f'{endpoint}?f={format_}&profile=jsonfg')

    assert response.status_code == 200
    assert 'Link' not in response.headers


def test_error_responses_name_no_profile(client):
    response = client.get('/collections/obs/items/999?profile=jsonfg')

    assert response.status_code == 400
    assert 'Link' not in response.headers


# What the formatter chosen through profile gets, and the links around it

def test_formatter_chosen_by_profile_gets_the_synthetic_property(client,
                                                                 endpoint):
    """Stripping runs on the format, so it has to be settled first."""

    response = client.get(f'{endpoint}?profile=jsonfg')

    assert _json(response)['sawSyntheticProperty'] is True


def test_alternate_links_keep_f_jsonfg(client, endpoint):
    """The NAP site and contract-diff find JSON-FG through these links."""

    links = _json(client.get(endpoint))['links']
    alternates = [link['href'] for link in links if link['rel'] == 'alternate']

    assert any(href.endswith('?f=jsonfg') for href in alternates)


def test_paging_links_carry_the_format_profile_chose(client):
    response = client.get('/collections/obs/items?offset=1&profile=jsonfg')
    links = _json(response)['links']
    prev = [link['href'] for link in links if link['rel'] == 'prev']

    assert prev == [
        'http://localhost:5000/collections/obs/items'
        '?f=jsonfg&offset=0&profile=jsonfg'
    ]


# Collections without a profile-declaring formatter

def test_collection_without_jsonfg_answers_rfc7946(client):
    response = client.get('/collections/plain/items?profile=jsonfg',
                          headers=ACCEPT_GEOJSON)

    assert response.status_code == 200
    assert response.headers['Content-Type'] == GEOJSON
    assert response.headers['Link'] == LINK_RFC7946


def test_geojson_formatter_mimetype_does_not_win_negotiation(client):
    response = client.get('/collections/legacy/items', headers=ACCEPT_GEOJSON)

    assert response.headers['Link'] == LINK_RFC7946
    assert _written_by(response) is None


def test_formatter_without_profiles_serves_no_profile(client):
    response = client.get('/collections/legacy/items?profile=jsonfg')

    assert response.headers['Link'] == LINK_RFC7946
    assert _written_by(response) is None


def test_formatter_without_profiles_still_answers_f(client):
    response = client.get('/collections/legacy/items?f=legacyfg')

    assert _written_by(response) == 'legacyfg'
    assert 'Link' not in response.headers


# A profile formatter with a media type of its own

LEGACY_ENDPOINTS = ['/collections/legacytype/items',
                    '/collections/legacytype/items/1']
LEGACY_TYPE = 'application/vnd.ogc.fg+json'


@pytest.mark.parametrize('path', LEGACY_ENDPOINTS)
def test_f_names_the_profile_of_its_own_media_type(client, path):
    response = client.get(f'{path}?f=jsonfg')

    assert response.headers['Content-Type'] == LEGACY_TYPE
    assert response.headers['Link'] == LINK_JSONFG
    assert _written_by(response) == 'jsonfg'


@pytest.mark.parametrize('path', LEGACY_ENDPOINTS)
def test_accept_of_its_own_media_type_names_the_profile(client, path):
    response = client.get(path, headers={'accept': LEGACY_TYPE})

    assert response.headers['Content-Type'] == LEGACY_TYPE
    assert response.headers['Link'] == LINK_JSONFG
    assert _written_by(response) == 'jsonfg'


@pytest.mark.parametrize('path', LEGACY_ENDPOINTS)
def test_abstract_test_32_with_its_own_media_type(client, path):
    """OGC 21-045 A.8.2 asserts application/geo+json, whatever the
    formatter calls its media type.
    """

    response = client.get(f'{path}?profile=jsonfg', headers=ACCEPT_GEOJSON)

    assert response.headers['Content-Type'] == GEOJSON
    assert response.headers['Link'] == LINK_JSONFG
    assert _written_by(response) == 'jsonfg'


def test_alternate_link_keeps_its_own_media_type(client):
    """GDAL and QGIS follow the last items link typed application/geo+json."""

    response = client.get('/collections/legacytype/items?profile=jsonfg')
    alternates = [link for link in _json(response)['links']
                  if link['href'].endswith('?f=jsonfg&profile=jsonfg')]

    assert [link['type'] for link in alternates] == [LEGACY_TYPE]


def test_profile_is_not_a_property_filter(client):
    response = client.get(
        '/collections/echo/items?profile=rfc7946&kommune=3201')
    properties = _json(response)['features'][0]['properties']

    assert properties['filters'] == [['kommune', '3201']]


def test_default_profile_wins_over_a_satisfied_one():
    """Whichever order the collection lists its formatters in."""

    plus = GeoJsonFormatter({'f': 'jsonfg-plus',
                             'profiles': ['jsonfg-plus', 'jsonfg']})
    jsonfg = GeoJsonFormatter({'f': 'jsonfg', 'profiles': ['jsonfg']})

    formatters = get_profile_formatters({'jsonfg-plus': plus,
                                         'jsonfg': jsonfg})

    assert formatters == {'jsonfg-plus': plus, 'jsonfg': jsonfg}


# Conformance

def _conforms_to(cfg: dict) -> list:
    _, _, body = conformance(API(cfg, {}), mock_api_request())

    return json.loads(body)['conformsTo']


def test_conformance_declares_jsonfg_in_web_apis(config):
    assert JSONFG_IN_WEB_APIS in _conforms_to(config)


def test_conformance_without_a_jsonfg_profile_formatter(config):
    for collection in ('obs', 'legacytype'):
        del config['resources'][collection]['formatters']

    assert JSONFG_IN_WEB_APIS not in _conforms_to(config)


def test_conformance_with_only_a_legacy_media_type(config):
    del config['resources']['obs']['formatters']

    assert JSONFG_IN_WEB_APIS in _conforms_to(config)


# OpenAPI

@pytest.fixture()
def oas(config):
    return get_oas(config, fail_on_invalid_collection=False)


def _profile_parameter(oas: dict, path: str) -> dict:
    parameters = oas['paths'][path]['get']['parameters']
    matches = [parameter for parameter in parameters
               if parameter.get('name') == 'profile']

    assert len(matches) == 1

    return matches[0]


@pytest.mark.parametrize('path', [
    '/collections/obs/items', '/collections/obs/items/{featureId}'
])
def test_openapi_declares_the_profile_parameter(oas, path):
    parameter = _profile_parameter(oas, path)

    assert parameter['in'] == 'query'
    assert parameter['required'] is False
    assert parameter['schema'] == {
        'type': 'array', 'items': {'type': 'string'}}
    assert parameter['style'] == 'form'
    assert parameter['explode'] is False


def test_openapi_lists_the_profiles_a_collection_supports(oas):
    obs = _profile_parameter(oas, '/collections/obs/items')['description']
    plain = _profile_parameter(oas, '/collections/plain/items')['description']

    assert all(id_ in obs for id_ in ('rfc7946', 'jsonfg', 'jsonfg-plus'))
    assert 'rfc7946' in plain and 'jsonfg' not in plain


def test_openapi_document_validates(oas):
    assert validate_openapi_document(oas)
