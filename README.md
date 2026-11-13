# PubMed Reading Queue (Claude Code plugin)

A private reading list of new PubMed articles for **your** keywords, as a claude.ai artifact with star / sign-off buttons, refreshed weekly by a scheduled Claude routine.

## Install
In Claude Code:

    /plugin marketplace add <github-user>/<this-repo>
    /plugin install pubmed-reading-queue@pubmed-reading-queue

(Private repo: you must have access and be signed in to GitHub, e.g. `gh auth login`.)

## Requirements
Claude Code with artifacts, the **PubMed connector** enabled, and scheduled routines (claude.ai/code/routines).

## Use
Say **"set up my PubMed reading queue"**. Claude shows the example keywords (ventilation topics) as defaults, lets you accept, trim or add your own, previews the PubMed query, fetches a first batch, publishes your artifact and schedules the weekly refresh. Later: "reconfigure my PubMed reading queue".

## How it works
The artifact holds `index.html`, `articles.json`, `refresh/fetch_pubmed.txt` and `refresh/config.json`. The weekly routine reads those, adds new articles (NCBI directly, or the PubMed connector if NCBI is blocked), prunes articles signed off >30 days ago, and republishes. It only reads your sign-offs; it never writes to the database.
