# Answers

Milestone 4 turns search into answers. An answer is made only of words from
the rules, each quote followed by its citation, and the system refuses when it
is not confident that any provision answers the question.

```
make ask Q="How long do I have to cancel a new savings account?"
```

## How an answer is made

1. **Search.** The milestone 3 pipeline: BM25 and dense search, fused, and the
   top 50 re-ranked by the cross-encoder.
2. **Refuse or answer.** If the best re-ranker score is below the threshold,
   the reply is *"No provision in DISP, BCOBS or PRIN clearly answers this"*,
   with the best score shown.
3. **Quote.** From each of the top two provisions that clear the threshold,
   the provision is cut into pieces (sentences and list items, without the
   editorial notes) and the cross-encoder scores each piece against the
   question. The best piece is quoted. If it belongs to a list of at most 150
   words, the whole list is quoted with its lead-in, so that *"what must a
   final response include?"* gets every item; for a longer list, the lead-in
   and the best item.

Two quotes are allowed because some questions need two provisions, and
because the right provision is often second (see below).

For nearly every answerable question this format *can* hold the answer: for
129 of the 130, one quoted piece of the gold provision (or one per gold
provision, for multi questions) contains every key fact. The test in
`tests/test_real_data.py` checks this.

## How it is scored

Each question ends in one of five outcomes:

| question | outcome | meaning |
|---|---|---|
| answerable | correct | answered, and the answer contains every key fact |
| | wrong | answered, but a key fact is missing |
| | refused | no answer, though there was one |
| unanswerable | refused | the right outcome |
| | answered | quoted something that cannot be the answer |

**Accuracy** is the share of all questions that are correct or rightly
refused. Matching key facts is strict: an answer that quotes the right rule
but the wrong sentence of it counts as wrong.

## Choosing the threshold on dev

Accuracy only changes when the threshold passes one of the questions' top
scores, so the candidates are the points between them. On dev the best
accuracy, 70%, held for every threshold from −2.24 to 0.58, and the middle,
**0.03**, was saved to `results/answers-choice.json`. A wide flat range means
the choice does not hang on one or two questions.

## Results

Full tables: [results/answers-dev.md](../results/answers-dev.md) and
[results/answers-test.md](../results/answers-test.md); every question's
outcome and quotes are in the `.json` files beside them.

**Test, 100 questions (87 answerable, 13 unanswerable), threshold 0.03:**

| | the system | never refusing | quoting whole provisions |
|---|---|---|---|
| accuracy (right / all) | **57%** | 49% | 69% |
| correct answers | 48 | 49 | 60 |
| wrong answers | 37 | 38 | 25 |
| answerable but refused | 2 | 0 | 2 |
| unanswerable, rightly refused | 9 of 13 | 0 of 13 | 9 of 13 |
| correct among answered | 54% | 49% | 67% |
| median words in an answer | 79 | 84 | 158 |

The 95% bootstrap interval for accuracy is 47% to 67%.

| right, by kind of question | fact (49) | number (15) | scope (12) | multi (11) | unanswerable (13) |
|---|---|---|---|---|---|
| % | 61 | 67 | 50 | 18 | 69 |

### What the results show

* **Refusing works, and costs little.** It refuses 9 of the 13 unanswerable
  test questions while refusing only 2 of the 87 answerable ones. Against
  answering everything, it gets 9 more questions right and 1 fewer (exact
  McNemar p = 0.021).
* **The threshold held up on new questions.** Over the test thresholds the
  best accuracy is 58% (at 2.0), against 57% at the threshold chosen on dev.
  Raising it further refuses answerable questions faster than it saves wrong
  answers: at 6.0 it answers less than half the questions.
* **Most errors are wrong quotes, not wrong refusals.** 37 of the 87
  answerable test questions get an answer that misses a key fact. They come
  from two places:
  * *the right provision is not in the top two.* Search puts it first for 59%
    of test questions and in the top three for 79% (milestone 3), and only
    the top two are quoted;
  * *the right provision, the wrong piece.* Quoting whole provisions instead
    of the best piece turns 12 of those wrong answers into correct ones (48
    to 60 correct), at twice the length. The cross-encoder was trained to
    match questions to passages, and it does worse at choosing between
    sentences of one provision. For example, for *"How long do I have to
    cancel a new savings account?"* it picks, from BCOBS 6.4.2R, the sentence
    *"This period begins from the day on which…"*, which says nothing on its
    own.
* **Questions that need two provisions mostly fail** (2 of 11 right): both
  provisions have to be in the top two and both pieces have to be right.
* **Dev was easier than test.** Accuracy was 70% on dev and 57% on test, and
  all 7 unanswerable dev questions were refused against 9 of 13 on test. With
  50 dev questions, a gap like this is within what chance can produce, and it
  is why the reported numbers come from test.

**Speed.** 3.8 seconds a question on the CPU (378 s for 100), most of it the
cross-encoder reading 50 provisions and then the pieces of the top two.

## Limits

* **"Contains the key facts" is not "a good answer".** An answer can contain
  them inside a second, longer quote after a misleading first one, and still
  count as correct; a reader would be confused. Milestone 6 looks at such
  answers by hand.
* **Refusing is decided on the best score alone**, one number from a model
  that was not trained on regulation. Four unanswerable test questions still
  got an answer.
* **No negations or conditions are checked.** If a rule says *"does not
  apply where…"*, the quote includes those words, but nothing checks that the
  question's situation meets them.
* The threshold was tuned on 50 dev questions, 7 of them unanswerable; a
  different set of 50 could move it.
