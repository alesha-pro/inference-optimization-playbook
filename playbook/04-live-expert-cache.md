# The live expert cache

Covers DeepSeek V4.1 Flash, MiniMax-M3.1-Flash, GLM-5.3-Flash, Qwen3.8-Flash-Next, Hy4 Flash.

> **Read when:** experts move between RAM and VRAM while the engine runs, or a static set is close to random. **Skip when:** everything fits in VRAM. **Ledger tags:** `#offload` `#weak-skew` `#strong-skew`.

A live cache moves an expert from RAM to VRAM when it gets hot in the current request and evicts one that cooled down.

## Implementations we ran

| Engine | Policy | Parameters |
|---|---|---|
| Maya for DeepSeek | heat with decay. An expert moves up if its heat > heat of the coldest one in VRAM × 1.25 + 1 | decay ×0.9 every 256 tokens, up to 8 swaps at once, 1 per layer |
| maya-mm3 for MiniMax | decaying counters (half-life ~230 tokens), async swap on a separate copy stream | up to 8 moves per token per model, no more than 4 in flight per layer |
| Our exllamav3 fork for GLM | CLOCK cache in VRAM on top of a fixed hot set | 180-480 slots. Admission to the cache only for small batches |
| Strata for Qwen | `--expert-cache auto`: sized to free VRAM, adapts to routing | the first requests after start are slower |
| Maya for Hy4 Flash | start from the profile of past answers, change the GPU cache content by decaying frequency | after prefill the freed VRAM also goes to experts (see below) |

## What different policies gave (MiniMax, simulator on traces of real answers)

| Policy | Hits |
|---|---|
| static placement by profile | 64-69% |
| random placement | 61% |
| 1 swap per token | 72-83% |
| up to 8 swaps per token (service) | 87-93% |
| LFU with decay, budget 8 | 89-96% |
| LRU that adds on every miss | 93-97% (but 6-15 moves per token) |
| oracle: best static set per answer | 90-97% |
| Belady (perfect eviction) | 97-99% |

Capacity vs misses on MiniMax (simulator with the service policy): 56 slots per layer → 82-91% hits, 64 → 87-93%, 72 → -25% misses, 80 → -44%, 96 → -70%. One slot on all 57 layers costs 1.03 GB. Another analysis with the LRU policy showed the opposite: +7 slots per layer add only 0.7-1.6 points. The better the cache policy, the less capacity matters. In the live MiniMax service hits were 71-94% by logs and 85% on a replay of real sessions.

On GLM a live cache of 480 slots on top of 50% fixed experts gave 94-95% hits. The simulator showed that with 66% of experts in VRAM you get 19-23 misses per token under any split of memory between the fixed set and the cache.

## Hy4 Flash: adaptive cache on 1 and 2 GPUs

| What we tried | Result | How to check transfer |
|---|---|---|
| Start from the profile of past answers and change the GPU cache by decaying frequency | After 57K on 2 GPUs a 600-token generation gave 81 tok/s, a 1,200-token one 91-97 as hits grew. In a real session the profile changed together with the task | Alternate topics. Compare a start with an empty cache, a warmed answer and a return to the earlier topic. Record the time spent moving weights |
| Give the free prefill memory to experts during decode | On 1 GPU the permanent and the temporary sets were merged into one adaptive cache. The CPU also parallelized the quantization of intermediate activations. These are parts of the single-GPU build from [07](07-prefill.md) | Compare the number of resident experts, hits and latency on the transitions prefill → decode → new prefill. Fix the budget for both runs |

A long control with the same task in an agent harness (DSH) gave for the final 2-GPU base: 47 calls, context up to 97,834, average decode 74.2 tok/s, range 51-87, VRAM hits 79.8%. An early version of the CPU lane without prefetch got 47.8 tok/s in another session on the same task. The agent trajectories differed, so the gap between the sessions cannot be assigned to one fix.

## Observations

- **Short answers do not warm the cache.** Agent tool calls (23-132 tokens) on MiniMax got 71-76% hits vs 85-93% on long answers.
- **A live cache makes output non-deterministic.** An expert runs on the GPU one time and on the CPU the next, so summation order and rounding differ. MiniMax service answers matched at temp 0 in only 1 case of 99. Moving 513 experts between CPU and GPU gives top-1 99.1% and KL 0.0028. This is normal, but freeze the cache when you test quality.
- **Warming from the prompt after prefill.** Idea: after reading a long prompt, immediately move up the experts that were hot in it. On DeepSeek (`DS4_SETTLE_MS`) a short test showed +21-24% decode, and free generation showed zero with TTFT +0.3-1.9 s. Rejected. On MiniMax the same trick (copying the expert from the prefill buffer, ~20 µs instead of 1.25 ms over PCIe) stayed in the plan.
- **A separate profile refresh for the task** (refresh on 24 prompts) did not help on DeepSeek: the live cache catches up in 1-2 requests. Upstream on AMD hardware reported the same trick lifting hits on the first answer from 42 to 75% (ext). It did not reproduce for us.
- **A "fast" live cache** (less hysteresis) on DeepSeek was worse: 36.4 vs 39-40 tok/s. Frequent swaps cost time by themselves.

