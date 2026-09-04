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
Regression tests for this fork's divergences from upstream pygeoapi.

Each test here pins behaviour that upstream does not have. A future rebase
that silently drops one of our hooks fails a test in this file rather than
going unnoticed. See FORK.md for why each divergence exists.
"""

import json

import pytest

from pygeoapi import util


# to_json: separators and ensure_ascii (FORK.md)

def test_to_json_keeps_non_ascii_literal():
    """Norwegian characters survive as themselves, not as \\uXXXX escapes."""

    output = util.to_json({'kommune': 'Bærum', 'sted': 'Ålesund'})

    assert output == '{"kommune": "Bærum", "sted": "Ålesund"}'
    assert '\\u' not in output
    assert json.loads(output) == {'kommune': 'Bærum', 'sted': 'Ålesund'}


def test_to_json_keeps_non_ascii_literal_when_pretty():
    output = util.to_json({'kommune': 'Bærum'}, pretty=True)

    assert output == '{\n    "kommune": "Bærum"\n}'


def test_to_json_uses_spaced_separators():
    """Non-pretty output is spaced, unlike upstream's compact separators."""

    assert util.to_json({'a': 1, 'b': 2}) == '{"a": 1, "b": 2}'


def test_to_json_still_escapes_angle_brackets():
    """Upstream's XSS mitigation must survive our changes to this function."""

    output = util.to_json({'k': '<script>alert("hi")</script>'})

    assert '<' not in output
    assert '>' not in output
    assert '&lt;script&gt;' in output


# get_choice_from_headers: media-type parameters (FORK.md)

@pytest.mark.parametrize('header,expected', [
    # A parameter other than q no longer discards the whole part
    ['application/vnd.ogc.sld+xml;version=1.1.0',
     ['application/vnd.ogc.sld+xml']],
    ['text/html;charset=utf-8', ['text/html']],
    # q alongside another parameter is still honoured as the weight
    ['text/html;version=1.1.0;q=0.2,application/json;q=0.9',
     ['application/json', 'text/html']],
    # Whitespace around the parameter
    ['application/json; q=0.8 , text/html',
     ['text/html', 'application/json']],
    # Every part parameterised: upstream raised IndexError for all=False
    ['application/se+xml;version=1.1.0,application/sld+xml;version=1.0.0',
     ['application/se+xml', 'application/sld+xml']],
])
def test_get_choice_from_headers_tolerates_media_type_parameters(header,
                                                                 expected):
    headers = {'accept': header}

    assert util.get_choice_from_headers(
        headers, 'accept', all=True) == expected
    assert util.get_choice_from_headers(headers, 'accept') == expected[0]


def test_get_choice_from_headers_drops_media_type_parameters():
    """Callers negotiate on the media type alone, so it is what we return."""

    headers = {'accept': 'application/vnd.ogc.sld+xml;version=1.1.0'}

    assert util.get_choice_from_headers(headers, 'accept') == \
        'application/vnd.ogc.sld+xml'


# get_choice_from_headers: q=0 and empty results (FORK.md)

@pytest.mark.parametrize('header', [
    'text/html;q=0',
    'text/html;q=0.0',
    'text/html;q=1.5',  # out of range, excluded upstream as well
])
def test_get_choice_from_headers_unacceptable_returns_none(header):
    """q=0 means "not acceptable"; upstream raised ZeroDivisionError."""

    headers = {'accept': header}

    assert util.get_choice_from_headers(headers, 'accept') is None
    assert util.get_choice_from_headers(headers, 'accept', all=True) == []


def test_get_choice_from_headers_q_zero_skips_only_that_part():
    headers = {'accept': 'text/html;q=0,application/json'}

    assert util.get_choice_from_headers(headers, 'accept') == \
        'application/json'
    assert util.get_choice_from_headers(headers, 'accept', all=True) == \
        ['application/json']


def test_get_choice_from_headers_all_returns_list_not_none():
    """Both callers in pygeoapi/api/__init__.py iterate the all=True result."""

    result = util.get_choice_from_headers({'accept': 'text/html;q=0'},
                                          'accept', all=True)

    assert result == []
    assert result is not None


# Behaviour we inherit unchanged, asserted so our edits cannot regress it

@pytest.mark.parametrize('header,expected', [
    ['fr-CH, fr;q=0.9, en;q=0.8', ['fr-CH', 'fr', 'en']],
    ['en;q=0.8,de', ['de', 'en']],
    ['en,de', ['en', 'de']],
    ['*/*', ['*/*']],
])
def test_get_choice_from_headers_plain_headers_unchanged(header, expected):
    headers = {'accept-language': header}

    assert util.get_choice_from_headers(
        headers, 'accept-language', all=True) == expected


def test_get_choice_from_headers_missing_header():
    assert util.get_choice_from_headers({'accept': '*/*'},
                                        'accept-language') is None
