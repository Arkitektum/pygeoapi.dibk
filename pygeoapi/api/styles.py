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

"""OGC API - Styles implementation"""

import logging
from http import HTTPStatus
from typing import Dict, List, Tuple, Any

from pygeoapi import l10n
from pygeoapi.plugin import load_plugin
from pygeoapi.util import filter_dict_by_key_value, to_json
from pygeoapi.provider import filter_providers_by_type
from pygeoapi.provider.base import ProviderGenericError
from pygeoapi.formats import FORMAT_TYPES, F_HTML, F_JSON
from pygeoapi.openapi import OPENAPI_YAML

from . import APIRequest, API, SYSTEM_LOCALE

LOGGER = logging.getLogger(__name__)

CONFORMANCE_CLASSES_STYLES = [
    'http://www.opengis.net/spec/ogcapi-styles-1/0.0/conf/core',
    'http://www.opengis.net/spec/ogcapi-styles-1/0.0/conf/sld-10',
    'http://www.opengis.net/spec/ogcapi-styles-1/0.0/conf/sld-11'
]

#: Name `pygeoapi.api.conformance()` looks up once we are in `all_apis()`
CONFORMANCE_CLASSES = CONFORMANCE_CLASSES_STYLES

STYLES_RELTYPE = 'http://www.opengis.net/def/rel/ogc/1.0/styles'


class BaseStyleProvider():
    """Interface a style provider plugin is expected to implement"""

    def get_styles(self) -> Dict[str, Any]:
        raise NotImplementedError()

    def get_style(self, style_id: str) -> Dict[str, Any] | None:
        raise NotImplementedError()

    def get_style_metadata(self, style_id: str) -> Dict[str, Any] | None:
        raise NotImplementedError()

    def get_style_definition(self, style_id: str, format_: str) -> str | None:
        raise NotImplementedError()

    def get_style_preview(self, style_id: str):
        raise NotImplementedError()


def get_styles(api: API, request: APIRequest) -> Tuple[Dict, int, str]:
    """
    Provide styles of all style providers

    :param api: API object
    :param request: APIRequest instance with query params

    :returns: tuple of headers, status code, content
    """

    headers = request.get_response_headers(SYSTEM_LOCALE, **api.api_headers)

    provider_defs = _get_provider_defs(api)
    server_url = api.config['server']['url']
    styles: List[Dict] = []

    for provider_def in provider_defs:
        try:
            plugin = _load_plugin(provider_def, server_url)
            content = plugin.get_styles()
            styles.extend(content['styles'])
        except ProviderGenericError as err:
            return api.get_exception(
                err.http_status_code, headers, request.format,
                err.ogc_exception_code, err.message)

    content = {
        'styles': styles,
        'links': [
            {
                'rel': 'alternate',
                'type': 'text/html',
                'title': 'This document as HTML',
                'href': f'{server_url}/styles?f=html'
            },
            {
                'rel': 'self',
                'type': 'application/json',
                'title': 'This document',
                'href': f'{server_url}/styles?f=json'
            }
        ]
    }

    if request.format == F_HTML:
        return headers, HTTPStatus.UNSUPPORTED_MEDIA_TYPE, ''

    return headers, HTTPStatus.OK, to_json(content, api.pretty_print)


