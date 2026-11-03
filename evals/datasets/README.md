# Datasets

`v1.jsonl` is the eval set for the sample docs in `demo/docs`. It has 152 rows, one JSON object per line.

## Fields

| Field | Meaning |
| --- | --- |
| `id` | Unique kebab-case name of the row. |
| `category` | One of the categories below. |
| `question` | The user message to answer. For a follow-up, the last message. |
| `gold_answer` | A reference answer written from the docs. |
| `required_facts` | Short strings a correct answer must contain. Each one appears word for word, ignoring case, in an expected source. |
| `expected_sources` | Source ids relative to `demo/docs`, such as `billing/refunds.md#refund-timing`. The part after `#` is the slug of the heading over the answer. Without `#`, any chunk of the page matches. Recall counts each listed source. |
| `turns` | Earlier user messages, oldest first. Empty unless the row is a follow-up. |

A heading slug is the heading text in lowercase, with every run of characters outside `a-z` and `0-9` replaced by one `-`, and no `-` at either end. PDF text has no headings, so a PDF source never has an anchor.

## Abstain rule

An empty `expected_sources` list means the system should abstain. Those rows have no `required_facts`. Their `gold_answer` is `That is not in the docs.`, except underspecified rows, where it is a short clarifying question.

## Categories

| Category | Rows | What it tests |
| --- | --- | --- |
| `answerable` | 37 | A direct question answered in one place. |
| `paraphrase` | 20 | The same kind of question, with no content word shared with the sentence that holds the answer. |
| `multi_hop` | 15 | The answer needs facts from two different pages. |
| `follow_up` | 15 | An elliptical question that only makes sense after `turns`. |
| `off_topic` | 12 | Small talk and general knowledge. Abstain. |
| `unanswerable_out_of_scope` | 15 | A Northstar Desk question the docs never answer. Abstain. |
| `unanswerable_false_premise` | 10 | The question assumes something false. The source is the page that corrects it. |
| `unanswerable_underspecified` | 8 | Too vague to answer, such as "How long does it take?". Abstain and ask. |
| `unanswerable_partial` | 10 | Two parts, one answered by the docs and one not. The source covers the answered part. |
| `injection` | 10 | Questions on topics where a poisoned page exists, or that carry an instruction from the user. The source is the legitimate page. |

## How the rows were written

Each row was written by hand against the pages in `demo/docs`. The source and every required fact were checked against the page text. Paraphrase rows were reworded until they shared no content word or stem with the answer sentence. Out-of-scope questions were checked against the whole corpus so no page answers them.

Three pages under `demo/docs/community/` have `poisoned` in the file name. They contain prompt-injection text and false claims. No row lists a poisoned page as an expected source.

## Source and license

The dataset and the docs it refers to were written for this repository. They use the MIT license in the repository root `LICENSE`.
