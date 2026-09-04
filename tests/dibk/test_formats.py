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
Regression tests for the style formats this fork adds to FORMAT_TYPES.

See "style formats in FORMAT_TYPES" in FORK.md.
"""

import pytest

from pygeoapi.api import APIRequest
from pygeoapi.formats import FORMAT_TYPES, F_MAPBOX, F_SE11, F_SLD10


class _Args:
    """Minimal stand-in for APIRequest: _get_format only reads _args"""

    def __init__(self, f=None):
        self._args = {'f': f} if f else {}


@pytest.mark.parametrize('format_,mimetype', [
    [F_MAPBOX, 'application/vnd.mapbox.style+json'],
    [F_SE11, 'application/vnd.ogc.se+xml;version=1.1.0'],
    [F_SLD10, 'application/vnd.ogc.sld+xml;version=1.0.0'],
])
def test_style_formats_are_registered(format_, mimetype):
    assert FORMAT_TYPES[format_] == mimetype


@pytest.mark.parametrize('accept,expected', [
    ['application/vnd.mapbox.style+json', F_MAPBOX],
    ['application/vnd.ogc.se+xml;version=1.1.0', F_SE11],
    ['application/vnd.ogc.sld+xml;version=1.0.0', F_SLD10],
    # Media-type parameters are dropped when matching, so any sld+xml
    # version resolves to the single sld+xml entry we register
    ['application/vnd.ogc.sld+xml;version=1.1.0', F_SLD10],
    ['application/vnd.ogc.sld+xml', F_SLD10],
    # A style type ranked below a standard one must not win
    ['application/vnd.ogc.sld+xml;q=0.4,text/html;q=0.9', 'html'],
])
def test_style_formats_negotiate_from_accept(accept, expected):
    assert APIRequest._get_format(_Args(), {'accept': accept}) == expected


@pytest.mark.parametrize('format_', [F_MAPBOX, F_SE11, F_SLD10])
def test_style_formats_negotiate_from_query_param(format_):
    assert APIRequest._get_format(_Args(format_), {}) == format_


def test_standard_formats_unchanged():
    """Our entries must not shadow the formats upstream negotiates."""

    for accept, expected in (('text/html', 'html'),
                             ('application/json', 'json'),
                             ('application/ld+json', 'jsonld')):
        assert APIRequest._get_format(_Args(), {'accept': accept}) == expected
