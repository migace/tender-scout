# Tender Scout

Reads requests for quotation from Poland's Baza Konkurencyjności, turns the
conditions of each one into a structure a person can check, and says how well
it fits a given company. Every claim it makes points at the sentence in the
notice it came from.

> **Status: the first of six stages is built.** Open notices for training
> services are collected into PostgreSQL, slowly and without the people named
> in them: a run on 22 November 2026 read 105 notices with 109 requests in four
> minutes. Nothing reads them with a model yet. See the [roadmap](#roadmap).

## The problem

Organisations that spend European funds in Poland publish their requests for
quotation in the [Baza Konkurencyjności](https://bazakonkurencyjnosci.funduszeeuropejskie.gov.pl/):
44,684 notices in 2025. The Base can be searched by category, place and CPV
code. Whether a company can actually bid is a different question, and the
answer sits in free text: how many similar contracts it must have completed,
what its trainers must have done, what share of the score is the price.

A small company reads dozens of notices to find the few it qualifies for. This
project does the first reading.

The first niche is training services (CPV 80500000-9 and 80000000-4): 3,764
notices in 2025, and 88 open ones under the first code on 22 November 2026.
It is narrow enough to label by hand and wide enough to matter.

## What it will do

1. **Collect** open notices from the Base's public search, a few requests at a
   time, and keep them in PostgreSQL with the date they were read. *Built.*
2. **Extract** the conditions of taking part and the scoring criteria into a
   typed structure: required experience, required people, money thresholds,
   criteria and their weights, deadlines.
3. **Match** a notice against a company profile and say which conditions are
   met, which are not, and which cannot be told from the notice.
4. **Show** the notice next to what was read from it, with each extracted
   field linked to its source sentence, so a person can confirm or correct it.

## What is interesting here

### Built, and backed by a test

**The source is someone else's server, and the code cannot forget it.** One
request at a time, a pause before each one after the first, and a ceiling of
requests for a run. The pause can be configured longer but not below a second.
A run that reaches its ceiling stops, and the next one carries on from what is
already kept: a notice is opened again only when its listing changed or its
reading is a week old.
See [`test_collect.py`](backend/tests/unit/test_collect.py) and
[`test_source.py`](backend/tests/unit/test_source.py).

**No contact person is stored, because no line of code names one.** The
parser copies nothing wholesale: a field reaches a notice only when a line
asks for it. Every recorded answer used in the tests carries an invented
contact person, and the tests look for that person in the parsed notice and in
every column of the database row. E-mail addresses and phone numbers typed
into free text are replaced with a mark. Names typed into free text are not
found, and [ADR 0001](docs/adr/0001-a-public-source-read-politely.md) says so.

**An undocumented source fails loudly and says where.** The Base has no
published contract, so every field is read through an accessor that knows its
own address in the answer. A missing or mistyped field stops the run with a
message such as `notice.data.advertisement.orders[0].order_items[0].participation_conditions is missing`.

**Tests never call the Base.** They replay answers recorded once by a script
that takes the people out first. The files say where they came from, when,
and how they were changed, as the Base's rules of use ask.

**The fake cannot drift from the database.** One set of contract tests runs
against the in-memory store and against PostgreSQL, including a real notice
with thousands of characters of conditions going in and coming back equal.

**The architecture is enforced by a test.** The domain imports no framework
and no outer layer, and the build fails if it starts to.

### Intended, not built

These become claims only when a test backs them.

**The model is not trusted.** Every extracted field will carry the quote it
was read from, and code will check that the quote is in the notice. A field
without a real quote is dropped, not shown.

**Quality is a number, and CI guards it.** A set of notices labelled by hand
gives precision and recall for each field. A change that makes them worse
fails the build, the same way a failing unit test does.

**A notice is untrusted input.** Anyone can publish one, so its text may try
to instruct the model. The test suite will include notices written to do
exactly that.

**The cost of a reading is known.** Each call records its tokens, its price
and its latency, and the evaluation report gives cost per notice next to
quality, so a cheaper model can be judged on both.

**The public demo cannot run up a bill.** Visitors see readings made ahead of
time. Nothing an anonymous visitor does calls a paid API.

## The data source

The Base has no documented API. Its own search page reads a public JSON
endpoint without signing in, and this project reads the same one.

The Base's rules of use (the version published on 13 May 2026) allow using its
content for other purposes on three conditions: name the Ministry of Funds and
Regional Policy as the source, give the date the information was obtained, and
say that it was processed. They also forbid anything that could hinder the
Base. So the collector is slow on purpose, keeps what it has read instead of
asking again, and every notice is stored with the moment it was read.

Notices contain the names, phone numbers and e-mail addresses of contact
people. They are not stored.
[ADR 0001](docs/adr/0001-a-public-source-read-politely.md) has the reasoning.

## Stack

Python 3.12, SQLAlchemy 2 (async) and Alembic on PostgreSQL 17, httpx, uv,
Ruff, mypy in strict mode, pytest. CI runs all of it on every pull request.

Planned for later stages, the same as in
[Tutor Calendar](https://github.com/migace/tutor-calendar) where the problem
is the same: FastAPI, `pgvector` beside PostgreSQL's own full-text search,
React with TypeScript. The model provider is not chosen yet.

## Develop it

```bash
docker compose up -d db
```

```bash
cd backend && uv sync && uv run alembic upgrade head
```

PostgreSQL listens on port 5433, so it can run beside another project's
database. Settings are `TS_*` environment variables or a `.env` file; see
[`config.py`](backend/src/tender_scout/config.py).

One collection run:

```bash
cd backend && uv run python -m tender_scout.collector
```

This makes real requests to the Base: up to 300 of them, two seconds apart.
It prints one line of JSON saying what it did.

## Test it

```bash
cd backend && uv run pytest
```

Tests marked `integration` need the database from `docker compose up -d db`.
They create and migrate a database of their own, `tender_scout_test`, and
leave collected notices alone. Without PostgreSQL they are skipped locally and
fail in CI. No test makes a request to the Base.

## Layout

```
backend/
  src/tender_scout/
    domain/          a notice, when to read one again, what is never kept
    application/     the collecting use case and the ports it needs
    adapters/
      baza/          the Base's JSON, parsed and fetched
      postgres/      tables and the notice store
      in_memory_*    the fake the fast tests use
    collector.py     one collection run, from the command line
  migrations/        written by hand; a test compares them with the tables
  scripts/           recording answers of the Base for the tests
  tests/
    unit/  contract/  integration/  fixtures/baza/
docs/adr/            why things are the way they are
```

## Roadmap

Each stage ends with something that runs and a test that would fail without it.

| # | Stage | Done when | |
|---|-------|-----------|---|
| 1 | Collect | Open training notices are in PostgreSQL, read at a fixed slow rate, with no contact people and with the date of reading. Recorded responses drive the tests. | done |
| 2 | Extract | Conditions and criteria come out as a typed structure, each field with a quote that code has found in the notice. | |
| 3 | Measure | A hand-labelled set, a report of quality and cost per field, and a CI check that fails when quality drops. | |
| 4 | Match | A company profile gives met, not met and unknown for each condition; similar notices are found by meaning and by words. | |
| 5 | Review | A screen with the notice beside its reading; a correction made there becomes a new labelled example. | |
| 6 | Harden and show | Notices written to hijack the model are in the tests, spending has a cap, and a demo runs on readings made ahead of time. | |

## What is not done

- **Attachments are not read.** Many notices keep details in PDF or Word
  files, and some keep all of them there. Of the 105 notices collected on
  22 November 2026, 29 have no condition longer than 80 characters; in the
  one recorded for the tests, every condition is the same sentence pointing
  at the attachments. The first version reads the notice's own fields and
  will say when a condition points away.
- **A closed notice is not noticed.** The collector lists open notices. One
  that closes simply stops being listed and keeps its last status here; its
  deadline is what tells that it is over.
- **An edit to the conditions alone can go unseen for a week.** The search
  result has no modification date. See ADR 0001.
- **Names in free text stay.** Only addresses and phone numbers are replaced.
- Nothing writes or submits offers, and nothing here is legal advice on
  whether a company may bid.

## License

[MIT](LICENSE).
