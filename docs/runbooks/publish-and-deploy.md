# Runbook: publish and deploy

For whoever holds the **admin** role. Editors cannot do these steps.

Live site: <https://maysg-creator.github.io/iphs400-mp2-cms/>

Publishing is three steps. Marking an update published in the admin console
does not change the live site by itself. Fans see the change only after steps 2
and 3.

## 1. Publish (or unpublish) in the admin console

```bash
uv run --env-file .env cms serve
```

1. Open <http://localhost:8000/admin> and log in as the admin.
2. Go to **Updates** and open the update.
3. Read it once more. Check every score and scorer against a trusted source.
   A wrong score on the team site is worse than no update.
4. Click **Publish**. The status changes to *Published*.

To pull an update (for example, a wrong score), open it and click
**Unpublish**. It goes back to being a draft.

## 2. Rebuild the site

In a second terminal, from the repo folder:

```bash
uv run --env-file .env cms publish
```

This rebuilds `site/` from scratch with only the published updates and pages. Anything
unpublished since the last run is removed. Never edit `site/` by hand: the next
run overwrites it.

Optional check before going live:

```bash
python3 -m http.server -d site 8001
```

Open <http://localhost:8001>. The home page lists published updates, newest
first, each with its last-updated date. No draft should appear.

## 3. Deploy

```bash
uv run --env-file .env cms deploy
```

This pushes `site/` to the `gh-pages` branch. GitHub Pages usually shows the
change within a few minutes. Reload the live site to confirm.

## If something goes wrong

| Symptom | Fix |
|---|---|
| The live site still shows old content | You skipped step 2 or 3. Run both again. |
| A draft is on the live site | That is a bug. Unpublish anything wrong, run steps 2 and 3, and open an issue. |
| `site/ does not exist yet` | Run step 2 first. |
| `cms deploy` is rejected by GitHub | Run `gh auth status`. If you are not logged in, run `gh auth login`. |
| The site returns 404 after 10 minutes | On GitHub: **Settings → Pages → Deploy from a branch → `gh-pages` / root**. |
