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
Stubs for the synthetic property and formatter tests.

`SyntheticProvider` returns a feature carrying `_geometry_gml`, a property
that exists only as input for a formatter, the way our postgresql_ext provider
does with `gml_passthrough`. The two formatters differ only in whether they
are attachments.
"""

from pygeoapi.formatter.base import BaseFormatter
from pygeoapi.provider.base import BaseProvider

SYNTHETIC_KEY = '_geometry_gml'

GML = '<gml:Point><gml:pos>10.7 59.9</gml:pos></gml:Point>'


class SyntheticProvider(BaseProvider):
    """Feature provider with a formatter-only property"""

    #: Read by pygeoapi.api.synthetic_properties.strip_synthetic_properties
    synthetic_property_keys = (SYNTHETIC_KEY,)

    def __init__(self, provider_def):
        super().__init__(provider_def)
        # Providers serving a single file set this; the api layer uses it as
        # the download filename
        self.filename = provider_def.get('filename')
        self._fields = {
            'id': {'type': 'string'},
            'stedsnavn': {'type': 'string'}
        }

    def get_fields(self):
        return self._fields

    def query(self, **kwargs):
        return {
            'type': 'FeatureCollection',
            'numberMatched': 1,
            'numberReturned': 1,
            'features': [{
                'type': 'Feature',
                'id': '1',
                'geometry': {'type': 'Point', 'coordinates': [10.7, 59.9]},
                'properties': {
                    'stedsnavn': 'Bærum',
                    SYNTHETIC_KEY: GML
                }
            }]
        }


class _GmlFormatter(BaseFormatter):
    """Writes the GML the provider passed through

    `name` has to equal `f`: `get_dataset_formatters()` keys the formatters by
    name and `APIRequest.is_valid()` matches `?f=` against those keys.
    """

    #: Overridden per subclass
    format_name = None
    is_attachment = False

    def __init__(self, formatter_def: dict):
        super().__init__({**formatter_def,
                          'name': self.format_name,
                          'attachment': self.is_attachment})
        self.f = self.format_name
        self.extension = 'gml'
        self.mimetype = 'application/gml+xml; version=3.2'

    def write(self, options: dict = {}, data: dict | None = None) -> str:
        features = (data or {}).get('features', [])
        members = [feature['properties'].get(SYNTHETIC_KEY, '')
                   for feature in features]

        return f"<wfs:FeatureCollection>{''.join(members)}"\
               '</wfs:FeatureCollection>'


class InlineFormatter(_GmlFormatter):
    """Rendered in the browser rather than downloaded"""

    format_name = 'inlinegml'


class AttachmentFormatter(_GmlFormatter):
    """Same output, but downloaded"""

    format_name = 'attachmentgml'
    is_attachment = True
