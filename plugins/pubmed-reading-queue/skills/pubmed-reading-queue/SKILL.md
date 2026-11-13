---
name: pubmed-reading-queue
description: Set up (or re-configure) a private PubMed reading queue as a claude.ai artifact, with tick-off and star buttons, and a weekly scheduled routine that adds new PubMed articles and drops old signed-off ones. Use when the user wants a PubMed reading list/digest for their own keywords, or asks to change the keywords of an existing queue.
---

# PubMed Reading Queue — setup

You build the user's own queue: a private artifact page (index.html) that loads `articles.json`, keeps sign-offs/stars in the artifact's database, and is refreshed weekly by a scheduled routine. Everything the routine needs is stored *inside the artifact* (`refresh/fetch_pubmed.txt`, `refresh/config.json`), because scheduled runs start in a fresh container.

Files in this skill folder (call it SKILL_DIR): `scripts/fetch_pubmed.py`, `scripts/build_page.py`, `assets/index.template.html`, `assets/config.default.json`, `assets/routine-prompt.md`.

Needs: the Artifact tool, the PubMed connector (mcp__PubMed__*), and permission to create a scheduled routine. If the PubMed connector is missing, tell the user to enable it before continuing.

## 1. Choose keywords (interview — do not skip)
Read `assets/config.default.json`. Show the user its `terms` and `exclude_terms` as bullet lists, and say these are the author's defaults (mechanical ventilation / NIV / HFNC / PEEP / EIT / transpulmonary pressure, pediatrics excluded). Ask, in one question:
- keep these as they are, remove some, or replace them entirely?
- any terms of their own to add (plain phrases are fine; you quote them)?
- anything to exclude (e.g. a population)?
- journals to flag as "high-impact"? (default list is critical-care journals; suggest ones for their field, as NLM abbreviations)
- topic categories for the dropdown? (name + words that identify it; suggest sensible ones from their terms)
- a queue name for the page title.
Wait for the answers. Never assume the defaults silently.

## 2. Write the config
Copy `config.default.json` to a working folder (e.g. `./pqr/config.json`) and edit: `queue_title`, `eyebrow`, `terms` (PubMed expressions; wrap phrases in escaped quotes), `exclude_terms`, `exclude_regex` (words that, in a title/journal, drop an article after search; use "" for none), `exclusion_note`, `categories` ([name, regex] pairs, first match wins), `high_impact`, `high_impact_prefixes`, optional `lede_extra`.
Run `python3 -I SKILL_DIR/scripts/fetch_pubmed.py query --config pqr/config.json` and show the user the resulting PubMed query. Get a yes before continuing; adjust if they want.

## 3. First fetch
`python3 -I SKILL_DIR/scripts/fetch_pubmed.py update pqr/articles.json --init-days 60 --config pqr/config.json`
If NCBI is unreachable (sandbox proxy), use the connector: search_articles with the query (datetype 'edat', last 60 days, max_results 100, paging with retstart), get_article_metadata in batches of 20, save the returned `articles` entries unchanged as pqr/connector.json, check the count matches, then run the same command with `--import pqr/connector.json`. If the query is too complex for the connector, run it as two halves and combine PMIDs.
Report how many articles came back. If zero or enormous (>2000), propose narrowing/widening terms before publishing.

## 4. Build and publish
- `python3 -I SKILL_DIR/scripts/build_page.py SKILL_DIR/assets/index.template.html pqr/config.json pqr/index.html`
- Copy `scripts/fetch_pubmed.py` to `pqr/refresh/fetch_pubmed.txt` and `pqr/config.json` to `pqr/refresh/config.json`.
- Load the `artifact-design` and `artifact-capabilities` skills. The page uses the **db** capability (`window.claude.use("db")`, collections `status` and `starred`, documents `<YYYY-MM>` shaped `{items:{pmid: epochMs}}`). Declare it per the capabilities skill. Do not change the page HTML beyond the template placeholders.
- Artifact publish: file_path pqr/index.html, `files` = {articles.json, refresh/fetch_pubmed.txt, refresh/config.json}, icon "book" or similar. Keep it private. Note the artifact URL.

## 5. Schedule the weekly routine
Take `assets/routine-prompt.md`, replace `{{ARTIFACT_URL}}`, `{{QUEUE_NAME}}` and `{{QUERY}}` (the query from step 2), and create a weekly scheduled routine (Mondays, morning) with that text as its prompt, using the scheduling tool/skill available in this session (e.g. CronCreate or /schedule). Confirm the schedule with the user. If you cannot create it, give them the filled prompt to paste into a routine at claude.ai/code/routines.

## 6. Hand over
Tell the user: the artifact link, that sign-offs are saved in the page's database, how to change keywords later (re-run this skill and say "reconfigure": it re-reads `refresh/config.json` from the artifact, edits it, rebuilds the page if categories changed, republishes, and updates the routine's query line), and that signed-off articles disappear 30 days after sign-off.

## Reconfigure mode
Read the artifact (`refresh/config.json`, `index.html`), redo steps 1–2 against the existing config, republish with the new config and, if categories or title changed, a rebuilt index.html. Never delete database rows.
