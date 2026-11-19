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
| 3 | Search: keyword, meaning-based, both combined, and re-ranking | done |
| 4 | Answers that quote the rule with its citation, and refuse when unsure | done |
| 5 | Comparison with a small local language model that writes its own answers | skipped |
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

## Milestone 3: search

Four ways of finding the provision that answers a question, all on the CPU:
keyword search (BM25), meaning search with a small embedding model
(`bge-small-en-v1.5`), the two combined (reciprocal rank fusion), and a
cross-encoder (`ms-marco-MiniLM-L6-v2`) that re-ranks the top 50 combined
results. The depth of 50 was chosen on the dev questions; the test questions
were run once. See [docs/search.md](docs/search.md).

Results on the 87 answerable test questions (percentages):

| method | right rule first | in top 5 | in top 20 | 95% interval, top 5 |
|---|---|---|---|---|
| keyword (BM25) | 41 | 76 | 91 | 67–84 |
| meaning (dense) | 52 | 80 | 90 | 71–89 |
| both (hybrid) | 49 | 80 | 95 | 72–89 |
| **re-ranked** | **59** | **87** | **97** | 80–94 |

Re-ranking finds the right rule in the top 5 for 14 test questions that
keyword search misses, and misses 4 that it finds (exact McNemar test,
p = 0.03). Its gains over the combined list and of the combined list over
either part are in the same direction but too small to tell from chance on
87 questions (p = 0.15 to 1.0). The largest gains are on questions that need
two provisions (55% to 73% in the top 5) and on whether a rule applies (75%
to 92%).

The re-ranker's score also separates the two kinds of question: the median
score of its first result is 6.0 for answerable test questions and −1.9 for
unanswerable ones. Milestone 4 uses that to decide when to refuse.

## Milestone 4: answers

An answer quotes, from each of the top two re-ranked provisions, the sentence
or short list that best answers the question, with its citation. If the best
re-ranker score is below a threshold, it refuses instead. The threshold (0.03)
was chosen on dev; the test questions were run once. See
[docs/answers.md](docs/answers.md).

```
make ask Q="What is the maximum award the ombudsman can make?"
```

Results on the 100 test questions:

| | the system | never refusing | quoting whole provisions |
|---|---|---|---|
| right (correct answer, or rightly refused) | **57%** (47–67) | 49% | 69% |
| correct answers, of 87 answerable | 48 | 49 | 60 |
| wrong answers | 37 | 38 | 25 |
| unanswerable questions refused, of 13 | 9 | 0 | 9 |
| answerable questions refused | 2 | 0 | 2 |
| median words in an answer | 79 | 84 | 158 |

Refusing gets 9 more questions right than answering everything and 1 fewer
(exact McNemar p = 0.02). The main weakness is choosing what to quote:
quoting whole provisions instead of the best piece would turn 12 wrong answers
into correct ones, at twice the length, and questions that need two
provisions are mostly wrong (2 of 11).

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
make search Q="How long do I have to cancel a new savings account?"
make search-dev    # score the search methods on dev; choose the re-ranking depth
make search-test   # score them on test, once
make ask Q="How long do I have to cancel a new savings account?"
make answer-dev    # score the answers on dev; choose the refusal threshold
make answer-test   # score them on test, once
```

`make setup` also installs PyTorch for the CPU and sentence-transformers. The
first search downloads the two models (about 220 MB) and embeds the
provisions once (about a minute and a half).

## Layout

```
rulecite/   the package: ids.py (provision IDs), records.py, ingest.py (PDF parser),
            testset.py (the test set and its checks),
            review.py (a tool for reviewing the questions by hand),
            search.py (the four search methods), metrics.py, evaluate.py,
            answer.py (quoting or refusing), answer_eval.py
testset/    questions.jsonl, the 150 test questions
results/    search and answer results on dev and test: tables (.md) and every question (.json)
tests/      tests; conftest.py builds a synthetic PDF in the Handbook layout
data/       how to get the PDFs, and the snapshot the results were made with
docs/       design and results
```

## About the data

The Handbook is © the Financial Conduct Authority. Its PDFs are not included
here: each user downloads their own copy, and nothing derived from them is
committed except the short key phrases in the test set. This project is a
study of question answering over regulation. It is not legal or compliance
advice.
