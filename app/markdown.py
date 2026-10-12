"""User Markdown -> safe HTML.

Every place that shows a body (the admin preview now, the export later) goes
through render(), so there is one sanitizer and one allow-list.
"""
from __future__ import annotations

import nh3
from markdown_it import MarkdownIt

_md = MarkdownIt("commonmark")

# Links may only point at the web or an email address; anything else
# (javascript:, data:, ...) is dropped by nh3.
_URL_SCHEMES = {"http", "https", "mailto"}


def render(body: str) -> str:
    """Render Markdown and strip every tag and attribute not on nh3's allow-list."""
    return nh3.clean(_md.render(body), url_schemes=_URL_SCHEMES)
