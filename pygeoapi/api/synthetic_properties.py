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
Provider properties that exist only as formatter input.

A provider may put values into `feature['properties']` that are meant for a
custom output formatter rather than for clients: our postgresql_ext provider
with `gml_passthrough` adds `_geometry_gml`, holding the GML the database
produced, which the GML formatter writes out verbatim.

Those keys must not appear in the GeoJSON, JSON-LD or HTML output. A provider
declares them in `synthetic_property_keys`, and the api layer strips them from
every response that is not going to a formatter.
"""

import logging
from typing import Iterable, List

LOGGER = logging.getLogger(__name__)


def strip_synthetic_properties(features: List, provider) -> None:
    """
    Remove a provider's formatter-only property keys, in place

    :param features: `list` of GeoJSON features from a provider query
    :param provider: provider plugin instance

    :returns: `None`
    """

    synthetic: Iterable[str] = getattr(
        provider, 'synthetic_property_keys', ())

    if not synthetic:
        return

    LOGGER.debug(f'Stripping synthetic properties: {list(synthetic)}')

    for feature in features:
        if not isinstance(feature, dict):
            continue

        properties = feature.get('properties')

        if properties:
            for key in synthetic:
                properties.pop(key, None)
