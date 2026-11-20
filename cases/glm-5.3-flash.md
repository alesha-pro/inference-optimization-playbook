# Case: GLM-5.3-Flash

Runs on our fork of exllamav3 and on Maya (a Strata fork for GLM), on the rig in [README.md](README.md).

Public fork: [alesha-pro/exllamav3-glm53-4x3090](https://github.com/alesha-pro/exllamav3-glm53-4x3090).

## Shape

- 42 MoE layers × 288 experts, top-8 + a shared expert. 12,096 experts, 336 picks per token.
- KV is almost free: 34 linear attention layers of 45.
- Quants: EXL3 2.05 / 3.05 / 4.05 bpw, Maya-M.
- Weak global skew: the "cold" half of experts gets 41% of picks, 0 dead experts on 42 layers. Inside one request a live cache gives 94-98% hits.
- Loses quality to quantization several times faster than Qwen Flash-Next (KL at 2.05/3.05/4.05 = 0.19/0.068/0.035, ext).

## Where it ended up

| Config | Number |
|---|---|
| 2.05 bpw, fully in VRAM, layer split → TP4 | 48.3 → 66-68 tok/s |
| same + MTP with draft length 1 | 75.7 tok/s |
| 3.05 bpw with offload, our fork, no draft → MTP length 1 | 38.7 → 45.2 tok/s |
| TP4 with a RAM tier: no VRAM cache → CLOCK cache at 94-95% hits | 19.8 → 37.6-38.7 tok/s (stock layer split with a CPU tail: 11.5), 2-channel RAM |
| Prefill in TP: host all-reduce → P2P exchange in 2 rounds | 961 → 1,447 tok/s |
| Maya, Maya-M quant, 2-channel RAM: stock (cold experts on the CPU) → calibration that sent 75% of misses to PCIe | 24.9 → 45-46 tok/s |
| Mixed bits (gate/up 2 + down 3) | 79% of experts in VRAM, 69 tok/s, KL 0.096 |

Time model in Maya at 4.05: `t ≈ 9.5 ms + 866 MB / RAM-to-GPU bandwidth`. 68.5 misses per token.

## What worked

- TP when the model is fully in VRAM ([05](../playbook/05-multi-gpu.md)).
- Our own RAM tier and a CLOCK VRAM cache under TP (stock exllamav3 forbids expert offload in TP).
- P2P all-reduce for prefill.
- MTP with draft length 1 (the default 3 gave zero or negative) ([08](../playbook/08-speculative-decoding.md)).
- A larger prefill chunk: 2048 → 4096 gave 764 → 1,000 tok/s.
- REAP as a way to rank experts: 19-22 of 25 tasks vs 4-9 for frequency ([10](../playbook/10-pruning-and-merging.md)).

## What did not

- A static hot set: cuts misses by only 10%.
- Loading the "almost picked" experts of the previous token: no gain, 22.9-30.9 misses per token vs 23.2.
- P2P all-reduce for decode in TP: -6%.
- DFlash2 with a long window in Maya: only +4% over MTP.
- Masking experts outside VRAM: KL 0.372 at 34% forbidden vs 0.047 for the full 3.05.
- REAM (merging): layer output error 0.449 vs 0.146 for plain removal (1 layer, 991 positions, not model quality).
- The pruned 108-of-288 model: we did not trust it, and it ran at 10.8 tok/s on 4 cards. A month later the full model on another engine ran at 43 tok/s at 3 bits with offload and 79 at 2 bits fully in VRAM (different engine, power limit and speculation, so a reference point, not a clean comparison).

## Hardware lessons from this case

- LRDIMM overheating without airflow: 22.7 → 6.6 tok/s within minutes ([06](../playbook/06-cpu-and-ram.md)).
- DIMM layout: 2 sticks → 6 without pairs → 4 in pairs gave 21.8 → 27.8 → 29.9 tok/s.
- An idle calibration put 11 CPU threads on 4 cards and DFlash2 fell from 21.8 to 8.1.

## Lessons that transfer

1. Check skew before building a static placement. On this model it was almost useless.
2. If the model fits in VRAM at fewer bits, compare "fewer bits + TP" against "more bits + offload" on quality and speed.
3. Pruning by frequency or by "not in VRAM" is worse than losing a bit on every expert.
