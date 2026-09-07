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
Regression tests for provider supplied collection schemas.

See "Provider supplied collection schemas" in FORK.md.
"""

import json
from copy import deepcopy

import pytest

from pygeoapi.api import API, get_collection_schema
from pygeoapi.util import yaml_load

from ..util import get_test_file_path, mock_api_request
from .schemaprovider import SchemaProvider

SCHEMA_PROVIDER = 'tests.dibk.schemaprovider.SchemaProvider'
FIELDS_ONLY_PROVIDER = 'tests.dibk.schemaprovider.FieldsOnlyProvider'


@pytest.fixture()
def config():
    with open(get_test_file_path('pygeoapi-test-config.yml')) as fh:
        return yaml_load(fh)


def _config_with_provider(config: dict, name: str) -> dict:
    """Replace the obs feature provider with one of our stubs"""

    cfg = deepcopy(config)
    cfg['resources']['obs']['providers'] = [{
        'type': 'feature',
        'name': name,
        'data': 'tests/data/obs.csv',
        'id_field': 'id',
        'time_field': 'registrert'
    }]

    return cfg


def _schema(config: dict, dataset: str = 'obs') -> dict:
    headers, status, content = get_collection_schema(
        API(config, {}), mock_api_request(), dataset)

    assert int(status) == 200
    assert headers['Content-Type'] == 'application/schema+json'

    return json.loads(content)


def test_provider_schema_is_served(config):
    schema = _schema(_config_with_provider(config, SCHEMA_PROVIDER))

    assert schema['required'] == ['stedsnavn']
    assert list(schema['properties']) == ['stedsnavn']
    assert schema['properties']['stedsnavn']['description'] == \
        'Navn på stedet, f.eks. Bærum'


def test_provider_schema_cannot_override_identity(config):
    """pygeoapi owns $schema, $id and title: the endpoint is the identity."""

    schema = _schema(_config_with_provider(config, SCHEMA_PROVIDER))

    assert schema['$schema'] == 'http://json-schema.org/draft/2019-09/schema'
    assert schema['$id'] == \
        'http://localhost:5000/collections/obs/schema'
    assert schema['title'] == 'Observations'


def test_provider_schema_description_comes_from_config(config):
    """The provider's own description is replaced by the collection's."""

    schema = _schema(_config_with_provider(config, SCHEMA_PROVIDER))

    assert schema['description'] == 'My cool observations'


def test_derived_schema_gains_description(config):
    """The derived schema carries the description too, which it did not."""

    schema = _schema(_config_with_provider(config, FIELDS_ONLY_PROVIDER))

    assert schema['description'] == 'My cool observations'


def test_provider_without_method_is_derived_as_before(config):
    schema = _schema(_config_with_provider(config, FIELDS_ONLY_PROVIDER))

    assert schema['type'] == 'object'
    assert schema['properties']['geometry'] == {
        'format': 'geometry-any',
        'x-ogc-role': 'primary-geometry'
    }
    assert schema['properties']['id']['x-ogc-role'] == 'id'
    assert schema['properties']['registrert']['x-ogc-role'] == \
        'primary-instant'
    # float is mapped to the JSON Schema type
    assert schema['properties']['hoyde']['type'] == 'number'


def test_provider_returning_none_falls_back(config, monkeypatch):
    """A provider with the method but no schema for this collection."""

    monkeypatch.setattr(SchemaProvider, 'has_schema', False)

    schema = _schema(_config_with_provider(config, SCHEMA_PROVIDER))

    assert schema['properties']['id']['x-ogc-role'] == 'id'
    assert 'geometry' in schema['properties']


def test_configured_properties_still_filter_derived_fields(config):
    """A provider `properties` whitelist must keep working."""

    cfg = _config_with_provider(config, FIELDS_ONLY_PROVIDER)
    cfg['resources']['obs']['providers'][0]['properties'] = ['stedsnavn']

    schema = _schema(cfg)

    assert 'stedsnavn' in schema['properties']
    assert 'hoyde' not in schema['properties']
