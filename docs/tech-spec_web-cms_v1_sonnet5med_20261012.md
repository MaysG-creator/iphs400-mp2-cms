## Problem Statement

Kenyon College Men's Soccer has no reliable place for fans, alumni, and players' families to find accurate game information. Today news comes through Instagram, which is hard to search and confusing for older relatives, and updates arrive in a random order. The team's student media members have average computer skills and need a simple way to write updates, but a wrong score or scorer on a public team site is worse than no site at all. The program needs a small CMS where several students can prepare content, one trusted person decides what goes public, and fans see a fast, readable, purple and white site that says when it was last updated.

## Solution

A local admin console (FastAPI, Jinja, SQLite) where one admin and a group of student editors log in, write updates and pages, and manage users, plus a `cms publish` step that exports only published content as static HTML for GitHub Pages. Editors can only produce drafts; the single admin reviews and publishes. The public site shows the newest updates on the home page, a navigation built from published pages (Schedule, Roster, Results/Record, History, About/Contact), and a last-updated date on everything. The admin console never goes on the internet.

## User Stories

1. As an editor, I want to log in with my own email and password, so that my work is attributed to me.
2. As an editor, I want a clear message when my password is wrong, so that I know to retry rather than think the site is broken.
3. As an admin, I want to log out, so that nobody else can use the shared machine under my name.
4. As an editor, I want to log out, so that the next editor at the shared machine signs in as themselves.
5. As an admin, I want every password stored only as a hash, so that a stolen database never reveals passwords.
6. As an editor, I want to create an update with a title and a Markdown body, so that I can write up a game quickly.
7. As an editor, I want the slug generated from the title automatically, so that I never have to think about URLs.
8. As an editor, I want a duplicate slug to be resolved automatically, so that two updates with the same title do not collide.
9. As an editor, I want a Markdown preview in the editor, so that I can check formatting before I save.
10. As an editor, I want my new content saved as a draft, so that nothing reaches fans before the admin approves it.
11. As an editor, I want to edit any draft, so that a teammate can fix a mistake on game night.
12. As an editor, I want to delete my own drafts, so that abandoned drafts do not clutter the list.
13. As an editor, I want to be blocked from deleting someone else's draft, so that nobody loses work by accident.
14. As an editor, I want to be blocked from publishing, unpublishing, or editing published content, so that live content only changes with the admin's approval.
15. As an editor, I want a clear "not allowed" screen when I try an admin-only action, so that I understand why it did not work.
16. As an editor, I want to create and edit page drafts such as Schedule, Roster, or History, so that I can prepare content for the admin.
17. As an editor, I want to filter the content list by status and by type, so that I can find drafts that need work.
18. As an editor, I want a success or error message after every save, so that I know whether my change landed.
19. As an editor, I want the admin navigation visible on every screen, so that I never get lost.
20. As an admin, I want a dashboard showing counts of drafts, published updates, and pages, so that I see what needs review at a glance.
21. As an admin, I want to filter the content list to drafts, so that I can review what editors wrote.
22. As an admin, I want to publish a draft, so that it becomes eligible for the public site.
23. As an admin, I want to unpublish published content, so that a wrong score can be pulled quickly.
24. As an admin, I want to edit published content, so that I can correct a mistake.
25. As an admin, I want to delete published content or pages, with a confirm step, so that I do not remove something live by accident.
26. As an admin, I want to set each page's nav order, so that Schedule and Results appear before History and About.
27. As an admin, I want to create a user with an email, a name, a role, and a starting password, so that a new media member can join.
28. As an admin, I want to change a user's role, so that responsibilities can change.
29. As an admin, I want to deactivate a user, so that a graduating media member can no longer log in.
30. As a deactivated user, I want my past drafts and attribution kept, so that history is not rewritten.
31. As an admin, I want the system to enforce exactly one admin, so that the club's single-admin rule is true in code.
32. As an admin, I want a hand-over action that promotes another user and demotes me in one step, so that the role can pass on when I graduate.
33. As an admin, I want to be prevented from deactivating or demoting myself outside of hand-over, so that the site is never left without an admin.
34. As an admin, I want `cms publish` to render only published updates and pages, so that drafts never leave the database.
35. As an admin, I want `cms publish` to remove content I unpublished or deleted from the exported site, so that stale content does not stay live.
36. As an admin, I want `cms deploy` to push the export to the gh-pages branch, so that fans see the new content.
37. As an admin, I want a short written runbook for publish and deploy, so that whoever inherits the role can do it.
38. As a fan, I want the home page to list the newest published updates first with their dates, so that I see the latest news.
39. As a fan, I want a navigation menu built from published pages, so that I can reach Schedule, Roster, Results, History, and About.
40. As a fan, I want each update and page to show when it was last updated, so that I can judge whether it is current.
41. As a fan, I want to read a match report with the verified score and scorers, so that I trust the numbers.
42. As an alumnus, I want a History page about past titles and accomplishments, so that I can find the program's record.
43. As a player's relative, I want a Roster page, so that I can find the player.
44. As a fan on a phone, I want the public site and admin screens to fit without sideways scrolling, so that I can read them anywhere.
45. As a fan, I want the site to look purple and white with a clear header, so that it feels like Kenyon.
46. As any visitor, I want all links to work on the hosted site, so that I never hit a broken page.
47. As any visitor, I want no script from a user's Markdown to run, so that the site is safe to open.
48. As the admin, I want every state-changing form to carry a CSRF token, so that another website cannot act on my behalf.
49. As a maintainer, I want sample content clearly marked as sample, so that no invented score ever looks real.
50. As an anonymous visitor to the admin console, I want to be sent to the login page, so that nothing is exposed.

