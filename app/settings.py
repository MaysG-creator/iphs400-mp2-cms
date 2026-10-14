"""Configuration, read from the environment (never hard-code secrets)."""
from __future__ import annotations

import os
import secrets
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TEMPLATES = ROOT / "templates"
SITE = ROOT / "site"

# Signs the session cookie. Without CMS_SECRET_KEY a random per-process key is
# used: sessions end on restart, but nobody can forge one from a known default.
SECRET_KEY = os.environ.get("CMS_SECRET_KEY") or secrets.token_urlsafe(32)
DATABASE_PATH = Path(os.environ.get("CMS_DATABASE", ROOT / "cms.db"))
SITE_TITLE = os.environ.get("CMS_SITE_TITLE", "Kenyon Men's Soccer")
# Set this to your Pages URL once you deploy, e.g.
# https://yourname.github.io/iphs400-mp2-cms/
BASE_PATH = os.environ.get("CMS_BASE_PATH", "")
