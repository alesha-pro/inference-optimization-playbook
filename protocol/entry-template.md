# Rig experiment log

This is the owner's format for recording experiments on the rig. Each log includes a date, the control, the result and the decision. When a later test changes a decision, the notebook links the 2 dated records so the reason stays visible.

The owner and the owner's agents use these records to maintain the chapters, ledger and model case files. [Internal notebook maintenance](../AGENTS.md)

```markdown
### [Model], [observed problem and mechanism], [date]

Load and criterion. Scenario, depth, share of fresh tokens, target metric, quality tolerance.
Control. Weights, engine and revision, hardware and links, placement, cache states, inputs and seed.
Hypothesis. Where are the milliseconds or bytes lost? Which observation would refute it?
Change. What was turned on, which path stayed for the A/B, which values were fixed.
Results. Before → after, units, series size, spread or worst case, cost of start and memory.
Quality. Reference, fixed continuations, behavior tests, the first divergence.
Decision. Accepted / separate mode / rolled back / microtest only. The reason and the remaining uncertainty.
Transfer. How to recognize a fitting case on another model, and the cheapest test to run.
Materials. Launch command, revision, input IDs or their hashes, raw results and control.
```

## Evidence labels

Mark every number that is not a plain run on the rig:

| Label | Meaning |
|---|---|
| (none) | a real run on the hardware in [cases/README.md](../cases/README.md) |
| (sim) | a simulator on real traces |
| (calc) | a calculation or a fit, not run |
| (micro) | a microbenchmark of one operation, not a full pass |
| (ext) | someone else's number |
| (1 run) | not repeated |

## Example from the Hy4 Flash log

This abbreviated example follows the drafter head experiment in the output head chapter. [Full experiment](../playbook/13-output-head.md)

```markdown
### Hy4 Flash, Q4 in the drafter head shifted the snapshot boundary, 2026-11-19

Load and criterion. Greedy decode. Target: faster decode with an exact ID match against the release.
Control. The release build and its weights. 9 extra dialogs with a second turn.
Hypothesis. A cheaper drafter head changes only proposals. The target model still verifies them, so the output should stay the same. Refuted by any ID that differs.
Change. Q4 weights in the drafter head only.
Results. 176.37 → 182.60 tok/s, 4,400 tokens match. All 510 IDs of the first turn in 9 dialogs match.
Quality. Second turn of 1 Chinese dialog: the 8th token diverged. A differently accepted last token moved the snapshot boundary by 1 position.
Decision. Rolled back, the old configuration restored. The variant with an exact recheck in both heads matches on 1,158 IDs and on the boundaries of 9 dialogs.
Transfer. Any change in how drafter proposals are accepted can shift the snapshot boundary even when the IDs of the turn match. Cheapest test: a 2-turn replay with a snapshot in between.
Materials. A/B report, 2-turn replay report.
```