## Implementation Decisions

- **Architecture.** Follow ADR-001 and ADR-002: a local FastAPI app with server-rendered Jinja templates and SQLite, and a publish step that writes static HTML. No frontend framework and no build step.
- **Vocabulary.** All code, templates, and tickets use the terms in `CONTEXT.md`: Update (stored as a post), Fixture, Match report, Page, Nav order, Draft, Published, Slug, Admin, Editor, Hand-over, Last updated.
- **Users.** A user has an email, a display name, a password hash (argon2), a role (admin or editor), and an active flag. Deactivation sets the flag and never deletes the user, so authorship survives.
- **Single admin.** Exactly one active admin exists at all times. Role changes cannot create a second admin, and the admin cannot demote or deactivate themselves. The only path is a hand-over action, which promotes the target and demotes the current admin atomically.
- **Content.** Updates and Pages share the same core fields: title, slug, Markdown body, status (draft or published), author, created and updated timestamps. Pages add a nav order. Only two statuses exist.
- **Slugs.** Generated from the title on first save, made unique automatically, and not editable by editors. Only the admin may change a slug.
- **Permissions.** Editor: create content as drafts, edit any draft, delete own drafts, view the content list and dashboard. Editor may not publish, unpublish, edit or delete published content, delete another editor's draft, or reach user management. Admin: everything, including publish, unpublish, edit and delete published content, and user management. Admin-only routes return 403 for editors and redirect anonymous visitors to login.
- **Session and login.** Cookie-based sessions. Login failures show one generic message. Deactivated users cannot log in.
- **CSRF.** Every state-changing form carries a token that the server verifies, and a POST without a valid token is rejected.
- **Markdown safety.** User Markdown is rendered and then sanitized with an allow-list, both in the admin preview and in the export, so script tags and event-handler attributes never execute.
- **Admin console.** A dashboard with counts, a filterable content list (by status and by type), an editor with a Markdown preview, a user list, and persistent navigation. Every save shows a success or error message. The console is not themed beyond clear, plain styling.
- **Publish.** `cms publish` reads only published rows and regenerates the export folder from scratch, so unpublished or deleted content disappears. Output uses relative paths only. The home page lists published updates newest first, the navigation is built from published pages by nav order, and each item shows its last-updated date. `cms deploy` pushes the export to the gh-pages branch. Both commands run from the terminal, and a short runbook is part of the documentation.
- **Public look.** Purple and white, with a CSS-only banner header, readable at 390 px. No image files are required.
- **Seed data.** The demo seed creates one admin, one editor, a few drafts, and a few published items. All content is clearly marked as sample, never realistic scores or stats. Credentials come from the environment.
- **Assumptions.** A deactivated user keeps authorship and content. Updates are expected about an hour after a game. Editors use one shared machine for now.

## Testing Decisions

- **What a good test is.** It asserts external behavior only: a status code, a redirect, a page's visible text, a file in the export. It never asserts on internal functions, table layouts, or template structure.
- **Seam 1: the HTTP app.** Every capability is tested through the FastAPI test client, using the existing `client` and `client_as(role)` helpers. This covers login and logout, roles and the editor 403 and anonymous redirect on every admin-only route, content CRUD and status changes, the dashboard and filters, preview, user management, hand-over, CSRF rejection, and sanitized preview output.
- **Seam 2: the publish export.** Run the exporter into a temporary folder and assert on the generated files: only published content is present, drafts are absent, unpublished content disappears on re-export, no root-absolute paths, navigation order matches nav order, sanitized bodies, and a last-updated date on each item.
- **Acceptance criteria.** Each ticket's acceptance criteria map to at least one named test so the review and grading can trace them.
- **Prior art.** The template's existing T00 test and the `client_as` fixture and its docstring examples for access-control tests.
- **Not tested.** Visual styling and the GitHub deploy itself are checked by hand and with screenshots at 1280 px and 390 px.

## Out of Scope

- Comments and moderation.
- Live in-game scores or any server-side feature on the public site.
- WYSIWYG editors, drag-and-drop page builders, and multi-site.
- Remote access for editors; for now the console runs on one machine (a later change, possibly the live admin deploy stretch).
- A "verified result" workflow or required source field for scores.
- Theming the admin console.
- Photo uploads and categories/tags are wanted but not in the core build; see Further Notes.

## Further Notes

- **Stretch goals, after the 7 core capabilities are green and reviewed:** photo uploads with alt text, and categories and tags (for example by season or opponent). Each gets its own `stretch` issue. Each is worth 1 extra-credit point and only counts if the base score is 70 or higher.
- **Core ticket plan.** The 7 required capabilities should split into 7 to 9 vertical tickets, each demoable alone and touching data, route, template, and test.
- **Accuracy rule.** The client's hard rule is that the site must never show false information. That is the reason for draft-only editors, a last-updated date, clearly marked sample content, and unpublish being fast for the admin.
- **ADR candidate.** Enforcing exactly one admin may be recorded as an ADR; this is pending the author's decision.
- **Open item outside this spec.** `notes/cms-field-notes.md` needs at least 5 observations from WordPress Playground (S1.1) before Stage 1.
