# Search

Before the system can quote a rule, it has to find it. Milestone 3 compares
four ways of finding the provision that answers a question, all running on a
laptop CPU, and measures each one on the test set.

```
make search Q="How long do I have to cancel a new savings account?"
```

## The four methods

**1. Keyword search (BM25).** Each provision is turned into a list of words:
lower case, common words such as *the* and *which* dropped, and endings removed
so that *cancel*, *cancelled* and *cancellation* count as the same word
(Snowball stemmer). A provision scores higher the more of the question's words
it contains, with three adjustments:

* a rare word counts for more than a common one (*idf*: a word in 5 of the
  1,176 provisions says much more than one in 500);
* the tenth use of a word adds less than the first (`k1 = 1.5`);
* a long provision is held back a little, since it contains more words by
  chance (`b = 0.75`).

BM25 is fast and exact: it never misses a provision that uses the question's
own words. It fails when the question and the rule say the same thing in
different words, which is common here: people ask about a *bank* and a
*savings account*, the rules say *firm* and *retail banking service*.

**2. Meaning search (dense).** A sentence-embedding model,
[`BAAI/bge-small-en-v1.5`](https://huggingface.co/BAAI/bge-small-en-v1.5)
(33 million weights, 130 MB), turns each provision into a list of 384 numbers,
a vector, so that texts with similar meanings get vectors pointing in similar
directions. The question gets a vector the same way, and provisions are ranked
by the cosine of the angle between their vector and the question's. The model
was trained so that a query prefixed with *"Represent this sentence for
searching relevant passages:"* lands near the passages that answer it, so
questions get that prefix.

The model reads at most 512 tokens (about 400 words). 71 provisions are longer
than that, so long provisions are cut into pieces of 200 words, each sharing
50 words with the one before and each starting with the provision's citation
and headings. A provision's score is the score of its best piece. The vectors
are computed once and saved in `data/processed/cache/`.

**3. Hybrid.** The two rankings are merged with *reciprocal rank fusion*: a
provision gets `1 / (60 + rank)` from each list, and the totals are sorted. A
provision near the top of either list ends up near the top, and BM25 scores
(0 to about 30) never have to be put on the same scale as cosines (−1 to 1).

**4. Re-ranking.** A cross-encoder,
[`cross-encoder/ms-marco-MiniLM-L6-v2`](https://huggingface.co/cross-encoder/ms-marco-MiniLM-L6-v2)
(22 million weights, 90 MB), reads the question and one provision *together*
and outputs one number: how well this text answers this question. Unlike the
embedding model, which reads them separately, it can see how the words of one
relate to the words of the other, so it is more exact; it is also far slower,
because it has to run once per pair. So it only reorders the top *N* hybrid
results, using each provision's best piece. *N* is chosen on dev from 10, 20
and 50.

## How it is measured

For each answerable question, the **rank** is the position of its gold
provision in a method's list (for a multi question, the position by which all
its gold provisions have appeared; for other questions, the first of any
alternatives).

* **Recall@k**: the share of questions whose rank is k or better. Recall@5
  matters most: milestone 4 quotes from the top few results, and a provision
  that is not among them cannot be quoted.
* **MRR@10**: the mean of 1/rank (0 past 10). It rewards first place over
  fifth.

The 20 unanswerable questions have no rank; they are kept for milestone 4,
which has to refuse them. The evaluation records the score of each method's
first result so milestone 4 can see how far apart the two groups are.

## Dev first, test once

```
make search-dev     # all methods on the 50 dev questions; chooses N
make search-test    # bm25, dense, hybrid and rerank@N on the 100 test questions
```

The dev run writes `results/search-choice.json` with the chosen *N*, and the
test run will not start without it. Nothing is chosen by looking at the test
questions, so the test numbers estimate how the system does on questions it
was not tuned on. The fixed settings (`k1`, `b`, the 60 in fusion, the piece
size) are the usual published defaults, not tuned at all.

## How sure the numbers are

With 87 answerable test questions, one question is worth more than one
percentage point, so a difference of a few points can be luck. The test run
reports two things:

* a **95% bootstrap interval** for each method's recall@5: the questions are
  resampled with replacement 10,000 times and the middle 95% of the resulting
  scores is reported;
* an **exact McNemar test** for each pair of methods compared: only the
  questions where one method finds the answer and the other does not count,
  and the p-value is the chance of a split at least that uneven if both
  methods were equally good (each disagreement a coin toss). Four comparisons
  are planned in advance: hybrid against each of its parts, re-ranking
  against hybrid, and re-ranking against BM25.

## Results

Full tables: [results/search-dev.md](../results/search-dev.md) and
[results/search-test.md](../results/search-test.md); the rank of every
question under every method is in the `.json` files beside them.

**Choosing the depth on dev.** Re-ranking the top 20 and the top 50 tied on
dev recall@5 (84%), and the top 50 had a slightly higher MRR@10, so 50 was
chosen. Re-ranking only the top 10 did worse (81%).

**Test, 87 answerable questions:**

| method | R@1 | R@3 | R@5 | R@10 | R@20 | MRR@10 |
|---|---|---|---|---|---|---|
| bm25 | 41 | 68 | 76 | 82 | 91 | 55 |
| dense | 52 | 75 | 80 | 85 | 90 | 64 |
| hybrid | 49 | 77 | 80 | 86 | 95 | 63 |
| rerank@50 | **59** | **79** | **87** | **91** | **97** | **70** |

| recall@5 by kind | fact (49) | number (15) | scope (12) | multi (11) |
|---|---|---|---|---|
| bm25 | 82 | 73 | 75 | 55 |
| dense | 84 | 100 | 67 | 55 |
| hybrid | 88 | 87 | 67 | 55 |
| rerank@50 | 86 | 100 | 92 | 73 |

### What the results show

* **Re-ranking is the one clear improvement.** Against BM25 it finds the
  answer in the top 5 for 14 questions BM25 misses and loses 4 (p = 0.031),
  and it puts the right rule first 59% of the time against 41%.
* **The middle steps are not proven.** Hybrid against BM25 (8 against 4,
  p = 0.39), hybrid against dense (5 against 5) and re-ranking against hybrid
  (9 against 3, p = 0.15) all point the same way but could be chance with 87
  questions. The 95% intervals for recall@5 overlap for every pair.
* **Dense and BM25 fail on different questions.** On dev, dense was worse than
  BM25 at recall@5 (72% against 77%) but better at recall@20 (95% against
  86%); on test it was better at both. Neither is reliably ahead, which is
  why combining them and re-ranking helps.
* **Questions that need two provisions are the hardest.** Even after
  re-ranking, 27% of them do not have both provisions in the top 5. Milestone
  4 has to quote from more than one result for these.
* **Example.** *"How long do I have to cancel a new savings account?"*: BM25
  does not have BCOBS 6.1.1R (14 calendar days) in its top 10, because the
  rule says *retail banking service*, not *savings account*. After
  re-ranking it is second, behind BCOBS 6.4.2R, a 30-day rule from the same
  chapter about what happens after cancelling.
* **The re-ranker's score can tell answerable from unanswerable questions,
  roughly.** The median score of its first result is 6.0 for answerable test
  questions and −1.9 for unanswerable ones (5.7 and −5.1 on dev). BM25 and
  dense scores overlap much more (19.0 against 14.4; 0.78 against 0.70).
  Milestone 4 sets a refusal threshold on this score, using dev only.

**Speed.** On the CPU, embedding the provisions took about a minute and a
half, once. Searching took about 2 seconds a question with re-ranking of the
top 50 (196 s for 100 test questions), almost all of it the cross-encoder
reading 50 pairs; re-ranking the top 20 would take about 40% of that for the
same dev recall@5.

## Reproducing

The numbers come from one run on a Windows 11 PC (WSL2, CPU only) with the
models and package versions pinned in `requirements-models.txt`. The
provisions are embedded once and the vectors saved in
`data/processed/cache/`. Different hardware can change the last
decimal places of the model scores, which can swap two results with almost
equal scores, so a rerun may differ by a question or two.

## Limits

* Every setting except *N* is a published default. Tuning them on 50 dev
  questions would risk fitting those questions rather than the task.
* Both models were trained on general web text (MS MARCO and similar), not on
  regulation. They have never seen how the Handbook uses *firm*, *respondent*
  or *eligible complainant*.
* A provision is searched as a whole (or as pieces of a long one). A question
  answered by one item in a long list competes with the rest of that list's
  text.
