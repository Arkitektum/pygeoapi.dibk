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
Provider supplied collection schemas.

`pygeoapi.api.get_collection_schema()` derives a JSON Schema from the
provider's field list. A provider that has a schema of its own — read from
disk, or published by an upstream service — can serve that instead by
implementing `get_collection_schema()`.
"""

import logging
from typing import Any, Dict

from pygeoapi import l10n

LOGGER = logging.getLogger(__name__)

#: Keys pygeoapi owns: a provider schema does not get to set its own identity
SCHEMA_IDENTITY_KEYS = ('$schema', '$id', 'title')


def apply_provider_schema(p, schema: Dict[str, Any],
                          resource_config: Dict[str, Any],
                          locale) -> Dict[str, Any]:
    """
    Replace a derived collection schema with the provider's own, if it has one

    The identity keys pygeoapi generated (`$schema`, `$id`, `title`) always
    win, so a provider cannot claim a different `$id` than the endpoint it is
    served from. The collection description is added here for both paths,
    since the derived schema does not carry one.

    :param p: provider plugin instance
    :param schema: `dict` of the schema derived from the provider's fields
    :param resource_config: `dict` of the collection resource definition
    :param locale: locale of the request

    :returns: `dict` of the schema to serve
    """

    get_collection_schema = getattr(p, 'get_collection_schema', None)
    provider_schema = None

    if callable(get_collection_schema):
        LOGGER.debug(f'Provider {p.name} serves its own schema')
        provider_schema = get_collection_schema()

        if provider_schema is None:
            LOGGER.debug('No provider schema; using the derived one')

    identity = {key: schema[key] for key in SCHEMA_IDENTITY_KEYS
                if key in schema}

    description = resource_config.get('description')

    if description:
        identity['description'] = l10n.translate(description, locale)

    return (provider_schema or schema) | identity