def get_collection_styles(api: API, request: APIRequest,
                          collection_id: str) -> Tuple[Dict, int, str]:
    """
    Provide styles of a collection

    :param api: API object
    :param request: APIRequest instance with query params
    :param collection_id: collection identifier

    :returns: tuple of headers, status code, content
    """

    headers = request.get_response_headers(SYSTEM_LOCALE, **api.api_headers)

    collections = filter_dict_by_key_value(
        api.config['resources'], 'type', 'collection')

    collection = collections.get(collection_id)

    if not collection:
        return api.get_exception(
            HTTPStatus.NOT_FOUND, headers, request.format,
            'NotFound', 'Collection not found')

    provider_def = filter_providers_by_type(collection['providers'], 'style')

    if not provider_def:
        return api.get_exception(
            HTTPStatus.NOT_FOUND, headers, request.format,
            'NotFound', 'Style not found')

    server_url = api.config['server']['url']

    try:
        plugin = _load_plugin(provider_def, server_url)
    except ProviderGenericError as err:
        return api.get_exception(
            err.http_status_code, headers, request.format,
            err.ogc_exception_code, err.message)

    content = plugin.get_styles()

    content['links'] = [
        {
            'rel': 'alternate',
            'type': 'text/html',
            'title': 'This document as HTML',
            'href': f'{server_url}/collections/{collection_id}/styles?f=html'
        },
        {
            'rel': 'self',
            'type': 'application/json',
            'title': 'This document',
            'href': f'{server_url}/collections/{collection_id}/styles?f=json'
        }
    ]

    if request.format == F_HTML:
        return headers, HTTPStatus.UNSUPPORTED_MEDIA_TYPE, ''

    return headers, HTTPStatus.OK, to_json(content, api.pretty_print)


def get_style(api: API, request: APIRequest,
              style_id: str) -> Tuple[dict, int, str]:
    """
    Provide a style, or its stylesheet when a stylesheet format is requested

    :param api: API object
    :param request: APIRequest instance with query params
    :param style_id: style identifier

    :returns: tuple of headers, status code, content
    """

    headers = request.get_response_headers(SYSTEM_LOCALE, **api.api_headers)

    provider_def = _get_provider_def(api, style_id)

    if not provider_def:
        return api.get_exception(
            HTTPStatus.NOT_FOUND, headers, request.format,
            'NotFound', 'Style not found')

    server_url = api.config['server']['url']

    try:
        plugin = _load_plugin(provider_def, server_url)
    except ProviderGenericError as err:
        return api.get_exception(
            err.http_status_code, headers, request.format,
            err.ogc_exception_code, err.message)

    format_ = request._get_format(request.get_request_headers(request.headers))
    has_stylesheet = _has_stylesheet(provider_def, format_)

    if has_stylesheet and format_:
        return _get_style_definition(
            api, request, headers, plugin, style_id, format_)

    content = plugin.get_style(style_id)

    if not content:
        return api.get_exception(
            HTTPStatus.NOT_FOUND, headers, request.format,
            'NotFound', 'Style not found')

    if request.format == F_HTML:
        return headers, HTTPStatus.UNSUPPORTED_MEDIA_TYPE, ''

    return headers, HTTPStatus.OK, to_json(content, api.pretty_print)


def get_style_definition(api: API, request: APIRequest,
                         style_id: str) -> Tuple[dict, int, str]:
    """
    Provide the stylesheet of a style in the requested format

    :param api: API object
    :param request: APIRequest instance with query params
    :param style_id: style identifier

    :returns: tuple of headers, status code, content
    """

    headers = request.get_response_headers(SYSTEM_LOCALE, **api.api_headers)
    provider_def = _get_provider_def(api, style_id)

    if not provider_def:
        return api.get_exception(
            HTTPStatus.NOT_FOUND, headers, request.format,
            'NotFound', 'Style not found')

    server_url = api.config['server']['url']

    try:
        plugin = _load_plugin(provider_def, server_url)
    except ProviderGenericError as err:
        return api.get_exception(
            err.http_status_code, headers, request.format,
            err.ogc_exception_code, err.message)

    return _get_style_definition(
        api, request, headers, plugin, style_id, str(request.format))


