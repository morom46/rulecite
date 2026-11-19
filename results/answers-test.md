# Answer results: test

100 test questions (87 answerable, 13 unanswerable). Made by `python -m rulecite.answer_eval --split test` on 19 November 2026 with `BAAI/bge-small-en-v1.5` and `cross-encoder/ms-marco-MiniLM-L6-v2`, on the CPU, in 312 s. Refusal threshold 0.03 (chosen on dev).

An answer is **correct** when it contains every key fact of the question. A question is **right** when its answer is correct, or when it is unanswerable and the system refused.

| | quoted pieces (the system) | no refusing | whole provisions |
|---|---|---|---|
| accuracy (right / all) | 59 | 51 | 69 |
| correct answers | 50 | 51 | 60 |
| wrong answers | 35 | 36 | 25 |
| answerable but refused | 2 | 0 | 2 |
| unanswerable, rightly refused | 9 | 0 | 9 |
| unanswerable but answered | 4 | 13 | 4 |
| correct among answered (%) | 56 | 51 | 67 |
| median words in an answer | 88 | 92 | 158 |

*No refusing* answers every question with the same quotes. *Whole provisions* quotes each provision in full instead of its best piece: an upper limit on what picking the piece can reach, at the cost of much longer answers.

95% bootstrap interval for accuracy: 49 to 69.
Refusing against never refusing: right only with refusing 9, right only without 1 (exact McNemar p = 0.021).

Right by kind of question (%):

| fact (49) | number (15) | scope (12) | multi (11) | unanswerable (13) |
|---|---|---|---|---|
| 63 | 67 | 50 | 27 | 69 |

## The trade-off

A higher threshold refuses more: fewer wrong answers and fewer unanswerable questions answered, but more answerable questions refused.

| threshold | answered | accuracy | correct | wrong | answerable refused | unanswerable answered |
|---|---|---|---|---|---|---|
| -6.00 | 98% | 53 | 51 | 36 | 0 | 11 |
| -4.00 | 97% | 54 | 51 | 36 | 0 | 10 |
| -2.00 | 94% | 57 | 51 | 36 | 0 | 7 |
| 0.00 | 89% | 59 | 50 | 35 | 2 | 4 |
| 0.03 **(chosen)** | 89% | 59 | 50 | 35 | 2 | 4 |
| 2.00 | 82% | 60 | 49 | 31 | 7 | 2 |
| 4.00 | 71% | 53 | 42 | 27 | 18 | 2 |
| 6.00 | 46% | 42 | 29 | 17 | 41 | 0 |
