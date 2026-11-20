# Rules for editing this repo

For agents and people who add results. Readers should start with [README.md](README.md) or [SKILL.md](SKILL.md).

The repo is a map, and it will grow: more models, more rows. The rules below keep 1 thing true as it grows. An agent with a new case must be able to find the results obtained under its conditions without reading everything.

## Layout: one place per kind of content

| Content | Place |
|---|---|
| The story of a mechanism: problem, change, result, how to transfer | the chapter in `playbook/` for that mechanism |
| One line per hypothesis with the verdict and tags | `ledger/hypotheses.md` |
| A digest per model: shape, final numbers, what worked and what did not, pointers to chapters | `cases/<model>.md` |
| Hardware, model shapes, the traits table | `cases/README.md` |
| The map: entry by regime and by symptom | `playbook/00-start-here.md` |
| Situation card, experiment rules, checklist, entry template | `protocol/` |
| Small scripts that help to orient | `tools/` |
| Terms | `glossary.md` |
| What changed and when | `CHANGELOG.md` |

Chapters are organized by mechanism, not by model. A result about live caches on a new model goes into chapter 04, not into a new file.

## Adding a result

1. Fill the [entry template](protocol/entry-template.md). An entry without a control, a before → after and a decision is not ready.
2. Put the story into the right chapter, in the section of that mechanism. Label it with the model name and date. Add a row to an existing table when the format fits.
3. Add 1 row to the ledger with the next free ID in its area (PL, MS, MG, PF, SD, HD, QP, AG), tags from the vocabulary, and a link to the chapter.
4. Update the model's case file and its column in the traits table of `cases/README.md`.
5. If the result changes the map (`playbook/00-start-here.md`: a question, a symptom row, a finding), the "Read when" line of a chapter, or the routing table of `SKILL.md`, update them.
6. If the count of hypotheses changed, update it in `README.md` and in the `description` of `SKILL.md`.
7. Add a line to `CHANGELOG.md`.

## Adding a model

1. Fill a [situation card](protocol/situation-card.md) for it and keep the tag line.
2. Create `cases/<model>.md` in the same shape as the others.
3. Add a column to the traits table and a row to the models table in `cases/README.md`.
4. Add its results by the steps above. If the model behaves unlike every column of the traits table, say so in the map: a new branch is worth more than a forced fit.

## Tags

- Every ledger row has tags. They state the conditions under which the verdict was obtained, not the topic.
- Use the vocabulary at the top of the ledger. Add a new tag only when a condition changed a verdict and no existing tag names it. Add it to the vocabulary table and to the situation card in the same commit.
- Tag what was tested. If a result was obtained only on strong skew, it gets `#strong-skew` and nothing about weak skew.
- `#dense-ok` only when the result does not depend on MoE routing.

## When the repo grows

- A chapter that passes about 20 KB is split by sub-mechanism. Keep the old file as a short index so links survive.
- When an area of the ledger passes about 40 rows, split it into 2 areas with new prefixes. Never renumber existing IDs.
- The map stays short. A new finding goes into a chapter and the ledger. It goes into the map only if it changes where a case should be routed.
- Every chapter keeps its second line: when to read it, when to skip it, its ledger tags.

## Changing an old result

Never delete a result silently. If a later run changed the verdict:

- edit the ledger row to the current verdict;
- in the chapter, keep the original result and add the new one next to it with the date and the reason.

A reader has to be able to see why a decision that was once reasonable was reversed.

## Numbers

- Every number comes from a real run, or carries a label: (sim), (calc), (micro), (ext), (1 run).
- State the conditions next to the number: model, quant, engine, number of cards, RAM config when the CPU is on the path, context depth, content type.
- Do not compare numbers taken on different RAM configs, power limits or harnesses. If you have to show them together, say they do not compare.
- Do not round away the uncertainty. If the result is inside the noise, write that.
- Negative results are as valuable as positive ones. Record them with the reason and a "revisit when".

## Tools

- Standard library only, 1 file per tool, a `--demo` that runs with no input, the input format in the docstring.
- A tool answers an orientation question from the situation card. Benchmark harnesses and engine launchers do not belong here.
- Never quote the output of a tool on synthetic data as a result.

## What must not get into the repo

- Private paths, hostnames, IP addresses, usernames, tokens, raw launch arguments with secrets.
- Links to files that exist only on a private machine. Link public repos, PRs and docs at a fixed revision.
- Unreleased model details shared under an agreement.
- Methods for removing model refusals. This repo is about speed and its quality cost.

Before a commit, grep the diff for `/mnt/`, `/home/`, `/Users/`, `192.168.`, `ssh `.

## Style

- Plain English, short sentences, digits for numbers (`4 cards`, not `four cards`).
- No em or en dashes. Use a comma, a period, a colon or parentheses. Ranges are written with a hyphen: `74-79%`.
- Straight quotes only.
- Say the result directly, without filler, hedging phrases or metaphors.
- Tables for comparisons, short paragraphs for mechanisms, a "Transfer checklist" at the end of every chapter.
- Engine flags, file names and code in backticks.
- Units: tok/s, ms, µs, GB/s, GiB vs GB as recorded.

## Commits

One topic per commit. The message says which model and mechanism: `Hy4 Flash: Engram on NVMe (chapter 12, AG-08)`.
