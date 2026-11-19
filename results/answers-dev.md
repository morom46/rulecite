# Answer results: dev

50 dev questions (43 answerable, 7 unanswerable). Made by `python -m rulecite.answer_eval --split dev` on 19 November 2026 with `BAAI/bge-small-en-v1.5` and `cross-encoder/ms-marco-MiniLM-L6-v2`, on the CPU, in 173 s. Refusal threshold 0.03 (chosen on these questions).

An answer is **correct** when it contains every key fact of the question. A question is **right** when its answer is correct, or when it is unanswerable and the system refused.

| | quoted pieces (the system) | no refusing | whole provisions |
|---|---|---|---|
| accuracy (right / all) | 70 | 58 | 84 |
| correct answers | 28 | 29 | 35 |
| wrong answers | 14 | 14 | 7 |
| answerable but refused | 1 | 0 | 1 |
| unanswerable, rightly refused | 7 | 0 | 7 |
| unanswerable but answered | 0 | 7 | 0 |
| correct among answered (%) | 67 | 58 | 83 |
| median words in an answer | 78 | 103 | 182 |

*No refusing* answers every question with the same quotes. *Whole provisions* quotes each provision in full instead of its best piece: an upper limit on what picking the piece can reach, at the cost of much longer answers.

95% bootstrap interval for accuracy: 58 to 82.

Right by kind of question (%):

| fact (24) | number (8) | scope (6) | multi (5) | unanswerable (7) |
|---|---|---|---|---|
| 71 | 62 | 83 | 20 | 100 |

## The trade-off

A higher threshold refuses more: fewer wrong answers and fewer unanswerable questions answered, but more answerable questions refused.

| threshold | answered | accuracy | correct | wrong | answerable refused | unanswerable answered |
|---|---|---|---|---|---|---|
| -6.00 | 94% | 64 | 29 | 14 | 0 | 4 |
| -4.00 | 86% | 70 | 29 | 13 | 1 | 1 |
| -2.00 | 86% | 70 | 29 | 13 | 1 | 1 |
| 0.00 | 84% | 70 | 28 | 14 | 1 | 0 |
| 0.03 **(chosen)** | 84% | 70 | 28 | 14 | 1 | 0 |
| 2.00 | 76% | 68 | 27 | 11 | 5 | 0 |
| 4.00 | 64% | 62 | 24 | 8 | 11 | 0 |
| 6.00 | 38% | 38 | 12 | 7 | 24 | 0 |

The best dev accuracy, 70%, holds for thresholds from -2.24 to 0.58; the middle, 0.03, is saved to `results/answers-choice.json`.
