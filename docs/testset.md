# The test set

`testset/questions.jsonl` holds 150 questions about DISP, BCOBS and PRIN, each
with the provisions that answer it. Every number this project reports (how
often search finds the right rule, how often an answer is right, how often the
system refuses when it should) is measured on these questions. Without them,
"it seems to work" is the best anyone could say.

## One question

```json
{"id": "q001",
 "question": "How long does a firm have to send its final response to an ordinary complaint?",
 "category": "number", "book": "DISP",
 "gold": ["DISP 1.6.2"], "key_facts": ["eight weeks"],
 "split": "test", "status": "draft", "note": ""}
```

| Field | What it holds |
|---|---|
| `id` | `q001` to `q150` |
| `question` | the question in plain words, written for this set, not copied from a rule |
| `category` | what kind of question it is (below) |
| `book` | the sourcebook that answers it; `null` for an unanswerable question |
| `gold` | the provisions that answer it, best first |
| `key_facts` | short phrases that a correct answer must contain, copied from the gold text |
| `split` | `dev` (50 questions, for tuning) or `test` (100, for the reported results) |
| `status` | `draft`; `checked` or `flagged` once someone reviews it with `make review` |
| `note` | why the gold is what it is, or where the answer to an unanswerable question lives |

## Five kinds of question

Each category tests a different way an answer can go wrong.

| Category | Example | What it catches |
|---|---|---|
| `fact` | *Can a firm charge a customer for making a complaint?* | the basic case: find the one rule and quote it |
| `number` | *How long does a customer have to cancel a new bank account?* | a wrong number is the most harmful mistake, and an easy one: DISP alone has eight-week, six-month, six-year and three-year limits |
| `scope` | *Can a customer cancel a fixed-rate savings account during the cooling-off period?* | exceptions and "does this apply?"; the rule that states the general case is usually a closer match than the exception |
| `multi` | *How long does a customer have to cancel, and how quickly must the bank repay them?* | needs two or more provisions; one search result is not enough |
| `unanswerable` | *What is the daily cap on interest and fees for payday loans?* | the system should say it cannot answer, not quote the nearest rule |

| | fact | number | scope | multi | unanswerable | total |
|---|---|---|---|---|---|---|
| DISP | 31 | 16 | 5 | 8 | | 60 |
| BCOBS | 24 | 5 | 7 | 3 | | 39 |
| PRIN | 18 | 2 | 6 | 5 | | 31 |
| none | | | | | 20 | 20 |
| **total** | 73 | 23 | 18 | 16 | 20 | **150** |

`make testset` prints the same table with the dev count of each cell in brackets.

## How gold and key facts are chosen

* **Gold** is the provision a careful reader would point to. For `fact`, `number`
  and `scope` questions the first gold provision answers the question on its
  own; any others listed are alternatives that answer it just as well. For a
  `multi` question every gold provision is needed.
* **Key facts** are the few words that make an answer right: `"eight weeks"`,
  `"£35"`, `"for the firm to prove"`. They are copied exactly from the rule, at
  most ten words each, so they can be checked by a program: an answer that does
  not contain them is wrong, whatever else it says.
* `python -m rulecite.testset` checks every gold ID against
  `data/processed/rules.jsonl` and every key fact against the gold text. For a
  `fact`, `number` or `scope` question all key facts must be in every gold
  provision. For a `multi` question each key fact must be in one of them and
  each gold provision must hold at least one key fact; otherwise it is not
  really needed.
* Questions use everyday words ("bank", "cancel", "ombudsman") where the rules
  use defined terms ("firm", "right to cancel", "Financial Ombudsman
  Service"). This is deliberate: a search that only matches identical words
  should not look better than it is.

## Unanswerable questions

The 20 unanswerable questions are about rules that exist, just not in these
three books: mortgage affordability (MCOB), the payday loan price cap (CONC),
deposit protection (the PRA Rulebook), insurance (ICOBS), anti-money
laundering, and so on. Seven of them are **hard negatives**: a provision in the
three books uses the same words without answering the question. For example,
BCOBS 6.1.1 gives a 14-day cancellation right for bank accounts, which looks
like an answer to *"How long is the cooling-off period for a consumer credit
agreement?"* but is not. These are the questions that show whether the
refusal threshold works.

The note on each says where the answer actually lives. The review tool shows
the three provisions sharing the most rare words with the question, so the
checker can confirm that none of them answers it.

## Dev and test

The questions are split 50 dev and 100 test, in the same proportions of book
and category (`assign_splits`, seed 2026, so the split can be remade exactly).

* **dev** is for choosing things: the search weights, the refusal threshold,
  the prompt for the local model. Look at these questions as often as needed.
* **test** is for the reported numbers, and is run once a choice is final.
  Tuning on the test questions would make the results look better than they
  would be on new questions.

## How the questions were checked

Each question was drafted while reading the full text of its gold provisions.
Then `python -m rulecite.testset` checked every one automatically: each gold ID
exists, each key fact is really in the gold text, every field is valid, and the
split is the one `assign_splits` makes. All 150 pass.

The questions have **not** been reviewed by a second person, so every status
is still `draft`. The review tool is there for that: `make review` shows each
question with its gold provisions in full and the key facts highlighted, and
asks:

| Key | Meaning |
|---|---|
| `c` | correct: the question is clear, the gold answers it, and the key facts are what a right answer must say |
| `f` | flag a problem, with a note saying what is wrong |
| `e` | change the wording of the question, then decide |
| `s` / `b` | skip ahead / go back |
| `q` | stop; every answer so far is saved, and the next run starts at the first draft |

What to look for:

1. Could someone who only reads the question know what is being asked?
2. Does the first gold provision really answer it? Is there a better one in
   the same section?
3. Would an answer without the key facts be wrong? Would an answer with them
   be right?
4. For unanswerable questions: does any of the nearest provisions answer it
   after all?

Flagged questions are fixed and looked at again (`python -m rulecite.review
--flagged`) until none are left.

## Limits

* **No independent review.** The automatic checks show that every gold ID and
  key fact is in the rules, but not that each question is clear or that its
  gold is the best provision. One person drafted them and nobody else has
  reviewed them, so some questions may be ambiguous or have a better answer
  elsewhere, which would make every method look slightly worse than it is.
* **The questions were written by people who had read the rules.** Real users
  phrase things differently and ask vaguer questions, so results here are
  likely to be better than results on real questions.
* **100 test questions give rough numbers.** A score of 70% on 100 questions
  could be anything from about 61% to 79% (95% confidence interval). Two
  systems a few points apart may not really differ; milestone 3 tests whether
  they do.
* **The IDs belong to one version of the Handbook** (the snapshot in
  `data/snapshot.json`). If the FCA renumbers a provision, `make testset`
  reports the gold ID as missing.
* **Some amounts change every year.** DISP 3.7.4R states the ombudsman's award
  limits as base amounts that are raised each April in line with inflation.
  The key fact is the amount in the rule text, and the note on those questions
  says so.

The test set stores rule IDs and short key phrases only, never the rule text
itself.
