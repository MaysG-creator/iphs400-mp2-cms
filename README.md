# Kenyon Men's Soccer CMS (IPHS 400 Mini-Project #2)

A small CMS for Kenyon College Men's Soccer. Student media members write updates and
pages in a local admin console. The admin publishes them, and `cms publish` exports the
published content as a static site on GitHub Pages. The glossary is in `CONTEXT.md`, and
the spec is GitHub issue #1.

## Live URL

https://maysg-creator.github.io/iphs400-mp2-cms/

## Run locally

You need `git` and [`uv`](https://docs.astral.sh/uv/). These steps were tested on a fresh
clone.

```bash
git clone https://github.com/MaysG-creator/iphs400-mp2-cms.git
cd iphs400-mp2-cms
uv sync
cp .env.example .env
uv run --env-file .env python scripts/seed_demo.py
uv run --env-file .env cms serve
```

Then open http://localhost:8000/admin and log in with a demo account:

| Role | Email | Password (from `.env`) |
|---|---|---|
| Admin | `admin@example.test` | `change-me-admin` (`CMS_ADMIN_PASSWORD`) |
| Editor | `editor@example.test` | `change-me-editor` (`CMS_EDITOR_PASSWORD`) |

The seed adds sample updates and pages, each one marked as a sample. Running it again is
harmless. If port 8000 is taken, add `--port 8001` to the serve command. Quote any `.env`
value that contains spaces, or `--env-file` will not read the file.

Run the tests with `uv run pytest`. To export the public site, run
`uv run --env-file .env cms publish`, which writes `site/`. To put that export live, follow
`docs/runbooks/publish-and-deploy.md`.

## Generative AI Use Statement

I built this with Claude Code, following the mattpocock/skills workflow: grill, spec,
tickets, then implement and code-review for each ticket.

**Models.** These are the models in `notes/usage-ledger.csv`, all at medium effort:

- **Claude Sonnet 5.5** for the grill, the spec, and the tickets. I used `/model opusplan`,
  which runs Opus in plan mode and Sonnet otherwise.
- **Claude Opus 5.5** for implementing tickets T01–T07.

**Skills** (from the mattpocock-skills plugin):

- `setup-matt-pocock-skills` and `ask-matt` for setup.
- `/grill-with-docs` for the grill session. It ran the `grilling` skill, with my field
  notes, client brief, manual, and rubric attached.
- `to-spec` and `to-tickets` to turn the grill into the spec and the tickets.
- `implement` and `tdd` to build each ticket test-first.
- `code-review` before closing each ticket.
- `handoff` for the session handoff in `docs/handoff/`.

### Two prompts I really used

> /grill-with-docs
> 1. GOAL: Build a CMS for Kenyon College Men's Soccer, run by student media members, so fans, alumni, and players' families can find accurate game info without digging through Instagram. It must meet every requirement in @docs/mp2-grading-rubric_20260922.md.
> 2. METHOD: Use best practices for a clean, efficient, easy-to-use CMS workflow, informed by @docs/manual_iphs400_mp2-web-cms_20260922.md, my field notes @notes/cms-field-notes.md, and my client brief @notes/client-brief.md.
> 3. PREP: Interview me one question at a time using the AskUserQuestion tool, with your recommended answer for each.

> wait for the last question I answered those were supposed to be things I want in the website, reverse my answers and continue with the grill after

### One real model failure
I asked Claude to commit and push Excercise A and it created a new branch called exercise-a-ctx-guard all by itself and pushed it there instead of main. When I found out I got very confused and had to merge it back into main and delete the branch it created. Then to be safe I added "to main" on every subsequent push and commit request
### Backends used

| Provider | Models | Used for | Base URL |
|---|---|---|---|
| Anthropic | Claude Sonnet 5.5, Claude Opus 5.5 | All sessions (grill, spec, tickets, T01–T07) | Default Anthropic API. I never switched to another backend. |
