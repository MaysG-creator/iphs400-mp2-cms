# CONTEXT.md glossary

Client: Kenyon College Men's Soccer. The site is run by student media members so fans,
alumni, and players' families can find accurate game info without digging through Instagram.

Use these words everywhere (code, templates, tickets, commits). If a better word appears,
change it here instead of using both.

## Terms

**Update** — A time-ordered team news item (what the CMS stores as a *post*). Free-form
Markdown with a title. Never call it "article" or "bulletin". Shown newest first on the home page.

**Fixture** — A scheduled game, listed on the Schedule page. Fans may say "game" or "match";
the glossary term is *fixture*.

**Match report** — An *update* written after a fixture, holding the verified score and scorers.
Also called a recap.

**Page** — Stable content that appears in the public navigation: Schedule, Roster,
Results/Record, History, About/Contact.

**Nav order** — A number on each *page* set by the admin that decides where it sits in the
public menu. Schedule and Results come before History and About.

**History** — A *page* covering the program's past titles and accomplishments.

**Draft** — Content only visible in the admin console. Editors can only produce drafts.
Drafts never reach `site/`.

**Published** — Content that `cms publish` exports to the public site. Only the admin can set it.

**Slug** — URL-safe name generated from the title when first saved. Read-only for editors.

**Admin** — The single account that publishes, deletes published content, manages users, and
runs `cms publish` and `cms deploy`. Exactly one exists at any time.

**Editor** — A student media member. Creates and edits drafts, edits any draft, deletes only
their own drafts, and cannot change published content.

**Hand-over** — The admin action that promotes another user to admin and demotes the current
admin in one step. It's the only way the admin role changes hands.

**Last updated** — The date shown on every public update and page, so fans can judge freshness.

## Decisions

- Out of scope: comments, live scores, WYSIWYG editor, multi-site.
- Stretch (after the 7 core capabilities): photo uploads with alt text, categories and tags.
- The admin console runs on one machine; remote access for editors comes later.
- Updates are expected about an hour after a game, not live.
- The home page orders updates by when they were first written, newest first. Editing or
  correcting an update changes its *last updated* date but never moves it above a newer update.
- The public site is purple and white with a CSS-only banner. The admin console is not themed.
- Sample content is clearly marked as sample, never invented scores or stats.
- A deactivated user keeps their authorship and content.
- The dashboard counts drafts (updates and pages together), published updates, and published
  pages. A draft page counts only as a draft.