def get_style_metadata(api: API, request: APIRequest,
                       style_id: str) -> Tuple[dict, int, str]:
    """
    Provide the metadata of a style

    :param api: API object
    :param request: APIRequest instance with query params
    :param style_id: style identifier

    :returns: tuple of headers, status code, content
    """

    headers = request.get_response_headers(SYSTEM_LOCALE, **api.api_headers)

    provider_def = _get_provider_def(api, style_id)

    if not provider_def:
        return api.get_exception(
            HTTPStatus.NOT_FOUND, headers, request.format,
            'NotFound', 'Style not found')

    server_url = api.config['server']['url']

    try:
        plugin = _load_plugin(provider_def, server_url)
    except ProviderGenericError as err:
        return api.get_exception(
            err.http_status_code, headers, request.format,
            err.ogc_exception_code, err.message)

    content = plugin.get_style_metadata(style_id)

    if not content:
        return api.get_exception(
            HTTPStatus.NOT_FOUND, headers, request.format,
            'NotFound', 'Style not found')

    if 'links' not in content:
        content['links'] = []

    content['links'].extend([
        {
            'rel': 'alternate',
            'type': 'text/html',
            'title': 'This document as HTML',
            'href': f'{server_url}/styles/{style_id}/metadata?f=html'
        },
        {
            'rel': 'self',
            'type': 'application/json',
            'title': 'This document',
            'href': f'{server_url}/styles/{style_id}/metadata?f=json'
        }
    ])

    if request.format == F_HTML:
        return headers, HTTPStatus.UNSUPPORTED_MEDIA_TYPE, ''

    return headers, HTTPStatus.OK, to_json(content, api.pretty_print)


