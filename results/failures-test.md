# Why answers go wrong: test

43 of 100 test questions were not right at the refusal threshold 0.03. Each is put in the first kind that fits, in this order. Search ranks are from `rerank@50`.

| kind of failure | questions |
|---|---|
| Answered a question these books do not cover | 4 |
| Refused a question that has an answer | 2 |
| Right provision not in the top 20 of search | 2 |
| Right provision found by search (top 20), but not in the top two | 16 |
| Right provision second, but its score was below the threshold | 0 |
| Multi question: one of the needed provisions not quoted | 7 |
| Right provision quoted, but the wrong piece of it | 12 |

Of the 12 wrong-piece failures, 12 would be correct if the whole provision were quoted.

Also: 5 answers counted as correct put another provision's quote first, so the right quote is second.

## Answered a question these books do not cover (4)

| id | kind | question | gold | quoted (score) | search rank |
|---|---|---|---|---|---|
| q137 | unanswerable | What are the rules for advising a customer on a defined benefit pension transfer? ⚑ | – | DISP App 4.2.1 (4.1), DISP App 4.1.1 (3.4) | – |
| q138 | unanswerable | How much is a bank allowed to charge for an unarranged overdraft? ⚑ | – | BCOBS 8.2.4 (4.0), BCOBS 8.4.13 (1.4) | – |
| q143 | unanswerable | What is the minimum interest rate a savings account must pay? | – | BCOBS 2.2A.1 (0.5) | – |
| q147 | unanswerable | How are the FCA's annual periodic fees calculated? ⚑ | – | DISP 4.2.6 (1.0) | – |

## Refused a question that has an answer (2)

| id | kind | question | gold | quoted (score) | search rank |
|---|---|---|---|---|---|
| q074 | fact | Must a bank help customers find old accounts they have lost track of? | BCOBS 5.1.9 | none (best -1.5) | 1 |
| q099 | scope | Does the £35 limit apply if the customer could not have noticed their card was missing be… | BCOBS 5.1.12 | none (best -1.9) | 1 |

## Right provision not in the top 20 of search (2)

| id | kind | question | gold | quoted (score) | search rank |
|---|---|---|---|---|---|
| q032 | fact | What must firms publish so that customers know how complaints are handled? | DISP 1.2.1 | DISP 1.1A.10 (5.4), DISP 1.10A.7 (4.9) | 24 |
| q034 | fact | Who can bring a complaint to the Financial Ombudsman Service? | DISP 2.7.3 | DISP 2.7.1 (7.9), DISP 1.11.4 (7.5) | 143 |

## Right provision found by search (top 20), but not in the top two (16)

| id | kind | question | gold | quoted (score) | search rank |
|---|---|---|---|---|---|
| q009 | number | How long after a firm's final response does a customer have to take the complaint to the… | DISP 2.8.2 | DISP 2.8.3 (6.4), DISP 1.6.2 (6.4) | 3 |
| q017 | fact | What must a firm send a customer when it resolves their complaint within three business d… | DISP 1.5.4 | DISP 1.1A.24 (5.6), DISP 1.1A.23 (5.3) | 4 |
| q019 | fact | Can a firm charge a customer for making a complaint? | DISP 1.3.1A | DISP 1.3.6 (2.3), DISP App 3.2.3 (2.2) | 5 |
| q029 | fact | Can a firm pass a complaint on to another firm that is responsible for the problem? | DISP 1.7.1 | DISP 1.10.1B (6.2), DISP App 3.2.3 (5.3) | 15 |
| q033 | fact | What happens if a firm misses the deadline for its complaints report? | DISP 1.10.6A | DISP 1.10.1D (0.8), DISP 1.10.6 (0.7) | 6 |
| q044 | fact | What happens before the ombudsman dismisses a complaint without considering its merits? | DISP 3.3.1 | DISP 3.3.4A (8.3), DISP 3.3.2 (8.2) | 3 |
| q048 | fact | Can a firm take back its consent for the ombudsman to consider a complaint that was refer… | DISP 2.8.2A | DISP 2.8.2 (4.6), DISP 2.8.1 (4.4) | 6 |
| q063 | number | How long must a bank keep records of customers cancelling a contract? | BCOBS 6.2.3 | BCOBS 6.4.2 (5.0), BCOBS 6.4.1 (4.9) | 3 |
| q067 | scope | Can a customer cancel a fixed-rate savings account during the cooling-off period? | BCOBS 6.1.2 | DISP App 3.6.2 (0.4) | 3 |
| q070 | fact | If a bank does not carry out a payment correctly, what must it refund besides the payment… | BCOBS 5.1.18 | BCOBS 5.1.16 (4.5), BCOBS 5.1.17 (2.7) | 4 |
| q077 | fact | What is the basic standard for a bank's communications and financial promotions? | BCOBS 2.2.1 | BCOBS 2.3.9 (4.6), BCOBS 2.3.1 (4.1) | 17 |
| q082 | fact | Can a bank show an 'available balance' that includes the customer's overdraft limit? | BCOBS 2.3.10 | BCOBS 4.4.3 (2.2), BCOBS 8.3.6 (1.6) | 6 |
| q096 | scope | Do the BCOBS rules on alerts and account tools apply to credit unions? | BCOBS 1.1.5 | BCOBS 8.1.5 (6.5), BCOBS 1.1.5A (4.6) | 4 |
| q122 | fact | What must the governing body report on the Consumer Duty set out? | PRIN 2A.8.3 | PRIN 2A.8.4 (7.4), PRIN 2A.8.5 (5.8) | 3 |
| q124 | scope | Is there any activity that PRIN does not apply to? | PRIN 3.1.1 | PRIN 3.2.8 (7.9), PRIN 3.4.-1 (7.6) | 12 |
| q130 | scope | Do the Consumer Duty product governance rules apply to products already covered by PROD 3? | PRIN 2A.3.24 | PRIN 2A.3.27 (7.9), PRIN 2A.3.26 (7.8) | 3 |

