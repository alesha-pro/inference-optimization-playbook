# Changelog

## 2026-11-26

- Updated Ling-3.2-air (`maya-ling`, PR `#1224` Wave 2-3): 4-GPU resident `pf_pipe_x` stage pipelining (32K FP16-KV prefill `2,230 -> 5,439 tok/s`), resident identity expert-slot order guard (`KL 5.399 -> 0.1229`), cold-cache `cgroup v2` buffered vs `O_DIRECT` NVMe expert streaming (`+45-92%` buffered; Linux `>= 6.8` `tmpfs` `O_DIRECT` CI trap), cross-GPU stage boundary norm-fusion parity (`--repeatable` / `--lane-parity`), sparse-MLA FP16 vs INT8 KV (`PL-24`), and final `0b14d202` baselines, `.lingrp` restore points, and `--drafting auto`.
- Added generalized 4x RTX 3090 PCIe 3.0, P2P, and 2-bit quant kernel findings: TP=4 decode vs `--tp 1` prefill split (`MG-19`, `PF-22`), direct posted-write 2-hop P2P all-reduce + bidirectional startup probe (`MG-20`), `Q8_1 __dp4a` bit-invariant IQ2 decode (`QP-17`), full-warp `F16_SMEM` `uint4` dequant + Ampere MMA prefill with `sm_75` arch guard (`QP-18`), and AVX2+FMA CPU lane vs scalar fallback on Zen 2 (`MS-17`). Total hypotheses: 138 (`PL-23..24`, `MS-17`, `MG-18..20`, `PF-21..22`, `QP-17..18`, `AG-15`, plus `AG-12` updated).

## 2026-11-24

- Added Ling-3.2-air (`maya-ling`) on 1x and 2x RTX 3090: 12 ledger rows (`PL-22`, `MS-14..16`, `MG-17`, `PF-18..20`, `SD-17..18`, `AG-13..14`), sections in chapters 02, 04, 07, 08, 11, 12, and `cases/ling-3.2-air.md`. Documented tiled Flash-MLA and macro-block prefill, inline D2D cache warm, `TILE=32` MLA decode, `blk.42` MTP with exact KDA state rollback, 4-slot RAM KDA prefix cache, lent-VRAM block-streaming Vision (`qwen3_moe_vit`), and negative results (`--ep-prefill` at ~73% residency, `kda_rec_split=8`, uncapped 47 CPU threads, `be=0.50` MTP backoff).

## 2026-11-21

- Added Inkling 2 Mini on one RTX 3090. Documented on-demand global KV, depth-dependent CPU placement, exact scalar codebook lookup, two-limb NVFP4 products and verified suffix copying.

## 2026-11-21, Inkling 2 Mini engine

- Inkling 2 Mini resident engine: 14 rows (PL-15..21, PF-16..17, SD-16, HD-04, QP-15..16), sections in chapters 03, 07, 08, 09, 13, 14, the case file extended.

## 2026-11-21, the map

- The entry page is now a map: 7 questions by regime plus the entry by symptom.
- New: situation card, experiment rules, a traits table for the 5 models, a section on ceilings in chapter 01.
- Every ledger row has condition tags. Every chapter says when to read it and when to skip it.
- New tools: `route_sim.py` (routing skew and cache simulator), `fit_cost.py` (time model fit).

## 2026-11-21

- First public version. 16 chapters, 97 hypotheses in the ledger, 5 model cases.
- Sources: the MoE expert offload handbook (July to November 2026: DeepSeek V4.1 Flash, Qwen3.8-Flash-Next, GLM-5.3-Flash, MiniMax-M3.1-Flash) and the Hy4 Flash port notebook (November 18-20, 2026).