def get_oas_30(cfg: Dict, locale: str) -> Tuple[List[Dict[str, str]], Dict[str, Dict]]:  # noqa
    """
    Get OpenAPI fragments

    :param cfg: `dict` of configuration
    :param locale: `str` of locale

    :returns: `tuple` of `list` of tag objects, and `dict` of path objects
    """

    collection_ids = _get_style_collection_ids(cfg)

    if not _has_global_styles(cfg) and not collection_ids:
        LOGGER.debug('No style providers configured')
        return [], {'paths': {}}

    paths = {}

    paths['/styles'] = {
        'get': {
            'tags': ['styles'],
            'summary': 'List available styles',
            'operationId': 'getStyles',
            'responses': {
                '200': {
                    'description': 'Styles available for the base resource',
                    'content': {
                        'application/json': {
                            'schema': {
                                '$ref': '#/components/schemas/styles'
                            }
                        },
                        'text/html': {
                            'schema': {
                                'type': 'string'
                            }
                        }
                    }
                }
            }
        }
    }

    paths['/styles/{styleId}'] = {
        'get': {
            'tags': ['styles'],
            'summary': 'Fetch a stylesheet for a style',
            'operationId': 'getStyle',
            'parameters': [
                {
                    '$ref': '#/components/parameters/styleId'
                }
            ],
            'responses': {
                '200': {
                    'description': 'The operation was executed successfully',
                    'content': {
                        'application/vnd.mapbox.style+json': {
                            'schema': {
                                'type': 'object'
                            }
                        },
                        'application/vnd.ogc.se+xml': {
                            'schema': {
                                'type': 'string',
                                'format': 'xml'
                            }
                        },
                        'application/vnd.ogc.sld+xml': {
                            'schema': {
                                'type': 'string',
                                'format': 'xml'
                            }
                        },
                        'text/html': {
                            'schema': {
                                'type': 'string'
                            }
                        }
                    }
                },
                '400': {
                    'description': 'Bad Request'
                },
                '404': {
                    'description': 'Not Found'
                },
                '406': {
                    'description': 'Not Acceptable'
                },
                '500': {
                    'description': 'Server Error'
                }
            }
        }
    }

    paths['/styles/{styleId}/metadata'] = {
        'get': {
            'tags': ['styles'],
            'summary': 'Fetch style metadata',
            'operationId': 'getStyleMetadata',
            'parameters': [
                {
                    '$ref': '#/components/parameters/styleId'
                }
            ],
            'responses': {
                '200': {
                    'description': 'The operation was executed successfully',
                    'content': {
                        'application/json': {
                            'schema': {
                                '$ref': '#/components/schemas/stylemetadata'
                            }
                        },
                        'text/html': {
                            'schema': {
                                'type': 'string'
                            }
                        }
                    }
                },
                '400': {
                    'description': 'Bad Request'
                },
                '404': {
                    'description': 'Not Found'
                },
                '406': {
                    'description': 'Not Acceptable'
                },
                '500': {
                    'description': 'Server Error'
                }
            }
        }
    }

    paths['/collections/{collectionId}/styles'] = {
        'get': {
            'tags': ['styles'],
            'summary': "List available styles for collection '{collectionId}'",
            'operationId': 'collection.getStyles',
            'parameters': [
                {
                    '$ref': '#/components/parameters/collectionIdStyles'
                },
            ],
            'responses': {
                '200': {
                    'description': 'Styles available for the collection',
                    'content': {
                        'application/json': {
                            'schema': {
                                '$ref': '#/components/schemas/styles'
                            }
                        },
                        'text/html': {
                            'schema': {
                                'type': 'string'
                            }
                        }
                    }
                },
                '400': {
                    'description': 'Bad Request'
                },
                '404': {
                    'description': 'Not Found'
                },
                '406': {
                    'description': 'Not Acceptable'
                },
                '500': {
                    'description': 'Server Error'
                }
            }
        }
    }

    link = f"{OPENAPI_YAML['oapit']}#/components/schemas/link"

    # An empty enum would be an invalid schema, so it is only set when at
    # least one collection has a style provider
    collection_id_schema: Dict[str, Any] = {'type': 'string'}

    if collection_ids:
        collection_id_schema['enum'] = collection_ids

    components = {
        'parameters': {
            'styleId': {
                'name': 'styleId',
                'in': 'path',
                'description': 'local identifier of a style',
                'required': True,
                'schema': {
                    'type': 'string'
                }
            },
            'collectionIdStyles': {
                'name': 'collectionId',
                'in': 'path',
                'description': 'local identifier of a collection with styles',
                'required': True,
                'schema': collection_id_schema
            }
        },
        'schemas': {
            'style': {
                'type': 'object',
                'required': ['id'],
                'properties': {
                    'id': {
                        'description': 'identifier of the style',
                        'type': 'string'
                    },
                    'title': {
                        'description': 'a human readable title of the style',
                        'type': 'string'
                    },
                    'links': {
                        'type': 'array',
                        'items': {'$ref': link}
                    }
                }
            },
            'styles': {
                'type': 'object',
                'required': ['styles'],
                'properties': {
                    'styles': {
                        'type': 'array',
                        'items': {'$ref': '#/components/schemas/style'}
                    },
                    'links': {
                        'type': 'array',
                        'items': {'$ref': link}
                    }
                }
            },
            'stylemetadata': {
                'type': 'object',
                'required': ['id'],
                # The spec allows a long list of optional properties; only
                # the ones our providers populate are described here.
                'additionalProperties': True,
                'properties': {
                    'id': {
                        'description': 'identifier of the style',
                        'type': 'string'
                    },
                    'title': {
                        'description': 'a human readable title of the style',
                        'type': 'string'
                    },
                    'description': {
                        'description': 'a description of the style',
                        'type': 'string'
                    },
                    'keywords': {
                        'type': 'array',
                        'items': {
                            'type': 'string'
                        }
                    },
                    'version': {
                        'description': 'the version of the style',
                        'type': 'string'
                    },
                    'stylesheets': {
                        'type': 'array',
                        'items': {
                            'type': 'object',
                            'properties': {
                                'title': {
                                    'type': 'string'
                                },
                                'version': {
                                    'type': 'string'
                                },
                                'specification': {
                                    'type': 'string',
                                    'format': 'uri'
                                },
                                'native': {
                                    'type': 'boolean'
                                },
                                'link': {'$ref': link}
                            }
                        }
                    },
                    'layers': {
                        'type': 'array',
                        'items': {
                            'type': 'object',
                            'properties': {
                                'id': {
                                    'type': 'string'
                                },
                                'type': {
                                    'type': 'string'
                                }
                            }
                        }
                    },
                    'links': {
                        'type': 'array',
                        'items': {'$ref': link}
                    }
                }
            }
        }
    }

    return [{'name': 'styles'}], {'paths': paths, 'components': components}


def has_styles(cfg: Dict) -> bool:
    """
    Whether anything in the configuration serves styles

    Used by `pygeoapi.api.landing_page()` to decide whether to advertise
    the endpoints at all, and by `get_oas_30()` for the same reason.

    :param cfg: `dict` of configuration

    :returns: `bool` of whether a style resource or a collection style
              provider is configured
    """

    return bool(_has_global_styles(cfg) or _get_style_collection_ids(cfg))


