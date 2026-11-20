# Case: Qwen3.8-Flash-Next

Runs on Strata (0.1.40 to 0.2.x), on the rig in [README.md](README.md).

Public recipe with raw traces: [alesha-pro/qwen38-flashnext-strata-4x3090](https://github.com/alesha-pro/qwen38-flashnext-strata-4x3090).

## Shape

- 48 layers × 512 experts, 24,576 in total, ~6B active parameters per token.
- n-gram (PLE) table 27-29 GB.
- Main quant: unsloth UD-IQ4_XS (experts 62 GB). Also IQ3_S and UD-Q4_K_XL.
- Strong routing skew: ~24% of experts in VRAM give 74-79% hits, ~53% give 92-95%.

## Where it ended up

Layer split, CPU computes misses, live cache `--expert-cache auto`, DFlash2 drafter with a Cyrillic draft vocabulary, session files.

| What | Number |
|---|---|
| Decode by cards (UD-IQ4_XS, 16K essay, 4 RAM channels) | 1: 90-93, 2: 121-130, 3: 127-129, 4: 118-129 tok/s |
| Prefill 64K by cards | 1,930 / 3,390 / 3,850 / 4,080 tok/s |
| DFlash2 vs no draft | +44-46% (1 card 70 → 102-103, 2 cards 78 → 112) |
| DFlash2 vs built-in MTP | +7-13% |
| 4 → 8 RAM channels | 1 card +7-17%, 2 cards 0, prefill 0 |
| Quants on 2 cards, prose | IQ3_S 138-147, UD-IQ4_XS 126-130, UD-Q4_K_XL 102-110 tok/s |
| Session restore at 120K | 7.2 s vs 34.7 s of cold prefill |

## What worked

- The second card: +31-38% decode. Cards 3 and 4 add only prefill ([05](../playbook/05-multi-gpu.md)).
- Confidence threshold 0.5 instead of 0.35: +8-15% ([08](../playbook/08-speculative-decoding.md)).
- A Cyrillic draft vocabulary: acceptance on Russian 32% → 54%, 78-81 → 94-101 tok/s, no training.
- 32 CPU threads instead of 46 on 1 card: 20-60 → ~75 tok/s ([06](../playbook/06-cpu-and-ram.md)).
- A smaller context window (128K instead of 262K): +3-5% decode, VRAM went to experts.
- The n-gram table on NVMe with direct reads: -27 GiB of RAM for -3% prefill ([12](../playbook/12-loading-and-big-tables.md)).
- The gpu-unlock module (full-speed fp32-accumulate tensor kernels on GeForce): prefill +10-12%.
- Session files under layer split: byte-for-byte answer after restore ([11](../playbook/11-sessions-and-prompt-cache.md)).

## What did not

- Helper cards for experts instead of layer split: -25-30% (IQ3_S, old Strata 0.1.40).
- Fine-tuning a drafter (DSpine) from DFlash2 weights: τ +4% against a +10% threshold, 2/3 of it from the vocabulary.
- Fused prefill expert kernels: +13% but KL 0.033 vs stock, not shipped.
- Threshold 0.65: worse than 0.5.

## Ceilings

At T=1 the model takes its own top token in 79% of positions. The ceiling of any drafter is +20% (Russian +32%, reasoning +14.6%). Reasoning is 55% of the tokens of our answers.

## Lessons that transfer

1. Count the cards that improve decode. Past the point where hits are above 90%, more cards only help prefill.
2. Check the drafter's vocabulary and threshold for your language before training anything.
3. RAM channels matter only where the CPU computes a real share of experts.
