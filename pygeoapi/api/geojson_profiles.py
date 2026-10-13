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
from typing import Dict, List, NamedTuple, Optional

from pygeoapi.formats import F_JSON
from pygeoapi.util import (filter_dict_by_key_value, get_choice_from_headers,
                           get_dataset_formatters)

LOGGER = logging.getLogger(__name__)

RFC7946 = 'rfc7946'
JSONFG = 'jsonfg'

GEOJSON = 'application/geo+json'

CONFORMANCE_CLASS_API = 'http://www.opengis.net/spec/json-fg-1/1.0/conf/api'

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


class GeoJsonProfile(NamedTuple):
    """
    The profile of a response, and the media type to serve it as

    `media_type` is `None` when the response keeps the type its format has.
    """

    id: str
    media_type: Optional[str] = None


def _is_geojson(formatter) -> bool:
    return formatter.mimetype.split(';')[0].strip() == GEOJSON


def _has_f(request) -> bool:
    return bool((request.params.get('f') or '').strip())


def _prefers_geojson(request) -> bool:
    """Whether `Accept` ranks `application/geo+json` above JSON"""

    accepted = get_choice_from_headers(
        request.get_request_headers(request.headers), 'accept', all=True)

    for type_ in accepted or []:
        if type_ in (GEOJSON, 'application/json'):
            return type_ == GEOJSON

    return False


def negotiate_profile(request,
                      dataset_formatters: Dict) -> Optional[GeoJsonProfile]:
    """
    Choose the GeoJSON profile of the response

    A format chosen by `f`, or by a media type of its own, stays and names
    the profile it serves. A format reached through `application/geo+json`,
    which plain GeoJSON shares, gives way to the first requested profile a
    formatter declares, served as `application/geo+json`; without one the
    response is plain GeoJSON.

    :param request: `APIRequest` instance, its format already negotiated
    :param dataset_formatters: `dict` of formatters, keyed by name

    :returns: `GeoJsonProfile`, or `None` when the response is neither
              GeoJSON nor a profile a formatter declares
    """

    formatter = next((df for df in dataset_formatters.values()
                      if df.f == request.format), None)
    declared = getattr(formatter, 'profiles', None) or []

    if formatter is None and request.format not in (None, F_JSON):
        return None

    if formatter is not None and not declared and not _is_geojson(formatter):
        return None

    if _has_f(request) or (formatter is not None and
                           not _is_geojson(formatter)):
        if formatter is None:
            return GeoJsonProfile(RFC7946)

        return GeoJsonProfile(declared[0]) if declared else None

    profile_formatters = get_profile_formatters(dataset_formatters)

    for profile in parse_profiles(request.params.get('profile')):
        if profile == RFC7946:
            break

        if profile in profile_formatters:
            request._format = profile_formatters[profile].f
            LOGGER.debug(f'Profile {profile}: format {request.format}')

            return GeoJsonProfile(profile, GEOJSON)

    if formatter is not None:
        request._format = None

    return GeoJsonProfile(RFC7946,
                          GEOJSON if _prefers_geojson(request) else None)


def set_profile_headers(headers: Dict,
                        profile: Optional[GeoJsonProfile]) -> None:
    """
    Name the profile of a successful response, and its media type

    :param headers: `dict` of response headers, modified in place
    :param profile: `GeoJsonProfile` returned by `negotiate_profile()`
    """

    if profile is None:
        return

    headers['Link'] = f'<{PROFILE_URI.format(profile.id)}>; rel="profile"'

    if profile.media_type:
        headers['Content-Type'] = profile.media_type


def get_conformance_classes(cfg: Dict) -> List[str]:
    """
    JSON-FG conformance classes of the API

    "JSON-FG in Web APIs" applies once a collection serves the `jsonfg`
    profile; the `profile` parameter itself is supported everywhere.

    :param cfg: `dict` of configuration

    :returns: `list` of conformance class URIs
    """

    collections = filter_dict_by_key_value(cfg['resources'],
                                           'type', 'collection')

    for collection in collections.values():
        formatters = get_dataset_formatters(collection)

        if JSONFG in get_profile_formatters(formatters):
            return [CONFORMANCE_CLASS_API]

    return []


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
