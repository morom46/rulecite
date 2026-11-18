# rulecite

**Answers questions about UK financial rules by quoting the rule that answers them, with its citation, and refuses when no rule does. Measured on a hand-checked test set.**

A question such as *"How long does a bank have to send a final response to a
complaint?"* should get the sentence from the FCA Handbook that says so, and
where it is: *"...by the end of eight weeks after its receipt of the complaint
[DISP 1.6.2R]"*. Not a paraphrase, and never a rule that does not exist.

The system covers three sourcebooks of the FCA Handbook:

* **DISP**, how firms must handle complaints,
* **BCOBS**, how banks must deal with their customers,
* **PRIN**, the Principles for Businesses, including PRIN 2A, the Consumer Duty.

Everything runs on a laptop CPU, with no paid API and no account.

## Status

| # | Milestone | Status |
|---|---|---|
| 1 | Parse the three sourcebooks into one record per provision | done |
| 2 | A test set of 150 questions, each checked by hand against the rule text | planned |
| 3 | Search: keyword, meaning-based, both combined, and re-ranking | planned |
| 4 | Answers that quote the rule with its citation, and refuse when unsure | planned |
| 5 | Comparison with a small local language model that writes its own answers | planned |
| 6 | Failure analysis and a demo page | planned |

## Milestone 1: the rules as data

`make ingest` reads the three PDFs and writes 1,176 provisions to
`data/processed/rules.jsonl`. Each record has the provision's ID and type
(rule or guidance), its chapter, section and subheading, its text with list
items and table rows kept apart, the provisions it refers to, and the Glossary
terms it uses. See [docs/data.md](docs/data.md) for the record format, how the
parser reads the PDF layout, and what it gets wrong.

| Book | Provisions | Rules (R) | Guidance (G) |
|---|---|---|---|
| DISP | 700 | 271 | 357 |
| BCOBS | 242 | 145 | 90 |
| PRIN | 234 | 115 | 112 |

## Quick start

Needs Python 3.11 or newer.

```
make setup     # .venv with the pinned packages
make test      # parser tests on a synthetic PDF
```

Then download the three PDFs as described in [data/README.md](data/README.md)
and run:

```
make ingest    # about two minutes
make test      # now also runs the checks on your real data
```

## Layout

```
rulecite/   the package: ids.py (provision IDs), records.py, ingest.py (PDF parser)
tests/      tests; conftest.py builds a synthetic PDF in the Handbook layout
data/       how to get the PDFs, and the snapshot the results were made with
docs/       design and results
```

## About the data

The Handbook is © the Financial Conduct Authority. Its PDFs are not included
here: each user downloads their own copy, and nothing derived from them is
committed. This project is a study of question answering over regulation. It
is not legal or compliance advice.
