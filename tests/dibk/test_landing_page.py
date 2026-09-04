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
Regression tests for the styles additions to `landing_page()`.

See "Styles on the landing page" in FORK.md.
"""

import json
from copy import deepcopy
from unittest import mock

import pytest

from pygeoapi.api import API, landing_page
from pygeoapi.util import yaml_load

from ..util import get_test_file_path, mock_api_request

STYLES_REL = 'http://www.opengis.net/def/rel/ogc/1.0/styles'


@pytest.fixture()
def config_with_styles():
    filename = 'dibk/pygeoapi-test-config-styles.yml'
    with open(get_test_file_path(filename)) as fh:
        return yaml_load(fh)


@pytest.fixture()
def config_without_styles():
    with open(get_test_file_path('pygeoapi-test-config.yml')) as fh:
        return yaml_load(fh)


def _render_data(config: dict) -> dict:
    """Return the template data `landing_page()` builds for HTML output"""

    api = API(config, {})
    request = mock_api_request({'f': 'html'})

    with mock.patch('pygeoapi.api.render_j2_template',
                    return_value='') as render:
        landing_page(api, request)

    return render.call_args[0][3]


def _links(config: dict) -> list:
    api = API(config, {})
    _, status, content = landing_page(api, mock_api_request())

    assert int(status) == 200

    return json.loads(content)['links']


def test_landing_page_has_styles_link(config_with_styles):
    links = _links(config_with_styles)
    styles_links = [link for link in links if link['rel'] == STYLES_REL]

    assert len(styles_links) == 1
    assert styles_links[0]['href'].endswith('/styles?f=json')
    assert styles_links[0]['type'] == 'application/json'
    assert styles_links[0]['title'] == 'Styles'


def test_landing_page_omits_styles_link_without_styles(config_without_styles):
    """Nothing configured to serve styles: do not advertise the endpoint.

    This also keeps tests/api/test_api.py::test_root green, which asserts an
    exact link count for the stock test configuration.
    """

    links = _links(config_without_styles)

    assert [link for link in links if link['rel'] == STYLES_REL] == []


def test_html_flag_for_global_style_resource(config_with_styles):
    cfg = deepcopy(config_with_styles)

    for key, value in cfg['resources'].items():
        if value['type'] == 'collection':
            value['providers'] = [provider for provider in value['providers']
                                  if provider['type'] != 'style']

    assert _render_data(cfg)['styles'] is True


def test_html_flag_for_collection_style_provider(config_with_styles):
    cfg = deepcopy(config_with_styles)
    del cfg['resources']['styles']

    assert _render_data(cfg)['styles'] is True


def test_html_flag_false_without_styles(config_without_styles):
    """Nothing style-related configured: the template must not show it."""

    assert _render_data(config_without_styles)['styles'] is False
