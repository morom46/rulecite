# Why answers go wrong

Milestone 6 looks at every test question the system did not get right, sorts
each into one kind of failure, and asks what would fix it. The counts come
from `make failures`, which reads the saved results; the full list, question
by question, is in [results/failures-test.md](../results/failures-test.md).

## The 41 failures on test

At the threshold chosen on dev (0.03), 59 of the 100 test questions were
right. Each of the other 41 is put in the first kind below that fits.

| kind of failure | questions | share of failures |
|---|---|---|
| Right provision found by search, but not in the top two | 16 | 39% |
| Right provision quoted, but the wrong piece of it | 10 | 24% |
| Multi question: one of the needed provisions not quoted | 7 | 17% |
| Answered a question these books do not cover | 4 | 10% |
| Refused a question that has an answer | 2 | 5% |
| Right provision not in the top 20 of search | 2 | 5% |
| Right provision second, but its score was below the threshold | 0 | 0% |

Two things stand out. **Search nearly always finds the right provision**: in
only 2 of the 87 answerable questions is it outside the top 20. And **the
system is rarely wrong about whether to answer**: 6 of the 41 failures are
about refusing. Most failures happen in between, in deciding which provision
and which sentence to quote.

## 1. Right provision found, but not in the top two (16)

Only the top two re-ranked provisions are quoted. For 13 of these 16
questions the right one was third to sixth; for the other 3, twelfth to
seventeenth.

**The nearest neighbour wins.** In 7 of the 16 the provision quoted first is
from the same section as the right one, and in 2 more from the same chapter;
each says something close to the right one:

* *"How long after a firm's final response does a customer have to take the
  complaint to the ombudsman?"* The answer is DISP 2.8.2R (six months). The
  system quotes DISP 2.8.3G, guidance on which response starts that six-month
  limit, and DISP 1.6.2R, the firm's own eight-week limit.
* *"How long must a bank keep records of customers cancelling a contract?"*
  The answer is BCOBS 6.2.3R (three years). The system quotes BCOBS 6.4.2R and
  6.4.1R, the 30-day limits for returning money after cancelling.
* *"What must the governing body report on the Consumer Duty set out?"* The
  answer is PRIN 2A.8.3R; the system quotes PRIN 2A.8.4R, the next provision,
  on how often the board reviews that report.

Neighbouring provisions share almost all their words and their headings, so
both search and the cross-encoder score them alike; the difference is in one
phrase (*"records"* against *"return any sums"*).

**Specialised text beats the general rule.** In 5 failures (in this group and
in kind 6) a quote comes from a part of the book written for one kind of
case: DISP App 3, on payment protection insurance complaints, for three
questions including *"Can a firm charge a customer for making a complaint?"*;
and DISP 1.1A, on complaints about MiFID investment business, for two more,
including *"What must firms publish so that customers know how complaints are
handled?"*, where it quotes the MiFID version of the rule. These parts repeat
*complaint*, *complainant* and *firm* in almost every sentence, so they match
almost any question about complaints. The same thing happened outside
the test set while trying the demo: for *"How long does a firm have to send a
final response to a complaint?"* the first quote was DISP 1.6.2AR, the
deadline for payment services complaints only, ahead of the general eight-week
rule.

## 2. Right provision, wrong piece (10)

The right provision is quoted, but not the sentence that holds the answer.
All 10 would be right if the whole provision were quoted, which is why
quoting whole provisions scores 69% against 59%, at nearly twice the length
(158 words against 88).

* *"How often does a firm normally have to send the FCA a complaints report?"*
  DISP 1.10.1R is quoted, but not the piece that says *"twice a year"*.
* *"A customer only found out years later… How long do they have from that
  point?"* DISP 2.8.2R is quoted, but not the piece with the three-year
  limit.

The cross-encoder was trained to judge whether a passage answers a question.
Choosing between sentences of one provision is a harder version of that task,
and it often picks the sentence with most of the question's words rather than
the one with the answer.

## 3. Multi questions missing a provision (7)

