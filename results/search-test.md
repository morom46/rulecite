# Search results: test

100 test questions, 87 of them answerable. Made by `python -m rulecite.evaluate --split test` on 18 November 2026 with `BAAI/bge-small-en-v1.5` and `cross-encoder/ms-marco-MiniLM-L6-v2`, on the CPU. Searching took 195.9 s for 100 questions.

Recall@k is the share of answerable questions whose gold provision is in the top k results (for multi questions, all of them). MRR@10 is the mean of 1/rank. All numbers are percentages.

| method | R@1 | R@3 | R@5 | R@10 | R@20 | MRR@10 |
|---|---|---|---|---|---|---|
| bm25 | 41 | 68 | 76 | 82 | 91 | 55 |
| dense | 52 | 75 | 80 | 85 | 90 | 64 |
| hybrid | 49 | 77 | 80 | 86 | 95 | 63 |
| rerank@50 | 59 | 79 | 87 | 91 | 97 | 70 |

Recall@5 by kind of question:

| method | fact (49) | number (15) | scope (12) | multi (11) |
|---|---|---|---|---|
| bm25 | 82 | 73 | 75 | 55 |
| dense | 84 | 100 | 67 | 55 |
| hybrid | 88 | 87 | 67 | 55 |
| rerank@50 | 86 | 100 | 92 | 73 |

## How sure are these numbers?

95% bootstrap intervals for recall@5 (10,000 resamples of the questions):

| method | R@5 | 95% interval |
|---|---|---|
| bm25 | 76 | 67 to 84 |
| dense | 80 | 71 to 89 |
| hybrid | 80 | 72 to 89 |
| rerank@50 | 87 | 80 to 94 |

Exact McNemar tests on recall@5: of the questions where two methods disagree, how many each one got, and the chance of a split that uneven if they were equally good.

| A | B | only A finds | only B finds | p |
|---|---|---|---|---|
| hybrid | bm25 | 8 | 4 | 0.388 |
| hybrid | dense | 5 | 5 | 1.000 |
| rerank@50 | hybrid | 9 | 3 | 0.146 |
| rerank@50 | bm25 | 14 | 4 | 0.031 |

## Score of the first result

For milestone 4, which has to refuse unanswerable questions: the median score of the top result for each kind of question.

| method | answerable | unanswerable |
|---|---|---|
| bm25 | 19.020 | 14.445 |
| dense | 0.784 | 0.696 |
| rerank@50 | 6.046 | -1.896 |
