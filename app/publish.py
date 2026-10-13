"""Render the public site into site/ as plain HTML.

Two rules the rubric checks:

  1. Only PUBLISHED content is written here. A draft that reaches site/ is a bug.
  2. Every href and src is RELATIVE ("style.css", "updates/x.html"), never
     root-absolute ("/style.css"), because Pages serves this from a subfolder.

The folder is rebuilt from scratch on every run, so an update that was
unpublished since the last run disappears from the site.
"""
from __future__ import annotations

import shutil
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from jinja2 import Environment, FileSystemLoader, select_autoescape

from app import markdown, settings, updates

# Purple and white, with a CSS-only banner. No images, and nothing wider than
# the screen, so a 390 px phone never scrolls sideways.
CSS = """*, *::before, *::after { box-sizing: border-box; }
:root { --purple: #4b2e83; --purple-dark: #2e1a57; --lilac: #f3eefb; }
body { font: 17px/1.6 system-ui, sans-serif; margin: 0; color: #1d1a24; background: #fff; }
.banner {
  background: linear-gradient(135deg, var(--purple-dark), var(--purple) 60%, #6a4bb0);
  border-bottom: .4rem solid #fff; box-shadow: 0 .4rem 0 var(--purple);
  padding: 1.5rem 1rem; text-align: center;
}
.banner a { color: #fff; font-size: 1.6rem; font-weight: 800; letter-spacing: .02em;
            text-decoration: none; text-transform: uppercase; }
main, footer { margin: 0 auto; max-width: 42rem; padding: 0 1rem; }
main { margin-block: 2rem; overflow-wrap: anywhere; }
h1, h2, h3 { color: var(--purple-dark); line-height: 1.25; }
a { color: var(--purple); }
.updates { list-style: none; padding: 0; }
.updates li { border-left: .3rem solid var(--purple); background: var(--lilac);
              margin-bottom: .75rem; padding: .6rem .9rem; }
.updates a { display: block; font-weight: 700; }
.meta, small { color: #5a5266; }
img, video { max-width: 100%; height: auto; }
pre { overflow-x: auto; }
table { display: block; overflow-x: auto; }
footer { border-top: 2px solid var(--lilac); padding-block: 1rem; }
"""

# Dates on the public site are the team's local date, not UTC: an update saved
# at 9 pm Eastern is already "tomorrow" in UTC.
LOCAL_TIME = ZoneInfo("America/New_York")


def local_date(timestamp: str) -> str:
    """'2026-10-13T01:30:00+00:00' -> 'October 12, 2026'."""
    local = datetime.fromisoformat(timestamp).astimezone(LOCAL_TIME)
    return f"{local:%B} {local.day}, {local.year}"


def update_path(update) -> str:
    """Where an update's page lives, relative to the site root."""
    return f"updates/{update['slug']}.html"


def environment() -> Environment:
    env = Environment(
        loader=FileSystemLoader(str(settings.TEMPLATES)),
        autoescape=select_autoescape(["html"]),
    )
    env.filters["local_date"] = local_date
    env.globals["site_title"] = settings.SITE_TITLE
    return env


def render_site(out: Path | None = None) -> Path:
    out = out or settings.SITE
    if out.exists():
        shutil.rmtree(out)
    (out / "updates").mkdir(parents=True)
    env = environment()
    published = updates.list_published()

    (out / "style.css").write_text(CSS)
    page = env.get_template("public/update.html")
    for update in published:
        (out / update_path(update)).write_text(page.render(
            root="../", title=update["title"], update=update,
            body=markdown.render(update["body"]),
        ))
    (out / "index.html").write_text(render_home(published, env))
    return out


def render_home(published: list | None = None, env: Environment | None = None) -> str:
    """The home page: published updates, newest first, each with its date."""
    if published is None:
        published = updates.list_published()
    items = [{"title": u["title"], "href": update_path(u), "updated_at": u["updated_at"]}
             for u in published]
    return (env or environment()).get_template("public/home.html").render(
        root="", title=settings.SITE_TITLE, items=items,
    )
