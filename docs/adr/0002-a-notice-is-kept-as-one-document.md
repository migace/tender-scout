# 2. A notice is kept as one document

Date: 2026-11-22

## Context

A notice is a tree: orders, their items and scoring criteria, the items'
conditions, places and CPV codes. The recorded notices have one to four
orders and up to seven conditions on an item.

Two things are known about how it will be used. It is read and shown whole:
the extraction of stage 2 takes a notice and reads all of its conditions, and
the review screen of stage 5 shows a notice beside what was read from it. And
it is filtered by a few plain facts: its CPV codes, its deadline, its status.

Nothing so far updates one condition, or asks for all conditions of a kind
across notices.

## Decision

One table, `notices`, with one row for each notice:

- a JSONB column, `body`, holding the whole notice in this project's own
  shape (not the Base's), enough on its own to rebuild it;
- plain columns beside it for what queries filter and sort by: `cpv_codes`
  (an array with a GIN index), `deadline`, `status`, `published_on`, and the
  title and buyer for listing;
- `read_at`, the moment the reading was taken, which the Base's rules of use
  ask to be shown.

The document carries a `shape` number. A change to what a notice is gets a
new number and a branch where documents are read, so rows written earlier
stay readable without a migration that rewrites them.

A new reading of a notice replaces the old one in a single statement.

Times are stored as instants. The Base prints Polish wall-clock times with no
zone; the adapter that reads it attaches `Europe/Warsaw` and the rest of the
code never sees a time without a zone.

## Consequences

- Saving and loading a notice is one row, and the contract tests check that a
  real notice comes back equal to what was saved.
- The columns repeat facts that are also in the document. They are written
  from the same notice in the same statement, so they cannot drift apart.
- Only the latest version of a notice is kept. A reading made by the model in
  stage 2 will record which version it read, so a reading of an edited notice
  can be told to be out of date. If the history of edits turns out to matter,
  the key becomes notice and version, which is a migration, not a redesign.
- A question such as "every experience condition in the last year" needs
  JSON path queries or a table of its own. When a stage needs it, that stage
  adds the table; guessing its shape now would be guessing.

## Not chosen

- **A table for each level** (orders, items, conditions, criteria, places).
  It is the textbook shape and would cost five tables and a join tree for a
  thing that is always handled whole.
- **Keeping the Base's answer as it came.** It would put contact people in
  the database, against ADR 0001, and tie every later stage to an
  undocumented format.
