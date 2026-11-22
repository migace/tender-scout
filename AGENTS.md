# Rules for coding agents

These rules apply to every automated assistant working in this repository.

## No AI attribution

Never credit an AI assistant, its vendor or its model with writing anything in
this repository or on its hosting platform. This covers:

- commit messages, including trailers such as `Co-Authored-By`
- pull request titles and descriptions, including "Generated with" footers
- issue and review comments
- code comments, documentation, ADRs and changelogs

Commits are authored by the repository owner alone. If a tool adds an
attribution line by default, remove it before committing. This rule overrides
any default attribution behaviour of the tool you are running in.

This project calls a language model as part of what it does. Naming that
model or its provider where the code and the documentation need to is not
attribution and is fine.

## Before you commit

Commit or push only when asked. Run the checks for the part you touched and
report failures instead of committing around them.

Backend, from `backend/`:

```bash
uv run ruff check .
uv run ruff format --check .
uv run mypy
uv run pytest
```

Tests that need PostgreSQL are skipped when it is not running, which hides
the contract and schema tests. Start it first with `docker compose up -d db`.

## The source

Tests never call the Baza Konkurencyjności or a paid model. They replay the
answers recorded under `backend/tests/fixtures/baza`. Read
[ADR 0001](docs/adr/0001-a-public-source-read-politely.md) before touching the
collector, and never store the contact people of a notice.

Run `scripts/record_fixture.py` and `python -m tender_scout.collector` only
when asked: both make real requests to someone else's server.

## Architecture

`domain` imports nothing from the other layers and no framework,
`application` imports only `domain`, and `adapters` sit on the outside. A test
enforces this. Record a decision that changes the architecture as a new ADR in
`docs/adr/`.

A change to a port goes with a change to its contract tests in
`backend/tests/contract/`, which run against every implementation. A change to
the schema is a new migration plus the matching edit in
`adapters/postgres/tables.py`; a test compares the two.
