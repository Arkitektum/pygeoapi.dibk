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
Regression tests for the OGC API - Styles module this fork adds.

See "OGC API - Styles" in FORK.md.
"""

import json
from copy import deepcopy

import pytest

from pygeoapi.api import API, all_apis, conformance, styles
from pygeoapi.openapi import get_oas, validate_openapi_document
from pygeoapi.util import yaml_load

from ..util import get_test_file_path, mock_api_request

STYLE_PROVIDER = {
    'type': 'style',
    'name': 'Dummy',
    'styles': [{'id': 'kommune', 'stylesheets': [{'type': 'sld10'}]}]
}


@pytest.fixture()
def config():
    with open(get_test_file_path('pygeoapi-test-config.yml')) as fh:
        return yaml_load(fh)


@pytest.fixture()
def config_with_styles(config):
    """Config with a global style resource and a collection style provider"""

    cfg = deepcopy(config)
    cfg['resources']['styles'] = {
        'type': 'style',
        'provider': deepcopy(STYLE_PROVIDER)
    }
    cfg['resources']['obs']['providers'].append(deepcopy(STYLE_PROVIDER))

    return cfg


def _local_refs(node, acc=None):
    """Collect every document-local $ref in an OpenAPI document"""

    acc = [] if acc is None else acc

    if isinstance(node, dict):
        for key, value in node.items():
            if key == '$ref' and isinstance(value, str):
                if value.startswith('#/'):
                    acc.append(value)
            else:
                _local_refs(value, acc)
    elif isinstance(node, list):
        for value in node:
            _local_refs(value, acc)

    return acc


def _resolves(document, ref):
    node = document

    for part in ref.lstrip('#/').split('/'):
        if not isinstance(node, dict) or part not in node:
            return False
        node = node[part]

    return True


# Registration in all_apis()

def test_styles_is_registered():
    """openapi.py and conformance() both dispatch through all_apis()"""

    assert all_apis().get('style') is styles


def test_conformance_classes_name_exists():
    """conformance() looks up CONFORMANCE_CLASSES on the module"""

    assert styles.CONFORMANCE_CLASSES == styles.CONFORMANCE_CLASSES_STYLES
    assert len(styles.CONFORMANCE_CLASSES) == 3


def test_conformance_lists_styles_classes(config_with_styles):
    api = API(config_with_styles, {})
    _, status, body = conformance(api, mock_api_request())

    conforms_to = json.loads(body)['conformsTo']

    assert int(status) == 200
    for conformance_class in styles.CONFORMANCE_CLASSES:
        assert conformance_class in conforms_to


def test_conformance_without_styles(config):
    api = API(config, {})
    _, _, body = conformance(api, mock_api_request())

    conforms_to = json.loads(body)['conformsTo']

    for conformance_class in styles.CONFORMANCE_CLASSES:
        assert conformance_class not in conforms_to


# OpenAPI fragment

def test_get_oas_30_is_empty_without_style_providers(config):
    tags, fragment = styles.get_oas_30(config, 'en-US')

    assert tags == []
    assert fragment['paths'] == {}


def test_get_oas_30_paths(config_with_styles):
    _, fragment = styles.get_oas_30(config_with_styles, 'en-US')

    assert sorted(fragment['paths']) == [
        '/collections/{collectionId}/styles',
        '/styles',
        '/styles/{styleId}',
        '/styles/{styleId}/metadata'
    ]


def test_get_oas_30_declares_the_components_it_refs(config_with_styles):
    """Every local $ref in our fragment must be one we also define."""

    _, fragment = styles.get_oas_30(config_with_styles, 'en-US')

    defined = {f'#/components/{group}/{name}'
               for group, defs in fragment['components'].items()
               for name in defs}

    for ref in _local_refs(fragment['paths']):
        assert ref in defined, f'{ref} is not defined by the fragment'


def test_get_oas_30_collection_enum(config_with_styles):
    _, fragment = styles.get_oas_30(config_with_styles, 'en-US')
    parameter = fragment['components']['parameters']['collectionIdStyles']

    assert parameter['name'] == 'collectionId'
    assert parameter['schema']['enum'] == ['obs']


def test_get_oas_30_omits_empty_collection_enum(config):
    """An empty enum is an invalid schema, so it must not be emitted."""

    cfg = deepcopy(config)
    cfg['resources']['styles'] = {
        'type': 'style',
        'provider': deepcopy(STYLE_PROVIDER)
    }

    _, fragment = styles.get_oas_30(cfg, 'en-US')
    parameter = fragment['components']['parameters']['collectionIdStyles']

    assert 'enum' not in parameter['schema']


# Merged into the served document by our openapi.py hook

def test_get_oas_merges_style_components(config_with_styles):
    oas = get_oas(config_with_styles, fail_on_invalid_collection=False)

    assert 'styleId' in oas['components']['parameters']
    assert 'collectionIdStyles' in oas['components']['parameters']
    assert 'styles' in oas['components']['schemas']
    assert 'stylemetadata' in oas['components']['schemas']
    assert {'name': 'styles'} in oas['tags']


def test_get_oas_has_no_dangling_refs(config_with_styles):
    oas = get_oas(config_with_styles, fail_on_invalid_collection=False)

    broken = sorted({ref for ref in set(_local_refs(oas))
                     if not _resolves(oas, ref)})

    assert broken == []


def test_get_oas_validates(config_with_styles):
    oas = get_oas(config_with_styles, fail_on_invalid_collection=False)

    assert validate_openapi_document(oas)


def test_get_oas_without_styles_is_unchanged(config):
    oas = get_oas(config, fail_on_invalid_collection=False)

    assert [path for path in oas['paths'] if 'styles' in path] == []
    assert 'styleId' not in oas['components']['parameters']
    assert {'name': 'styles'} not in oas['tags']
