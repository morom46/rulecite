# From PDF to rule records

Milestone 1 turns three Handbook PDFs into one record per provision:
`data/processed/rules.jsonl`, one JSON object per line. Everything later
(search, answers, evaluation) works on these records.

## The record

```json
{
  "id": "DISP 1.6.2A",
  "type": "R",
  "book": "DISP",
  "kind": "rule",
  "chapter": "DISP 1",
  "section": "DISP 1.6",
  "section_title": "Complaints time limit rules",
  "heading": "EMD and PSD Complaints",
  "text": "Where a complaint is an EMD complaint or a PSD complaint, the respondent must:\n(1) send a final response ...",
  "page": 37,
  "refs": [],
  "terms": ["complaint", "emd complaint", "psd complaint", "respondent", "final response", "business days"],
  "deleted": false
}
```

| Field | Meaning |
|---|---|
| `id` | the provision's number as printed in the margin |
| `type` | `R` rule, `G` guidance, `E` evidential provision, `D` direction; empty for annexes and schedules |
| `kind` | `rule`, `annex`, `app` (appendix), `sch` (schedule), `tp` (transitional provision), `intro` |
| `chapter`, `section` | where it sits; schedules and transitional provisions have no sections |
| `section_title` | from the "Section :" line that starts each section |
| `heading` | the nearest subheading above it inside the section |
| `text` | the text; list items and paragraphs start new lines; table rows have their cells joined by ` \| ` |
| `page` | the PDF page it starts on |
| `refs` | other provisions it mentions, type letter removed |
| `terms` | Glossary terms it uses (the Handbook prints them in italics), lower case |
| `deleted` | the whole provision reads "[deleted]"; such records are kept but not indexed |

The citation form joins ID and type with no space: `DISP 1.6.2AR`.

## How the parser works

The PDFs are generated from the Handbook website and have a fixed layout. The
parser (`rulecite/ingest.py`) reads that layout through PyMuPDF instead of
working on plain text, because plain text loses the information that says
where one provision ends and the next begins.

| What | How it is recognised |
|---|---|
| a provision ID | 7.2 pt bold text in the left margin (x < 90) |
| its type letter | 7.2 pt regular text at x 90 to 132, level with the ID |
| provision text | 9.9 pt text in the column starting at x = 133 |
| a new section | a 12 pt bold line starting "Section :" |
| a subheading | 12 pt bold text inside the text column |
| page header and footer | above y = 40 or below y = 780 |
| chapter title pages | text larger than 20 pt |
| the table of contents | 12 and 14 pt bold text in the margin, before any ID |
| a table | PyMuPDF's table finder gives the grid; the words in each cell are read separately |

Three details took some care:

* **Order.** An ID is printed about 2 points lower than the first line of its
  text. Sorting by height alone would put the first line into the previous
  provision, so IDs are moved up by 6 points before sorting.
* **False tables.** On some pages the table finder reports one table covering
  the whole page, because the layout itself is a grid (IDs in one column,
  text in another). Real tables sit inside the text column, so any table that
  starts in the margin is ignored and that page is read line by line.
* **Terms broken across lines.** A Glossary term such as "Financial Ombudsman
  Service" can wrap onto the next line. Italic text that runs to the end of a
  line and continues at the start of the next is joined back together.

## What came out

| Book | Provisions | R | G | Other types | No type |
|---|---|---|---|---|---|
| DISP | 700 | 271 | 357 | 60 (E, D) | 12 |
| BCOBS | 242 | 145 | 90 | 0 | 7 |
| PRIN | 234 | 115 | 112 | 2 (E) | 5 |
| **Total** | **1,176** | 531 | 559 | 62 | 24 |

* Median length 58 words; 90% are under 206 words. The longest is DISP TP 1.1,
  a transitional provisions table of about 5,000 words.
* 41 provisions contain tables; for example PRIN 2.1.1, the 12 Principles,
  comes out as twelve rows such as `1 Integrity | A firm must conduct its
  business with integrity.`
* 891 provisions have a subheading, 455 refer to other provisions (842
  references in all), and 740 different Glossary terms are used.
* Of the 779 references between these three books, 763 (98%) point to a
  provision that exists in the files. The rest name deleted provisions or
  annexes printed under a different ID.

## Checks

* `tests/test_ingest.py` builds a small synthetic PDF with the same layout and
  checks every rule above: IDs, types, sections, subheadings, list items,
  text continuing over a page break, a table, an annex whose type letter is
  printed inside its ID, a deleted provision, and that the header, footer,
  table of contents and text before the first ID are all left out. The text
  in it is invented, so no Handbook text is stored in the repository.
* `tests/test_real_data.py` runs on your own download after `make ingest`: no
  provision without text, no header or footer text, all 12 Principles in
  PRIN 2.1.1, a few known facts (for example DISP 1.6.2 contains "eight
  weeks"), and more than 95% of references resolving.

## Known limits

* A few annex forms (for example the claims management complaints return in
  DISP 1 Annex 1AB) are tables that start in the margin. They are read line by line, so their
  columns run together.
* Text is not de-hyphenated, because the PDFs break lines at spaces only.
* Only the latest version of each sourcebook is used; the Handbook's history
  is not.
* Ingest takes about two minutes, almost all of it in the table finder.