## Predicting the next experts

| What | Result |
|---|---|
| Loading the "almost picked" experts of the previous token (GLM) | did not work: 22.9-30.9 misses vs 23.2. Neighbor tokens pick different experts |
| Predicting the router of layer L+1 from the input of layer L (MiniMax, offline) | top-8 catches 84-90% of the real picks, top-16 93-95%. For L+2 top-8 catches 73-83% |
| Same for GLM (sim) | 1 block ahead, 75% of the real 8 are in the top-8. Estimate +20-28% decode at 3.05 bpw. Not implemented |

The limit: an expert takes 1.4 ms over PCIe 3.0 and a layer takes 0.4-0.7 ms. Prefetch only makes it 2 or more layers ahead, where prediction is worse. On our hardware this is more of a hint for the cache and for the CPU work order than real prefetch. A faster link can help if transfers fit in the overlap window and leave enough GPU compute and host memory bandwidth for the rest of the layer.

### DeepSeek V4.1 Flash, next-layer prefetch into VRAM, 2026-10-23

DSX tested whether serving more decode misses on the GPU would shorten a token step. The control ran misses on the CPU. The candidate ran the next layer's router on the current layer's expert input, then copied up to 1 or 2 predicted CPU-resident experts into the main GPU and repacked their weights on a separate CUDA stream. Routing still used the next layer's actual picks.

The rig ran DeepSeek V4.1 Flash 1017 with T16 experts and IQ4_NL Engram, 2 RTX 3090s, an i7-12700K and 128 GB of dual-channel DDR4-3200. The main GPU used PCIe 4.0 x16, measured at about 24.6 GB/s from the host. The second GPU used PCIe 3.0 x4 and held a fixed set of experts. Each cell is 1 run of 400 generated tokens (ext). The log does not specify the prompt or seed.

| Decode | Prefetch off | Up to 1 expert per layer | Up to 2 experts per layer |
|---|---:|---:|---:|
| Expert deferral off | 33.12 tok/s | 25.30 tok/s | 22.19 tok/s |
| Lower-ranked CPU experts deferred by 1 layer | 37.35 tok/s | 28.30 tok/s | 20.66 tok/s |

With deferral off, the 2-expert variant handled 49.4% of the CPU-bound picks and cut CPU expert busy time from 12.2 to 6.3 ms per token. Decode still slowed by a third. The copy and repack kernels competed with attention on the GPU. The transfers also shared DRAM bandwidth with the CPU experts, and about half the copied experts went unused. On a separate 2,046-token decode eval, KL was 0.2082 with prefetch off and 0.2048 with the 2-expert variant. Top-1 agreement was 82.55% and 82.45%, respectively.

DSX left prefetch off. Revisit if weights can be copied in their final layout with DMA, or if a confidence threshold can cut wasted bytes enough to fit the available overlap. Time the whole decode step with prefetch off and on, and check attention time and concurrent DRAM reads. The fraction of CPU misses served by the GPU only measures one part of the change.

[DSX implementation](https://github.com/lxe/dsx/commit/ec68799ae659b31d01b2e2e6ddb74855b13b0af8), [benchmark log](https://github.com/lxe/dsx/blob/60e9870b74509825f2f8de088306d82260f0fd87/bench/results/2026-10-22-102/pf102.out#L4-L35), [resource budget](https://github.com/lxe/dsx/blob/60e9870b74509825f2f8de088306d82260f0fd87/docs/budget-102.md#4-dsx_prefetch-against-this-budget-negative-result).

## Transfer checklist

1. Run a cache simulator on real router traces before writing engine code: static, random, your policy, Belady. The gap between your policy and Belady is your headroom.
2. Sweep capacity with your policy. If +10% slots barely moves hits, capacity is not the lever.
3. Count swaps per token and their cost. A policy with more hits and many more moves can be slower.
4. Test on short answers separately (tool calls). They see a colder cache.
5. For any quality check, freeze the cache content.
6. Before enabling next-layer prefetch, measure how long copy and repack take alongside attention and CPU expert reads. Compare whole-token time with the same placement and cache policy.
