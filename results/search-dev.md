# Search results: dev

50 dev questions, 43 of them answerable. Made by `python -m rulecite.evaluate --split dev` on 18 November 2026 with `BAAI/bge-small-en-v1.5` and `cross-encoder/ms-marco-MiniLM-L6-v2`, on the CPU. Searching took 118.9 s for 50 questions.

Recall@k is the share of answerable questions whose gold provision is in the top k results (for multi questions, all of them). MRR@10 is the mean of 1/rank. All numbers are percentages.

| method | R@1 | R@3 | R@5 | R@10 | R@20 | MRR@10 |
|---|---|---|---|---|---|---|
| bm25 | 47 | 63 | 77 | 79 | 86 | 57 |
| dense | 40 | 60 | 72 | 88 | 95 | 53 |
| hybrid | 56 | 70 | 79 | 86 | 93 | 64 |
| rerank@10 | 56 | 74 | 81 | 86 | 93 | 67 |
| rerank@20 | 58 | 79 | 84 | 88 | 93 | 70 |
| rerank@50 | 58 | 79 | 84 | 88 | 95 | 70 |

Recall@5 by kind of question:

| method | fact (24) | number (8) | scope (6) | multi (5) |
|---|---|---|---|---|
| bm25 | 79 | 88 | 83 | 40 |
| dense | 79 | 75 | 83 | 20 |
| hybrid | 83 | 88 | 83 | 40 |
| rerank@10 | 79 | 88 | 100 | 60 |
| rerank@20 | 83 | 88 | 100 | 60 |
| rerank@50 | 83 | 100 | 100 | 40 |

**Chosen re-ranking depth: 50** (best recall@5 on dev, then best MRR@10, then the smallest). Saved to `results/search-choice.json` for the test run.

## Score of the first result

For milestone 4, which has to refuse unanswerable questions: the median score of the top result for each kind of question.

| method | answerable | unanswerable |
|---|---|---|
| bm25 | 18.596 | 12.046 |
| dense | 0.775 | 0.683 |
| rerank@10 | 5.733 | -6.601 |
| rerank@20 | 5.733 | -5.060 |
| rerank@50 | 5.733 | -5.060 |
