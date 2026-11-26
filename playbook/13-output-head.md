# The output head

Covers Hy4 Flash (vocabulary 120,832, BF16 head). Applies to any model where the projection onto the vocabulary is a visible share of the decode step, dense models included.

> **Read when:** the projection onto the vocabulary is a visible share of the decode step. **Skip when:** it is a few percent of the step. **Ledger tags:** `#head`.

## What worked: a cheap estimate with an exact recheck

The original projection reads BF16 weights for the full vocabulary. For greedy we tested a cheaper Q8 estimate plus a conservative error bound for every row. Rows that can still win are recomputed with the original weights. For the drafter the second candidate is checked too. On a tie the order of token IDs matters.

For sampling you need the original distribution or a separately verified selection algorithm that accounts for temperature, penalties and bias.

The proof for greedy depends on the number format, the reduction order and the rounding mode of the specific kernel. It does not carry over to another kernel for free.

## What had to be rolled back

Q4 only in the drafter head looked good: in the first A/B 176.37 → 182.60 tok/s with 4,400 tokens matching. All 510 IDs of the first turn in 9 additional dialogs matched too.

But a differently accepted last token shifted the snapshot boundary by 1 position. In the second turn of 1 Chinese dialog the 8th token diverged. The old config was restored.

A variant with an exact recheck in both heads matched on all 1,158 IDs and on the boundaries of 9 dialogs.

The lesson for any "safe" drafter change: a single-turn check is not enough. All first-turn IDs matched, but a last token that was accepted differently shifted the snapshot boundary by 1 position, so the second turn started from a different saved state. Run a 2-turn replay ([15](15-quality-and-release-gates.md)).

## What stayed in the lab

Q2 with a short candidate list and an exact BF16 recheck returned the original first 2 IDs on 720 of 720 recorded states. But a conservative bound by norms left a median of **120,832 of 120,832** rows for the recheck. So the guarantee cost at least a full pass.

On a new model, first look at the distribution of the number of candidates after applying the bound. The size of the initial list and success on a held-out set do not tell you the cost of a guaranteed answer.

## Sampling candidates on the device (Inkling 2 Mini, 2026-11-21)

Copying 200,058 logits to the host and sorting them cost ~0.8 ms a token. A histogram of 1,024 bins over the softcapped range finds the bin from which the top 1,000 start, and only those (1,000-2,400) go to the host: sampling 100 → 110 tok/s, the same tokens for the same seed.

## A contrastive guide from an earlier loop pass (Inkling 2 Mini, LoopCD-Logits, 2026-11-26)

External result (ext) from a homelab with 1 RTX 3090 Ti, not this rig.

LoopCD-Logits (arXiv 2610.02185) is meant for looped models. Inkling 2 Mini runs its middle layers 3 times a token. The guide runs the last 6 layers a second time on the state after the first loop pass, sends the final row and this early row through one 2-row head, and moves the final logits away from the early ones: `z' = z + w (z - z_ref)`, `w = omega_max x (1 - (p1 - p2))` from the top 2 probabilities of the final row. Settings: `omega_max` 0.5, control tokens keep their final logits, and the text tokens keep the total probability of the final distribution. 2 arms: the guide only outside thinking blocks, and the guide inside thinking too.

Control. Inkling 2 Mini IQ4_NL (17.6 GB), llama.cpp `e58e0c7f7` with a patch, CUDA, every layer on the card, q8_0 K/V, `-fa on`. At strength 0 the patched build matched the unpatched one on token IDs and top-5 logprobs, 5 prompts x 256 tokens. The arms of 1 problem ran as 1 request with `n_cmpl 3`, so they share the prompt state and decode in the same batches (see the traps in [14](14-benchmarking-and-traps.md)).

| Benchmark | Off | Guide outside thinking | Guide inside thinking too |
|---|---:|---:|---:|
| HumanEval+ base / plus, 164 tasks | 98.2% / 92.1% | same, 0 discordant pairs | not run |
| LiveCodeBench v5 + v6, the first 104 of 342 problems in a seeded order, effort low, greedy | 61.5% | 60.6%, -1.0 points [-2.9, 0.0], 1 discordant pair | 60.6%, -1.0 [-7.7, +4.8], 11 discordant (6 lost, 5 won) |

Intervals are 95% paired bootstrap. All 36 discordant answers were graded a second time with the same verdicts.

| Cost | Off | Guide on |
|---|---:|---:|
| tg128 | 62.36 tok/s | 55.79 (-10.5%) |
| pp512 | 1,639.2 tok/s | 1,476.7 (-9.9%) |
| Long answers at the default thinking effort, up to 8,192 tokens, 3 problems x 2 builds interleaved | 58.48 tok/s | 52.47 (-10.3%) |
| K/V buffers | | +12.5% (6 more layer visits, 48 → 54) |

The head is nearly free with 2 rows. The extra layer visits are the cost.

What it did. Outside thinking, the thinking block stayed bit-identical to the off arm on all 104 problems. The guide changed the final answer on 36 and the outcome of 1, a loss. On HumanEval+ it changed the text of 95 answers and the outcome of none: imports moved, annotations added, loops reordered. Inside thinking, the guided answer left the off arm at token 2-73 (median 7). Its outcomes moved 6 down and 5 up.

Limits. At effort low the model thought 4,683 tokens a problem on average, and 31 of 47 hard answers hit the 10,240-token cap inside thinking, so the hard bucket mostly measures the cap. With 104 problems the inside-thinking arm resolves only about ±6 points.

Verdict, with conditions (◐ in `HD-05`). No gain on single-shot coding (LiveCodeBench, HumanEval+) at 4-bit weights and effort low. That is narrower than the authors' claim, which is about agentic coding. What matched the authors: `omega_max` 0.5, adaptive strength, the guide only outside thinking, control tokens untouched (the settings of omlx PR #5640), and strength 0 bit-exact against the unpatched engine. What did not: the benchmarks (single-shot, not agentic), the weights (IQ4_NL; 4-bit noise may blur the contrast between the first and the third loop pass that the guide amplifies), the effort (low, with a cap that cut off most hard answers mid-thinking), and the sample size. Retest when any of these changes: agentic coding benchmarks, 8-bit or 16-bit weights, default effort or a larger thinking budget, factuality tasks, or enough problems to resolve the inside-thinking arm.

Decision: not served. Revisit with a larger thinking budget on hard problems and more problems for the inside-thinking arm. Raw token streams, grades and the patch are available on request.

## Transfer checklist

1. Profile the decode step. If the head is a few percent, skip this chapter.
2. Build the cheap estimate and a per-row error bound. Count how many rows survive the bound on recorded states. If almost all survive, stop.
3. For greedy: recheck survivors with the original weights, handle ties by token ID.
4. For sampling: keep the original distribution unless you have a verified selection algorithm.
5. Test over at least 2 turns with a snapshot in between, in several languages.
6. For a logit guide (contrastive decoding and the like), measure the gain on a benchmark with headroom and pair the arms on the same prompts. A benchmark at 92-98% has nothing to win.
