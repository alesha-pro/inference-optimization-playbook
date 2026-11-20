# Case: DeepSeek V4.1 Flash

Runs on Maya (a Strata fork for DeepSeek) with our patches, on the rig in [README.md](README.md).

## Shape

- 40 trunk layers × 384 experts, top-6. Drafter DSpark: 3 blocks × 128, top-3. 15,744 experts, 240 picks per token.
- Engram (n-gram tables): 161 GB, read from the page cache.
- Quants: Maya-S (experts IQ2-IQ3, 10.6-12.6 MB each, 169 GB of experts) and unsloth UD-IQ3_S (13.8-18.8 MB each, 253 GB).
- Routing skew is clear: top-100 of 384 cover 70% of picks, ~194 effective experts per layer.

## Live service layout

7,392 of 15,744 experts in VRAM (about 20 GB per card), 92.7 GB of copies in pinned RAM, Engram from the page cache. Layer split over 4 cards, CPU lane for decode misses, live cache with decay.

## Where it ended up

| What | Number |
|---|---|
| Decode, Maya-S vs UD-IQ3_S | 70.1 vs 53.6 tok/s |
| Full session replay, Maya-S vs UD | 720 vs 992 s |
| Prefill 32K, stock → our build | 430 → 2,199 tok/s |
| Re-read of 1.5K tokens | 2.9 s (floor 1.6-2.2 s, calc) |
| Round time fit | 22.4 ms + 5.1 ms × rows + 13.4 ms × rows × miss rate |
| CPU share of a round after all fixes | ~10% |

## What worked

- CPU lane instead of the PCIe stream in decode: +17% on 2-channel RAM ([02](../playbook/02-serving-a-miss.md)).
- PDEP fix on Zen 2: one cold expert 1.6 → 0.44 ms.
- DMA from pinned copies for all formats, layer skip on the prompt, auto chunk: prefill 32K 430 → 2,199 tok/s ([07](../playbook/07-prefill.md)).
- EP in prefill over idle PCIe links: re-read of 1.5K -42%.
- RAM copies of borrowed experts plus incremental prompt prep: turns -14.7% ([11](../playbook/11-sessions-and-prompt-cache.md)).
- A service profile accumulated on real agent work: 86% coverage vs 68% for stock ([03](../playbook/03-expert-profile-and-placement.md)).
- NPS2 with NUMA-aware copies on a partial DIMM population, then 8 channels ([06](../playbook/06-cpu-and-ram.md)).
- THP only for the duration of the expert copy, no page cache drop on 503 GiB ([12](../playbook/12-loading-and-big-tables.md)).
- Q8 matvec on int8 tensor cores: decode +5.6%, bit for bit ([mw00/project-maya#810](https://github.com/mw00/project-maya/pull/810)).

## What did not

- TP=2 with P2P: decode +7%, but reading 344K is 2.2x slower and EP stops working.
- Warming the cache from the prompt (`DS4_SETTLE_MS`): +21-24% on a short test, zero on free generation.
- Profile refresh for the task, a "faster" live cache, thread pinning to near CCX, SMT, generic prefetch.
- Fine-tuning DSpark on our quant's answers: 3.215 → 3.17-3.20 tokens per round.
- Engram in RAM instead of the page cache: 0-1.3% for +30-45 s of loading.
- EP in decode (llama.cpp, V4 fully in VRAM): -34%.

## What the live session showed

295 turns, context up to 279K: generation 77% of time, reading 23%. Median of new prompt tokens per turn: 243. 4 reads from scratch took 24% of all reading ([11](../playbook/11-sessions-and-prompt-cache.md)).

## Lessons that transfer

1. Once misses are ~10% of a round, stop adding VRAM for experts and work on the constant part.
2. A short test promised +27% for the UD quant, real generation gave +2%. Decide on replay.
3. The profile file keeps growing. Freeze a copy per A/B arm.
