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
Regression tests for the style links this fork adds to `gen_collection()`.

See "Style links on collections" in FORK.md.
"""

import json
from copy import deepcopy

import pytest

from pygeoapi.api import API, describe_collections
from pygeoapi.api.collection import gen_collection
from pygeoapi.api.styles import STYLES_RELTYPE
from pygeoapi.util import yaml_load

from ..util import get_test_file_path, mock_api_request


@pytest.fixture()
def config_with_styles():
    filename = 'dibk/pygeoapi-test-config-styles.yml'
    with open(get_test_file_path(filename)) as fh:
        return yaml_load(fh)


def _style_links(config: dict, dataset: str = 'obs') -> list:
    api = API(config, {})
    request = mock_api_request()
    data = gen_collection(api, request, dataset, request.locale)

    return [link for link in data['links'] if link['rel'] == STYLES_RELTYPE]


def test_collection_style_links(config_with_styles):
    links = _style_links(config_with_styles)

    assert len(links) == 2

    json_link, html_link = links

    assert json_link['type'] == 'application/json'
    assert json_link['title'] == 'Styles to render data in maps as JSON'
    assert json_link['href'] == \
        'http://localhost:5000/collections/obs/styles?f=json'

    assert html_link['type'] == 'text/html'
    assert html_link['title'] == 'Styles to render data in maps as HTML'
    assert html_link['href'] == \
        'http://localhost:5000/collections/obs/styles'


def test_no_style_links_without_style_provider(config_with_styles):
    """A collection without a style provider must not get the links.

    This is also what keeps the upstream collection tests green: the stock
    test configuration has no style providers, so nothing is added there.
    """

    cfg = deepcopy(config_with_styles)
    cfg['resources']['obs']['providers'] = [
        provider for provider in cfg['resources']['obs']['providers']
        if provider['type'] != 'style'
    ]

    assert _style_links(cfg) == []


def test_style_links_in_collections_list(config_with_styles):
    """`/collections` builds each entry through gen_collection() too."""

    api = API(config_with_styles, {})
    _, status, content = describe_collections(api, mock_api_request())
    collections = json.loads(content)['collections']

    obs = [c for c in collections if c['id'] == 'obs'][0]
    links = [link for link in obs['links'] if link['rel'] == STYLES_RELTYPE]

    assert int(status) == 200
    assert len(links) == 2
