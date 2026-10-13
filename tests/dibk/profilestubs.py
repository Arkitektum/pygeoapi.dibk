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
Stubs for the GeoJSON profile tests.

`GeoJsonFormatter` stands in for `pygeoapi_formatter_jsonfg.JsonFgFormatter`,
which needs GDAL. It takes `profiles` from its configuration so one class can
play every variant, including a release that predates the attribute.
"""

import json

from pygeoapi.formatter.base import BaseFormatter

from .syntheticprovider import SYNTHETIC_KEY, SyntheticProvider

JSONFG_CORE = 'http://www.opengis.net/spec/json-fg-1/1.0/conf/core'


class GeoJsonFormatter(BaseFormatter):
    """A JSON-FG formatter that reports what it was given"""

    def __init__(self, formatter_def: dict):
        f = formatter_def['f']
        super().__init__({'name': f})
        self.f = f
        self.mimetype = formatter_def.get('mimetype', 'application/geo+json')
        self.extension = 'json'

        if 'profiles' in formatter_def:
            self.profiles = formatter_def['profiles']

    def write(self, options: dict = {}, data: dict | None = None) -> str:
        data = data or {}
        features = data.get('features', [])

        return json.dumps({
            'type': 'FeatureCollection',
            'conformsTo': [JSONFG_CORE],
            'writtenBy': self.f,
            'sawSyntheticProperty': any(
                SYNTHETIC_KEY in feature['properties']
                for feature in features),
            'links': data.get('links', [])
        })


class FilterEchoProvider(SyntheticProvider):
    """Returns the property filters it was queried with"""

    def query(self, **kwargs):
        content = super().query(**kwargs)
        content['features'][0]['properties']['filters'] = [
            list(filter_) for filter_ in kwargs.get('properties', [])]

        return content
