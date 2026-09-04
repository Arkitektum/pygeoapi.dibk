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
Style provider stub, loaded by dotted path from the test configuration.

It serves fixed content so the api layer and the routes can be exercised
without a real style store. Norwegian characters are deliberate: they also
cover the non-ASCII serialization divergence.
"""


class StyleProvider:
    """Minimal `type: style` provider for tests"""

    def __init__(self, provider_def: dict):
        self.styles = provider_def['styles']
        self.server_url = provider_def['server_url']

    def _get_configured_style(self, style_id: str) -> dict | None:
        for style in self.styles:
            if style['id'] == style_id:
                return style

        return None

    def get_styles(self) -> dict:
        return {
            'styles': [
                {
                    'id': style['id'],
                    'title': style.get('title'),
                    'links': [
                        {
                            'rel': 'stylesheet',
                            'type': stylesheet['type'],
                            'href': f"{self.server_url}/styles/{style['id']}"
                        }
                        for stylesheet in style.get('stylesheets', [])
                    ]
                }
                for style in self.styles
            ]
        }

    def get_style(self, style_id: str) -> dict | None:
        style = self._get_configured_style(style_id)

        if not style:
            return None

        return {'id': style['id'], 'title': style.get('title')}

    def get_style_metadata(self, style_id: str) -> dict | None:
        style = self._get_configured_style(style_id)

        if not style:
            return None

        return {
            'id': style['id'],
            'title': style.get('title'),
            'description': 'Stilsett for Bærum og Ålesund',
            'stylesheets': [
                {'title': style.get('title'), 'native': True,
                 'version': stylesheet['type']}
                for stylesheet in style.get('stylesheets', [])
            ]
        }

    def get_style_definition(self, style_id: str, format_: str) -> str | None:
        style = self._get_configured_style(style_id)

        if not style:
            return None

        for stylesheet in style.get('stylesheets', []):
            if stylesheet['type'] == format_:
                return (f'<?xml version="1.0"?><{format_} '
                        f'id="{style_id}">Bærum</{format_}>')

        return None

    def get_style_preview(self, style_id: str):
        raise NotImplementedError()
