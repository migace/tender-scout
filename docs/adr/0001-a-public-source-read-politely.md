# 1. A public source, read politely, without the people in it

Date: 2026-11-22

## Context

The project needs real requests for quotation. The Baza Konkurencyjności
publishes them, but offers no documented API and no bulk download.

What was checked on 22 November 2026, without signing in:

- The search page of the Base reads `GET /api/announcements/search`. It
  answers with JSON when a status filter is given (`status[]=PUBLISHED`) and
  with an error when it is not. It reported 1,037 open notices, 88 of them
  under CPV 80500000-9.
- `GET /api/announcements/{id}` returns one notice in full: orders, items,
  CPV codes, places, conditions of taking part, scoring criteria, deadlines
  and a list of attachments. The conditions are free text, often thousands of
  characters long.
- The same answer contains the contact people of the buyer: forename, surname,
  phone number and e-mail address.
- The rules of use, in the version published on 13 May 2026, say that someone
  who uses the Base's content for a purpose other than the Base's own must
  follow the Ministry's conditions for reusing public sector information:
  name the Ministry as the source, give the date the information was
  obtained, and say whether it was processed. They also forbid "any activity
  that may hinder the operation of the Base".
- The site serves no `robots.txt`.

## Decision

Read the same public endpoints the Base's own page reads, under these rules:

1. **Slowly.** One request at a time with a pause between requests, a fixed
   ceiling per run, and a user agent that names the project. The pause can be
   made longer by configuration but not shorter than one second. A search
   result carries no modification date, so a notice already stored is opened
   again only when the title or the deadline in the result differs from what
   is kept, or when the kept reading is more than a week old.
2. **With its origin.** Every stored notice keeps the time it was read. Every
   screen and export that shows a notice names the Ministry of Funds and
   Regional Policy as the source, gives that time, and says the content was
   processed.
3. **Without the people.** Contact people are removed before a notice is
   stored, and so are the identifiers of the accounts that created or changed
   it. The buyer's name and tax number stay: they identify an organisation
   and are the point of a public notice. E-mail addresses, and numbers the
   text itself calls a phone number, are replaced with a mark wherever a
   buyer typed them into free text.
4. **Without attachments, for now.** Attachments are listed by name but not
   downloaded in the first version.
5. **Tests never touch the Base.** They run on recorded responses kept in the
   repository, with the contact people already removed.

## Consequences

- The endpoint is undocumented and can change without notice. The collector
  is one adapter behind a port, and a contract test on recorded responses
  shows at once which field moved.
- Collection is slow. A first load of a few thousand notices takes hours, not
  minutes. That is acceptable: 44,684 notices in 2025 is about 120 a day
  across all categories, and the first niche is a small part of that.
- A buyer that happens to be a sole trader is identified by name in the
  notice itself. That is published by the buyer under the Base's rules and is
  kept; phone numbers and e-mail addresses are not.
- A name typed into free text stays. Finding names in Polish prose reliably
  is a problem of its own, and a filter that is right most of the time would
  be described as one that works. The mark for an address or a phone number
  also changes the text a little, so a quote from a notice is checked against
  the kept text, never against the Base's.
- An edit that changes only the conditions of a notice goes unnoticed for up
  to a week. Noticing it sooner would mean opening every open notice on every
  run, which is the load this decision exists to avoid.
- If the Ministry objects to this use or publishes an API, this decision is
  replaced, not patched.

## Not chosen

- **Scraping the rendered pages.** Slower for the Base and more fragile for
  us than reading the JSON its own page reads.
- **e-Zamówienia or TED instead.** Both have documented APIs, and both cover
  public procurement under the procurement act, where notices are longer,
  more formal and already served by many paid tools. The gap this project is
  about is the smaller buyer below those thresholds.
- **A synthetic data set.** It would make the evaluation meaningless: the
  difficulty is in how real buyers write.