## Multi question: one of the needed provisions not quoted (7)

| id | kind | question | gold | quoted (score) | search rank |
|---|---|---|---|---|---|
| q053 | multi | Does a complaint that a firm forwarded in full to another firm count in the forwarding fi… | DISP 1.10.1A, DISP 1.7.1 | DISP 1.10.1A (7.1), DISP 1.10.1B (6.5) | 5 |
| q057 | multi | A complaint arrives seven years after the event. Can the firm reject it without looking a… | DISP 1.8.1, DISP 2.8.2 | DISP 1.8.1 (2.7), DISP 1.1A.36 (1.4) | 4 |
| q097 | multi | How long does a customer have to cancel a new savings account, and how quickly must the b… | BCOBS 6.1.1, BCOBS 6.4.1 | BCOBS 6.4.2 (2.9), BCOBS 6.4.1 (2.7) | 3 |
| q098 | multi | Someone uses a customer's stolen card. Who has to prove the payments were authorised, and… | BCOBS 5.1.11, BCOBS 5.1.12 | BCOBS 5.1.12 (0.2) | 2 |
| q104 | multi | What are the three cross-cutting obligations of the Consumer Duty? | PRIN 2A.2.1, PRIN 2A.2.8, PRIN 2A.2.14 | PRIN 2A.1.10 (6.0), PRIN 2A.4.12 (5.6) | 27 |
| q126 | multi | A firm finds it has harmed customers and one of them has complained. What must it do, and… | PRIN 2A.2.5, PRIN 2A.10.2 | DISP 1.3.6 (4.8), PRIN 2A.2.5 (4.6) | 4 |
| q127 | multi | What does fair value mean under the Consumer Duty, and when must a manufacturer first ass… | PRIN 2A.4.1, PRIN 2A.4.3 | PRIN 2A.4.19 (6.6), PRIN 2A.4.5 (6.6) | 19 |

## Right provision quoted, but the wrong piece of it (12)

| id | kind | question | gold | quoted (score) | search rank |
|---|---|---|---|---|---|
| q006 | number | How often does a firm normally have to send the FCA a complaints report? | DISP 1.10.1 | DISP 1.10.1 (6.5), DISP 1.10B.1 (4.6) | 1 |
| q011 | number | A customer only found out years later that something had gone wrong. How long do they hav… | DISP 2.8.2 | DISP 2.8.2 (0.4), DISP 1 Annex 3 (0.3) | 1 |
| q016 | number | If a firm has not replied to an ordinary complaint, after how long can the ombudsman cons… | DISP 2.8.1 | DISP 2.8.1 (5.5), DISP 2.8.2 (5.5) | 1 |
| q028 | fact | If a firm cannot give a final response within eight weeks, what must its written response… | DISP 1.6.2 | DISP 1.6.2 (4.5), DISP 2.8.1 (1.6) | 1 |
| q055 | multi | If a firm misses the eight-week deadline for a final response, when can the customer go t… | DISP 2.8.1, DISP 1.6.2 | DISP 1.6.2 (2.4), DISP 2.8.1 (1.8) | 2 |
| q056 | multi | What is the ombudsman's maximum money award for something that happened after April 2019,… | DISP 3.7.4, DISP 3.7.5 | DISP 3.7.4 (6.9), DISP 3.7.5 (2.8) | 2 |
| q058 | scope | Does any letter from the firm start the six-month time limit for going to the ombudsman? | DISP 2.8.3 | DISP 1 Annex 3 (5.1), DISP 2.8.3 (4.9) | 2 |
| q086 | fact | What must a bank's general overdraft information explain about what an overdraft is? | BCOBS 4.4.3, BCOBS 2.2B.2 | BCOBS 2.2B.2 (6.1), BCOBS 4.4.3 (5.4) | 1 |
| q093 | fact | Which overdraft alerts must personal current account customers be enrolled to receive? | BCOBS 8.4.3 | BCOBS 8.4.3 (7.3), BCOBS 8.4.4 (5.0) | 1 |
| q109 | fact | Does the Consumer Duty create a fiduciary relationship between a firm and its customers? | PRIN 2A.1.11 | PRIN 2A.1.11 (9.1), PRIN 2A.1.13 (4.3) | 1 |
| q116 | fact | How must manufacturers test their products under the Consumer Duty? | PRIN 2A.3.9 | PRIN 2A.3.9 (9.3), PRIN 2A.3.7 (7.5) | 1 |
| q119 | fact | What must customer support avoid putting in customers' way under the Consumer Duty? | PRIN 2A.6.2 | PRIN 2A.6.6 (4.5), PRIN 2A.6.2 (3.5) | 2 |

⚑ marks a hard negative: a question written to share words with a real provision that does not answer it.
