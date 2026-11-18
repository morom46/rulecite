# Getting the data

rulecite works on three sourcebooks of the FCA Handbook:

| Book | Name | What it covers |
|---|---|---|
| DISP | Dispute Resolution: Complaints | how firms must handle complaints, and the Financial Ombudsman Service |
| BCOBS | Banking: Conduct of Business sourcebook | how banks deal with customers: communications, statements, cancellation |
| PRIN | Principles for Businesses | the 12 Principles, and PRIN 2A, the Consumer Duty |

The PDFs are **not** in this repository. Copying Handbook text needs the
FCA's permission, so each person downloads their own copy. Everything made
from them (`data/processed/`) also stays on your machine. The one exception is
the test set, which stores rule IDs and short key phrases of a few words each
(see [docs/testset.md](../docs/testset.md)), never the rule text.

## Download

1. Open [handbook.fca.org.uk](https://handbook.fca.org.uk).
2. Search for `DISP` and open any chapter, for example **DISP 1**.
3. Choose **View Sourcebook as PDF** (not Chapter or Section) and save it as
   `data/raw/DISP.pdf`.
4. Do the same for `BCOBS` and `PRIN`, saving `data/raw/BCOBS.pdf` and
   `data/raw/PRIN.pdf`.

Then:

```
make ingest
```

## Which versions the results use

`data/snapshot.json` records the exact files the published results were made
with: their SHA-256 checksums, page counts, the "last updated" month printed in
each PDF, and the number of provisions found. `make ingest` compares your files
with it and says whether they match. The FCA updates the Handbook often, so a
newer download can give slightly different numbers.

| Book | Last updated | Pages | Provisions |
|---|---|---|---|
| DISP | September 2026 | 285 | 700 |
| BCOBS | June 2026 | 147 | 242 |
| PRIN | June 2026 | 86 | 234 |

Downloaded on 18 November 2026.
