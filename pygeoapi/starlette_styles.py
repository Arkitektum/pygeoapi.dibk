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
Starlette routes for OGC API - Styles.

The handlers live here rather than in `pygeoapi/starlette_app.py` so that
registering them costs that file two lines: the import of `style_routes` and
one unpack in `api_routes`. `execute_from_starlette` is imported inside each
handler because `pygeoapi.starlette_app` imports this module, and it is that
function which needs the fully initialised app module.
"""

import logging

from starlette.requests import Request
from starlette.responses import Response
from starlette.routing import Route

import pygeoapi.api.styles as styles_api

LOGGER = logging.getLogger(__name__)


async def get_styles(request: Request) -> Response:
    """
    OGC API - Styles styles endpoint

    :param request: Starlette Request instance

    :returns: Starlette HTTP Response
    """

    from pygeoapi.starlette_app import execute_from_starlette

    return await execute_from_starlette(styles_api.get_styles, request)


async def get_style(request: Request, style_id: str | None = None) -> Response:
    """
    OGC API - Styles style endpoint

    :param request: Starlette Request instance
    :param style_id: style identifier

    :returns: Starlette HTTP Response
    """

    from pygeoapi.starlette_app import execute_from_starlette

    if 'style_id' in request.path_params:
        style_id = request.path_params['style_id']

    return await execute_from_starlette(
        styles_api.get_style, request, style_id)


async def get_style_metadata(request: Request,
                             style_id: str | None = None) -> Response:
    """
    OGC API - Styles style metadata endpoint

    :param request: Starlette Request instance
    :param style_id: style identifier

    :returns: Starlette HTTP Response
    """

    from pygeoapi.starlette_app import execute_from_starlette

    if 'style_id' in request.path_params:
        style_id = request.path_params['style_id']

    return await execute_from_starlette(
        styles_api.get_style_metadata, request, style_id)


async def get_collection_styles(request: Request,
                                collection_id: str | None = None) -> Response:
    """
    OGC API - Styles collection styles endpoint

    :param request: Starlette Request instance
    :param collection_id: collection identifier

    :returns: Starlette HTTP Response
    """

    from pygeoapi.starlette_app import execute_from_starlette

    if 'collection_id' in request.path_params:
        collection_id = request.path_params['collection_id']

    return await execute_from_starlette(
        styles_api.get_collection_styles, request, collection_id)


#: Must be unpacked into `api_routes` before the `/collections` catch-all
style_routes = [
    Route('/styles', get_styles),
    Route('/styles/{style_id}/metadata', get_style_metadata),
    Route('/styles/{style_id}', get_style),
    Route('/collections/{collection_id:path}/styles', get_collection_styles)
]