Questions that need two or more provisions are right only 3 times in 11. Both
provisions have to be in the top two and both pieces have to be right. In
*"How long does a customer have to cancel a new savings account, and how
quickly must the bank repay them?"* the system quotes the two 30-day
repayment rules and misses BCOBS 6.1.1R, the 14-day right to cancel. For
*"What are the three cross-cutting obligations of the Consumer Duty?"*, which
needs three provisions, none is in the top two.

## 4. Answered questions these books do not cover (4)

Three of the four are *hard negatives*, written to share words with a real
provision:

* *"What are the rules for advising a customer on a defined benefit pension
  transfer?"* quotes DISP App 4, which sets out how to work out redress for
  unsuitable transfer advice, with a high score (4.1).
* *"How much is a bank allowed to charge for an unarranged overdraft?"*
  quotes BCOBS 8.2.4R, on the overdraft cost calculator banks must provide
  (4.0). It is about overdraft costs, but sets no limit on them.
* *"How are the FCA's annual periodic fees calculated?"* quotes DISP 4.2.6R,
  which applies parts of the FEES manual to firms in the voluntary
  jurisdiction (1.0).

The fourth, *"What is the minimum interest rate a savings account must pay?"*,
scored only 0.5, just above the threshold. The cross-encoder's score
measures how much a passage is *about* the question's topic, not whether it
answers it, so a provision on the same topic can score high.

## 5. Refused questions that have an answer (2)

In both, the right provision was ranked first but scored below the
threshold (−1.5 and −1.9): *"Must a bank help customers find old accounts
they have lost track of?"* and *"Does the £35 limit apply if the customer
could not have noticed their card was missing?"* The questions use everyday
words (*lost track of*, *noticed*) where the rules say *trace* and
*detectable*.

## 6. Not found by search (2)

*"Who can bring a complaint to the Financial Ombudsman Service?"* The answer,
DISP 2.7.3R, is ranked 143rd. It answers with a defined term, *"an eligible
complainant must be a person that is: (1) a consumer…"*, and never uses the
words *bring* or *ombudsman*, while dozens of other provisions do.

*"What must firms publish so that customers know how complaints are
handled?"* The answer, DISP 1.2.1R, is ranked 24th, behind the MiFID version
of the same duty (DISP 1.1A.10R), which is quoted instead.

## Correct, but in the wrong order

The score counts an answer as correct if its key facts are anywhere in it.
In 5 correct test answers, the first quote is from the wrong provision and
the right one is second. A reader would see the wrong rule first. A stricter
measure that only counts the first quote would have 45 correct answers
rather than 50.

## What would fix it

In order of how many test failures each could reach. None of these has been
tried: each would have to be built and tuned on dev, and then checked on new
test questions, since these 100 have now been looked at closely.

| idea | reaches | cost |
|---|---|---|
| Quote the top three provisions, or the top two plus any within a small score margin | up to 13 of the 16 in kind 1, and some of kind 3 | longer answers |
| Quote whole provisions when they are short (most are under 100 words) | the 10 wrong-piece failures | longer answers |
| Rank specialised parts (DISP App, DISP 1.1A) lower unless the question names their subject | about 5 | a rule to maintain per book |
| Expand questions with the Handbook Glossary (*bring a complaint* → *eligible complainant*, *lost track of* → *trace*) | kinds 5 and 6 | building the mapping |
| A second check before answering: does the quoted piece contain a number or a yes/no that matches the question's kind? | some of kind 4 and of the wrong pieces | rules per kind of question |
| Fine-tune the cross-encoder on question-provision pairs from regulation | all kinds | needs hundreds of labelled pairs, which this test set is too small to provide without using up the test |
| Let a local language model write the answer from the quotes (the skipped milestone 5) | wrong pieces and multi questions | can introduce words that are not in the rules, which this design avoids |

## Limits of this analysis

* Each failure is given one kind, the first that fits. Some have two causes:
  a multi question can also have a wrong piece.
* The kinds are decided by a program from ranks, scores and key facts. The
  examples above were read by hand, but not all 41.
* The test set has 100 questions, so a kind with 2 failures could easily be
  4 or 0 on another 100.
