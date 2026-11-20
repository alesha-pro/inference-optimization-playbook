# Case: Tencent Hy4 Flash

Runs on Maya (a new model port), with a first reference in patched llama.cpp, on November 18-20, 2026. The rig is the one in [README.md](README.md), with 1, 2 or 4 RTX 3090 at 300 W, P2P over PCIe, 8 channels of DDR4 and 512 GB of RAM.

Public engine notes at a fixed revision: [project-maya docs/HY4-FLASH.md at 82a77bf](https://github.com/alesha-pro/project-maya/blob/82a77bf/docs/HY4-FLASH.md). Upstream PRs: [#1062](https://github.com/mw00/project-maya/pull/1062), [#1068](https://github.com/mw00/project-maya/pull/1068).

This case is the most complete record of one port from parity to release, with the same engine run on 1, 2 and 4 cards.

## Shape

- A sparse MoE: the router picks 16 experts of 512 per token.
- Alternating layers of local attention (SWA) and sparse attention with an indexer (DSA).
- A large n-gram embedding table, Engram: 660,006,416 rows × 96 bytes = 59.009 GiB.
- A built-in MTP drafter and a vision projector.
- So table placement, expert placement and dialog state could be changed independently. On a dense model without a router, the tests with attention, exchange, the output head and the dialog cache still apply.

The main Maya series uses the AngelSlim Q3_K GGUF, MTP Q3_K, Q8 KV and a 262,144 window. "Reference" below means a specific named build and its weights. Most numbers are for 1 active request.

## How the work went

| Stage | What we learned |
|---|---|
| Nov 18, llama.cpp with a model patch | First built the full profile with MTP, vision and long context. At 128K it gave about 435 tok/s prefill and 29 decode. A config with a shortened context was much faster |
| Nov 18, port into Maya | Comparing intermediate tensors, a GPU path for MoE, tensor parallel, KV and CUDA Graphs gave a working engine. Then batch prefill, normal decode and MTP verify were profiled separately |
| Nov 18-19, 4 cards | Changed the exchange between cards, optimized attention, projections, generation and the server. On a full cold HTTP input the prefill block target was reached. The lower bound of decode stayed open |
| Nov 19, 2 cards | The boundary between RAM and VRAM started to set the cost of a step. What helped: computing rare experts on the CPU, an adaptive GPU cache, prefetch and staging |
| Nov 19, 1 card | For long prefill, raised the number of tokens served by 1 load of experts. After prefill the same VRAM went to experts for decode |
| Nov 19-20, lower-RAM variants | Tested separately: direct Engram reads from NVMe, IQ2 for experts only, and both together. These changes have different prices and numeric effects |
| Nov 20, upstream | 2 ideas ported into upstream Maya v1.1.69 and compared with the clean version |

## Results by number of cards

| Cards | Prefill | Decode | Where |
|---|---|---|---|
| 4 | 262,135 fresh tokens over HTTP at 2,873.5 tok/s, worst of 128 blocks 2,576.10 | 187.67 tok/s over 16 answers of 400 tokens, worst answer 159.35, worst 32-token window at depth 261,632: 132.49 | [15](../playbook/15-quality-and-release-gates.md) |
| 2 | 846 → 1,225 → 1,588 tok/s at blocks 2,048 / 4,096 / 8,192 | CPU lane 24.6 → 70.4 tok/s on short code. Long agent control: 74.2 tok/s average, 51-87 range, 79.8% VRAM hits | [02](../playbook/02-serving-a-miss.md), [04](../playbook/04-live-expert-cache.md), [07](../playbook/07-prefill.md) |
| 1 | 57,587 tokens: 415.6 → 1,510.2 tok/s. 261,888 tokens: 420.0 → 1,422.5 | 39.69 → 53.70 tok/s at 57K | [07](../playbook/07-prefill.md) |
| 1, IQ2 experts + Engram on NVMe | 1,184 tok/s on 49K of code | 54.0 tok/s, service pinned 45.4 GiB of RAM | [09](../playbook/09-quants.md), [12](../playbook/12-loading-and-big-tables.md) |

## What worked

- A host F32 reference and stage-by-stage parity before any GPU work ([14](../playbook/14-benchmarking-and-traps.md)).
- One expert load per logical block of up to 57,600 tokens with attention in tiles of 2,048: single-card prefill ×3.4-3.6 for the full build ([07](../playbook/07-prefill.md)).
- Cold experts on the CPU in parallel with hot ones on the GPU ([02](../playbook/02-serving-a-miss.md)).
- Decode all-reduce as one 8-byte word, prefill exchange through peer DMA ([05](../playbook/05-multi-gpu.md)).
- A Q8 head estimate with an error bound and an exact recheck ([13](../playbook/13-output-head.md)).
- Engram through `O_DIRECT`: pinned RAM 137.2 → 78.2 GiB ([12](../playbook/12-loading-and-big-tables.md)).
- 2 dialog snapshots in pinned RAM: TTFT on A → B → A 9.617 → 0.477 s ([11](../playbook/11-sessions-and-prompt-cache.md)).
- Each expert on 1 card and TP under partial placement, both ported upstream ([05](../playbook/05-multi-gpu.md)).

## What did not, or was rolled back

- DFly2, a separate wider drafter: 126 vs 153 tok/s for native MTP K=2.
- Every drafter training variant: within noise.
- Q4 in the drafter head without a recheck: faster, matched on the first turn, diverged on the second.
- Layer split instead of TP on 4 cards: 25-35% slower with MTP.
- Lossless compression of experts, an INT8 indexer, an early KV snapshot copy, unified kernels across phases, THP for expert storage.
- A release candidate that improved one minimum and lowered the mean: rejected.

Full list with numbers: [ledger](../ledger/hypotheses.md), rows marked HY.

## Lessons that transfer

1. Separate "tokens served by one expert load" from "activations materialized at once". On 1 card the build that introduced this split gave ×3.4-3.6 prefill (the number is for the full build, not for the split alone).
2. A profile of the prompt does not predict the experts of the answer (48% vs 96% coverage). Start from past answers and adapt.
3. Test the second turn. The first turn matched on a change that was wrong.
4. Name the release number: mean, worst block, worst answer or worst rolling window, and at what depth.
5. When porting an idea to another engine, compare against that engine's clean version. The baseline moved.