def get_landing_page_link(base_url: str, locale: str) -> Dict:
    """
    Get the landing page link to the styles endpoint

    :param base_url: `str` of server base URL
    :param locale: locale of the request

    :returns: `dict` of a link object
    """

    return {
        'rel': STYLES_RELTYPE,
        'type': FORMAT_TYPES[F_JSON],
        'title': l10n.translate('Styles', locale),
        'href': f'{base_url}/styles?f={F_JSON}'
    }


def get_collection_links(config: Dict, collections_url: str, dataset: str,
                         locale: str) -> List[Dict]:
    """
    Get the links from a collection to its styles endpoint

    :param config: `dict` of the collection resource definition
    :param collections_url: `str` of collections URL
    :param dataset: `str` of collection identifier
    :param locale: locale of the request

    :returns: `list` of link objects, empty when the collection has no style
              provider
    """

    if not filter_providers_by_type(config.get('providers', []), 'style'):
        return []

    return [{
        'type': FORMAT_TYPES[F_JSON],
        'rel': STYLES_RELTYPE,
        'title': l10n.translate('Styles to render data in maps as JSON', locale),  # noqa
        'href': f'{collections_url}/{dataset}/styles?f={F_JSON}'
    }, {
        'type': FORMAT_TYPES[F_HTML],
        'rel': STYLES_RELTYPE,
        'title': l10n.translate('Styles to render data in maps as HTML', locale),  # noqa
        'href': f'{collections_url}/{dataset}/styles'
    }]


def _has_global_styles(cfg: Dict) -> bool:
    resources = cfg.get('resources', {})

    return bool(filter_dict_by_key_value(resources, 'type', 'style'))


def _get_style_collection_ids(cfg: Dict) -> List[str]:
    collection_ids = []

    collections = filter_dict_by_key_value(
        cfg.get('resources', {}), 'type', 'collection')

    for key, collection in collections.items():
        if filter_providers_by_type(collection['providers'], 'style'):
            collection_ids.append(key)

    return collection_ids


def _get_provider_def(api: API, style_id: str) -> Dict | None:
    provider_defs = _get_provider_defs(api)

    for provider_def in provider_defs:
        if _has_style_id(provider_def, style_id):
            return provider_def

    return None


def _get_provider_defs(api: API) -> List[Dict]:
    provider_defs = []

    global_styles = filter_dict_by_key_value(
        api.config['resources'], 'type', 'style')

    if global_styles:
        provider_defs.append(global_styles['styles']['provider'])

    collections = filter_dict_by_key_value(
        api.config['resources'], 'type', 'collection')

    for key in collections.keys():
        provider_def = filter_providers_by_type(
            collections[key]['providers'], 'style')

        if provider_def:
            provider_defs.append(provider_def)

    return provider_defs


def _get_style_definition(
    api: API,
    request: APIRequest,
    headers: Dict,
    plugin: BaseStyleProvider,
    style_id: str,
    format_: str
) -> Tuple[dict, int, str]:
    content = plugin.get_style_definition(style_id, format_)

    if not content:
        return api.get_exception(
            HTTPStatus.NOT_FOUND, headers, request.format,
            'NotFound', 'Style not found')

    if request.format == F_HTML:
        return headers, HTTPStatus.UNSUPPORTED_MEDIA_TYPE, ''

    return headers, HTTPStatus.OK, content


def _has_style_id(provider_def: Dict | None, style_id: str) -> bool:
    if not provider_def:
        return False

    styles = provider_def['styles']
    has_style_id = any(style['id'] == style_id for style in styles)

    return has_style_id


def _load_plugin(provider_def: Dict, server_url: str) -> BaseStyleProvider:
    provider_def['server_url'] = server_url

    return load_plugin('provider', provider_def)


def _has_stylesheet(provider_def: Dict, type_: str | None) -> bool:
    if not type_:
        return False

    styles: List[Dict[str, Any]] = provider_def.get('styles', [])

    for style in styles:
        stylesheets: List[Dict[str, Any]] = style.get('stylesheets', [])

        for stylesheet in stylesheets:
            if stylesheet.get('type') == type_:
                return True

    return False
