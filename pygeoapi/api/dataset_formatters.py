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
Collection formatters for single items.

`get_collection_items()` negotiates a collection's configured formatters and
runs them; `get_collection_item()` upstream does neither, so a custom format
is only available on the item list and not on an individual feature. These
helpers hold that machinery so the hooks in `pygeoapi/api/itemtypes.py` stay
small.
"""

import logging
from http import HTTPStatus
from typing import Dict, List, Tuple

from pygeoapi.formatter.base import FormatterSerializationError

LOGGER = logging.getLogger(__name__)


def negotiate_dataset_format(request, dataset_formatters: Dict) -> bool:
    """
    Re-negotiate the request format against a collection's formatters

    The same as the block in `get_collection_items()`: the formats a
    collection accepts are not known until its configuration is read, so
    `APIRequest` has to be asked again with them.

    :param request: `APIRequest` instance
    :param dataset_formatters: `dict` of formatters, keyed by name

    :returns: `bool` of whether the requested format is acceptable
    """

    if dataset_formatters:
        LOGGER.debug(f'Dataset formatters: {dataset_formatters}')
        request._format = request._get_format(
            request.get_request_headers(request.headers),
            {v.f: v.mimetype for v in dataset_formatters.values()})

        LOGGER.debug(f'Request format: {request.format}')

    return request.is_valid(dataset_formatters.keys())


def is_formatter_format(request, dataset_formatters: Dict) -> bool:
    """
    Whether the requested format belongs to one of the formatters

    :param request: `APIRequest` instance
    :param dataset_formatters: `dict` of formatters, keyed by name

    :returns: `bool`
    """

    return request.format in [df.f for df in dataset_formatters.values()]


def get_alternate_links(dataset_formatters: Dict, uri: str) -> List[Dict]:
    """
    Get one alternate link per formatter

    :param dataset_formatters: `dict` of formatters, keyed by name
    :param uri: `str` of the URI of the document being linked from

    :returns: `list` of link objects
    """

    return [{
        'type': formatter.mimetype,
        'rel': 'alternate',
        'title': f'This document as {name}',
        'href': f'{uri}?f={formatter.f}'
    } for name, formatter in dataset_formatters.items()]


def write_item(api, request, headers: Dict, dataset: str, p,
               provider_def: Dict, dataset_formatters: Dict,
               feature: Dict) -> Tuple[Dict, int, str]:
    """
    Run the requested formatter over a single feature

    Formatters take a FeatureCollection, so the feature is wrapped in one:
    a formatter written for the item list works on an item unchanged.

    :param api: API object
    :param request: `APIRequest` instance
    :param headers: `dict` of response headers, modified in place
    :param dataset: `str` of collection identifier
    :param p: provider plugin instance
    :param provider_def: `dict` of the provider definition
    :param dataset_formatters: `dict` of formatters, keyed by name
    :param feature: `dict` of the GeoJSON feature to write

    :returns: tuple of headers, status code, content
    """

    formatter = [df for df in dataset_formatters.values()
                 if df.f == request.format][0]

    data = {'type': 'FeatureCollection', 'features': [feature]}

    try:
        content = formatter.write(
            data=data, options={'provider_def': provider_def})
    except FormatterSerializationError:
        msg = 'Error serializing output'
        return api.get_exception(
            HTTPStatus.INTERNAL_SERVER_ERROR, headers, request.format,
            'NoApplicableCode', msg)

    headers['Content-Type'] = formatter.mimetype

    filename = p.filename or f'{dataset}.{formatter.extension}'
    disposition = 'attachment' if formatter.attachment else 'inline'
    headers['Content-Disposition'] = f'{disposition}; filename="{filename}"'

    return headers, HTTPStatus.OK, content
