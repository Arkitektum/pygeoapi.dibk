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
Feature provider stubs for the provider supplied schema tests.

`SchemaProvider` serves a schema of its own, the way a provider reading JSON
Schema files from disk would. `FieldsOnlyProvider` does not, so pygeoapi
derives the schema from its fields as before.
"""

from pygeoapi.provider.base import BaseProvider

FIELDS = {
    'id': {'type': 'string'},
    'stedsnavn': {'type': 'string'},
    'hoyde': {'type': 'float'},
    'registrert': {'type': 'string', 'format': 'date-time'}
}


class FieldsOnlyProvider(BaseProvider):
    """Provider without a schema of its own"""

    def __init__(self, provider_def):
        super().__init__(provider_def)
        self._fields = dict(FIELDS)

    def get_fields(self):
        return self._fields


class SchemaProvider(FieldsOnlyProvider):
    """Provider serving a schema it holds itself"""

    #: Set to False to exercise the fallback when a provider has the method
    #: but no schema for the collection
    has_schema = True

    def get_collection_schema(self):
        if not self.has_schema:
            return None

        return {
            '$schema': 'http://json-schema.org/draft/2020-12/schema',
            '$id': 'https://example.org/schemas/sted.json',
            'title': 'Sted fra fil',
            'description': 'Skjema lest fra disk',
            'type': 'object',
            'required': ['stedsnavn'],
            'properties': {
                'stedsnavn': {
                    'type': 'string',
                    'description': 'Navn på stedet, f.eks. Bærum'
                }
            }
        }
