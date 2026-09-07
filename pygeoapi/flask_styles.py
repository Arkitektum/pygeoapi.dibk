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
Flask routes for OGC API - Styles.

The Starlette twin of this module is `pygeoapi/starlette_styles.py`. As there,
the handlers live outside the app module so that registering them costs
`pygeoapi/flask_app.py` two lines, and `execute_from_flask` is imported inside
each handler because `flask_app` imports this module at its top.

Routes are added with `add_url_rule` rather than `@BLUEPRINT.route`, since the
blueprint is created in `flask_app` and this module must not import it.
"""

import logging

from flask import Blueprint, Response, request

import pygeoapi.api.styles as styles_api

LOGGER = logging.getLogger(__name__)


def get_styles() -> Response:
    """
    OGC API - Styles styles endpoint

    :returns: HTTP response
    """

    from pygeoapi.flask_app import execute_from_flask

    return execute_from_flask(styles_api.get_styles, request)


def get_style(style_id: str) -> Response:
    """
    OGC API - Styles style endpoint

    :param style_id: style identifier

    :returns: HTTP response
    """

    from pygeoapi.flask_app import execute_from_flask

    return execute_from_flask(styles_api.get_style, request, style_id)


def get_style_metadata(style_id: str) -> Response:
    """
    OGC API - Styles style metadata endpoint

    :param style_id: style identifier

    :returns: HTTP response
    """

    from pygeoapi.flask_app import execute_from_flask

    return execute_from_flask(
        styles_api.get_style_metadata, request, style_id)


def get_collection_styles(collection_id: str | None = None) -> Response:
    """
    OGC API - Styles collection styles endpoint

    :param collection_id: collection identifier

    :returns: HTTP response
    """

    from pygeoapi.flask_app import execute_from_flask

    return execute_from_flask(
        styles_api.get_collection_styles, request, collection_id)


#: Rule and view function for each endpoint, in the same order as the
#: Starlette routes
STYLE_ROUTES = (
    ('/styles', get_styles),
    ('/styles/<style_id>/metadata', get_style_metadata),
    ('/styles/<style_id>', get_style),
    ('/collections/<path:collection_id>/styles', get_collection_styles)
)


def register_style_routes(blueprint: Blueprint) -> None:
    """
    Add the OGC API - Styles rules to a blueprint

    Must be called before the blueprint is registered on the app: Flask
    rejects rules added to a blueprint that is already registered.

    :param blueprint: `Blueprint` to add the rules to

    :returns: `None`
    """

    for rule, view_func in STYLE_ROUTES:
        LOGGER.debug(f'Adding style route {rule}')
        blueprint.add_url_rule(rule, view_func=view_func)
