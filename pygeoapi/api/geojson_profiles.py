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
GeoJSON profiles for items and single items (OGC 21-045 clause 15).

JSON-FG and plain GeoJSON share the `application/geo+json` media type; the
`profile` query parameter picks between them. Plain GeoJSON is `rfc7946`;
any other profile is served by a collection formatter that lists it in its
`profiles` attribute.
"""

import logging
import re
from typing import Dict, List, Optional

from pygeoapi.formats import F_JSON
from pygeoapi.util import (filter_dict_by_key_value, get_choice_from_headers,
                           get_dataset_formatters)

LOGGER = logging.getLogger(__name__)

RFC7946 = 'rfc7946'

GEOJSON = 'application/geo+json'

PROFILE_URI = 'http://www.opengis.net/def/profile/OGC/0/{}'

# OGC API - Features - Part 5, /req/profile-parameter/profile-param B
PROFILE_URI_PATTERN = re.compile(
    r'^https?://www\.opengis\.net/def/profile/OGC/0/(.+)$')
PROFILE_CURIE_PATTERN = re.compile(r'^\[ogc-profile:(.+)\]$')


def parse_profiles(value: Optional[str]) -> List[str]:
    """
    Reduce a `profile` query parameter to profile identifiers

    :param value: comma separated profile identifiers, URIs or safe CURIEs

    :returns: `list` of profile identifiers, in request order
    """

    profiles = []

    for item in (value or '').split(','):
        item = item.strip()
        match = (PROFILE_URI_PATTERN.match(item) or
                 PROFILE_CURIE_PATTERN.match(item))

        if match:
            item = match.group(1)

        if item:
            profiles.append(item)

    return profiles


def get_profile_formatters(dataset_formatters: Dict) -> Dict:
    """
    Map each declared profile to the formatter that serves it

    A formatter serving a profile by default wins over one that merely
    satisfies it as well.

    :param dataset_formatters: `dict` of formatters, keyed by name

    :returns: `dict` of formatters, keyed by profile identifier
    """

    declaring = [formatter for formatter in dataset_formatters.values()
                 if getattr(formatter, 'profiles', None)]
    profile_formatters = {}

    for formatter in declaring:
        profile_formatters.setdefault(formatter.profiles[0], formatter)

    for formatter in declaring:
        for profile in formatter.profiles:
            profile_formatters.setdefault(profile, formatter)

    return profile_formatters


def _is_geojson(formatter) -> bool:
    return formatter.mimetype.split(';')[0].strip() == GEOJSON


def _has_f(request) -> bool:
    return bool((request.params.get('f') or '').strip())


def negotiate_profile(request, dataset_formatters: Dict) -> Optional[str]:
    """
    Choose the GeoJSON profile of the response

    An explicit `f` keeps its format and only names the profile it serves.
    Otherwise the first requested profile a formatter declares replaces the
    negotiated format, and anything else is answered as plain GeoJSON, so
    a formatter's `application/geo+json` never wins negotiation on its own.

    :param request: `APIRequest` instance, its format already negotiated
    :param dataset_formatters: `dict` of formatters, keyed by name

    :returns: `str` of the profile identifier, or `None` when the response
              is not GeoJSON or its profile is unknown
    """

    formatter = next((df for df in dataset_formatters.values()
                      if df.f == request.format), None)

    if formatter is None and request.format not in (None, F_JSON):
        return None

    if formatter is not None and not _is_geojson(formatter):
        return None

    if _has_f(request):
        if formatter is None:
            return RFC7946

        return (getattr(formatter, 'profiles', None) or [None])[0]

    profile_formatters = get_profile_formatters(dataset_formatters)

    for profile in parse_profiles(request.params.get('profile')):
        if profile == RFC7946:
            break

        if profile in profile_formatters:
            request._format = profile_formatters[profile].f
            LOGGER.debug(f'Profile {profile}: format {request.format}')

            return profile

    if formatter is not None:
        request._format = None

    return RFC7946


def _prefers_geojson(request) -> bool:
    """Whether `Accept` ranks `application/geo+json` above JSON"""

    if _has_f(request):
        return False

    accepted = get_choice_from_headers(
        request.get_request_headers(request.headers), 'accept', all=True)

    for type_ in accepted or []:
        if type_ in (GEOJSON, 'application/json'):
            return type_ == GEOJSON

    return False


def set_profile_headers(request, headers: Dict,
                        profile: Optional[str]) -> None:
    """
    Name the profile of a successful response

    :param request: `APIRequest` instance
    :param headers: `dict` of response headers, modified in place
    :param profile: `str` returned by `negotiate_profile()`
    """

    if profile is None:
        return

    headers['Link'] = f'<{PROFILE_URI.format(profile)}>; rel="profile"'

    if profile == RFC7946 and _prefers_geojson(request):
        headers['Content-Type'] = GEOJSON


def _get_profile_parameter(profiles: List[str]) -> Dict:
    description = (
        'GeoJSON profile of the response (OGC 21-045). '
        f"Supported: {', '.join(profiles)}. Default: {RFC7946}. "
        'Profile URIs are accepted as well.'
    )

    return {
        'name': 'profile',
        'in': 'query',
        'description': description,
        'required': False,
        'style': 'form',
        'explode': False,
        'schema': {
            'type': 'array',
            'items': {'type': 'string'}
        }
    }


def add_profile_parameters(cfg: Dict, paths: Dict) -> None:
    """
    Declare `profile` on the items and item operations of each collection

    :param cfg: `dict` of configuration
    :param paths: `dict` of OpenAPI paths, modified in place
    """

    collections = filter_dict_by_key_value(cfg['resources'],
                                           'type', 'collection')

    for name, collection in collections.items():
        operations = [
            paths.get(path, {}).get('get') for path in (
                f'/collections/{name}/items',
                f'/collections/{name}/items/{{featureId}}')
        ]
        operations = [operation for operation in operations if operation]

        if not operations:
            continue

        profiles = [RFC7946, *get_profile_formatters(
            get_dataset_formatters(collection))]

        for operation in operations:
            operation['parameters'].append(_get_profile_parameter(profiles))
