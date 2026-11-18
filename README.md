# rulecite

**Answers questions about UK financial rules by quoting the rule that answers them, with its citation, and refuses when no rule does. Measured on a test set of 150 questions.**

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
| 2 | A test set of 150 questions, each with the rules that answer it and the facts a right answer must contain | done |
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

## Milestone 2: the test set

`testset/questions.jsonl` holds 150 questions, each with the provisions that
answer it and the key facts a right answer must contain (*"eight weeks"*,
*"£35"*). They were drafted from the rule text, and a checker confirms every
rule ID exists and every key fact is in its rule. They have not been reviewed
by a second person (`make review` is there for that). 50 are kept for tuning
(dev) and 100 for the reported results (test). See [docs/testset.md](docs/testset.md).

| | fact | number | scope | multi | unanswerable | total |
|---|---|---|---|---|---|---|
| DISP | 31 | 16 | 5 | 8 | | 60 |
| BCOBS | 24 | 5 | 7 | 3 | | 39 |
| PRIN | 18 | 2 | 6 | 5 | | 31 |
| none | | | | | 20 | 20 |

*Multi* questions need two or more provisions. *Unanswerable* ones are about
rules in other parts of the Handbook (mortgages, insurance, consumer credit);
seven of them are hard negatives, where a provision in these three books uses
the same words without answering the question.

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
make testset   # checks every gold ID and key fact against the rule text
```

## Layout

```
rulecite/   the package: ids.py (provision IDs), records.py, ingest.py (PDF parser),
            testset.py (the test set and its checks),
            review.py (a tool for reviewing the questions by hand)
testset/    questions.jsonl, the 150 test questions
tests/      tests; conftest.py builds a synthetic PDF in the Handbook layout
data/       how to get the PDFs, and the snapshot the results were made with
docs/       design and results
```

## About the data

The Handbook is © the Financial Conduct Authority. Its PDFs are not included
here: each user downloads their own copy, and nothing derived from them is
committed except the short key phrases in the test set. This project is a study of question answering over regulation. It
is not legal or compliance advice.
