# Case: MiniMax-M3.1-Flash

Runs on maya-mm3 (a Maya fork for MiniMax), on the rig in [README.md](README.md).

## Shape

- 57 MoE layers × 128 experts, top-4 + a shared expert. 7,296 experts, 228 picks per token.
- Experts are large: ~15-18 MB at 2 bits.
- Quants: unsloth UD-Q2_K_XL and Maya-S.
- Weak global skew: random placement gives 61% hits, placement by profile 64-69%, an oracle on the answer itself 95-99% (sim). The working set fits in VRAM, but every answer has its own.

## Where it ended up

Layer split, CPU lane for misses, live cache with decaying counters (half-life ~230 tokens, up to 8 moves per token), DSpark drafter with a cost-based window policy.

| What | Number |
|---|---|
| Live cache hits | 71-94% in service logs, 85% on a replay of real sessions |
| Hits by policy (sim) | static 64-69%, live with 8 swaps 87-93%, Belady 97-99% |
| Prefill, 2 → 8 RAM channels | 1,120 → 1,130 tok/s (not limited by RAM) |
| Attention K/V gathered into VRAM | prefill 64K ×3.3, session replay 4,050 → 1,084 s (1 run) |
| DSpark on synthetic prompts | 17-25 → 21-29 tok/s (+16-24%) |
| DSpark on 2K of real agent context, before fixes | 27.0 → 25.0 tok/s (negative) |
| Synthetic vs real content | 42 tok/s on "write an analysis" vs 26 on real sessions |

## What worked

- A live cache. On this model it is the main mechanism, the static profile is close to random ([04](../playbook/04-live-expert-cache.md)).
- Removing the PCIe stream of misses in decode: an expert takes 1.4-1.5 ms to copy, a full layer takes 0.4-0.7 ms ([02](../playbook/02-serving-a-miss.md)).
- Splitting CPU lane work by dot products instead of rows: +16-23% in speculation windows ([06](../playbook/06-cpu-and-ram.md)).
- Gathering K/V into VRAM once per chunk plus an LRU pool in decode: the attention kernel had been reading the same host RAM blocks 73-383 times per chunk ([07](../playbook/07-prefill.md)).
- A cost-based window policy for the drafter: +3-13% ([08](../playbook/08-speculative-decoding.md)).

## What did not

- A static profile: 64-69% vs 61% random (sim).
- Pinning CPU lane threads to cores/CCX: 21.7 vs 23.7 tok/s (not the best variant: the main thread was not pinned).
- TP only for attention: decode +3-10%, prefill -4.8%. Left behind a flag.
- Skipping RAM experts with a small routing weight: top-1 98.9%, KL 0.0049, did not pass the quality gate.
- top-3 or top-2 instead of top-4: NLL +46% and up to +250%.

## Traps found here

- `save_profile` ran only on a clean exit and the service was stopped with SIGTERM. The "service profile" was a snapshot of ~300 tokens of 1 session.
- The live cache makes output non-deterministic: service answers matched at temp 0 in 1 case of 99.
- Short tool calls (23-132 tokens) see a colder cache: 71-76% hits vs 85-93% on long answers.
- Before the attention fix, a replay of real sessions spent 87% of the time reading. It looked like an expert delivery problem and was not.

## Lessons that transfer

1. Simulate "profile vs random" at your VRAM budget before investing in profiling.
2. When a miss copy costs more than a layer, compute misses on the CPU.
3. Profile prefill on long context. The limit can be attention reading from host RAM.
