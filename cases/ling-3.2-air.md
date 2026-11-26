# Case: Ling-3.2-air

Runs on `maya-ling` (the `ling32-air` branch of Maya, PR [#1224](https://github.com/mw00/project-maya/pull/1224), Wave 2-3 final revision `0b14d202`) with a float64 reference, `llama.cpp Q8_0` parity gate, and original published FP8 safetensors gate on November 24-25, 2026. The hardware is the rig in [README.md](README.md): 1x, 2x, 3x, or 4x RTX 3090 (24 GB, 300 W, PCIe 3.0 x16 at ~13 GB/s per GPU), AMD EPYC 7642 (47 active cores, AVX2), and 512 GB 8-channel DDR4-2133.

## Shape and situation card

- **Parameters:** 124.4B total, 5.1B active per token. 42 trunk layers: 2 dense MLP lead layers (0, 1), 35 KDA linear attention layers (32 heads x 128), and 7 gated MLA layers (5, 11, 17, 23, 29, 35, 41) with 64-dim RoPE, head-wise sigmoid gate and no DSA indexer.
- **MoE:** 40 MoE layers (2..41) x 512 small experts (3 x 768 x 2,560 = 5.9M parameters each, 20,480 trunk experts) + shared expert + 8-group / top-4 / top-8 sigmoid router with renorm. Post-SiLU SwiGLU clamp on layers 34-41.
- **Drafter and vision:** optional `blk.42` MTP (512 experts) and `qwen3_moe_vit` + `linear_proj` Vision tower (`mmproj` BF16 829.1 MiB, 333 tensors) with 3D M-RoPE (`[8, 12, 12]`).
- **Vocabulary:** 157,184 entries.
- **Main test quant:** `Ling-3.2-air-R3-test.gguf` (58 GiB: IQ3_XXS routed gate/up + Q4_K down, edge layers 2, 3, 38-41 in Q4_K, ~2.61 MB average per expert). Oracle: `Ling-3.2-air-Q8_0.gguf` (127 GiB).
- **Placement and miss path:** layer split on 1-4 GPUs with an adaptive VRAM expert cache (~31-33% resident on 1 card, ~72-74% on 2 cards, 20,480/20,480 100% resident on 3-4 cards), an AVX2 CPU lane (`kCpu` on 1 card, CUDA-graphed `kGpu` on 2-4 cards), and buffered page-cache NVMe expert streaming (`--direct` opt-in) under strict RAM caps. Decode VRAM hit rates on R3: 83-88% cold / 89.0% at 260K filled / 94.9-96.1% warm on 1 card; 97-99.8% on 2 cards; 100% on 3-4 cards.

Tag line: `#offload #in-vram #cpu-lane #1gpu #multi-gpu #layer-split #drafter #long-context #pcie3 #zen2`

## Results on 1x and 2x RTX 3090 (R3 58 GiB, real prompts, temp=0)

| Setup | Prefill before -> after (tok/s) | Decode before -> after (tok/s) | Where |
|---|---|---|---|
| 1x RTX 3090, 8K ctx (2K prompt) | 492.7 -> 668.4 (warm stall 0.95 s -> 0.000 s) | 57.95 (`gpu`) / 74.18 (`cpu`) -> 79.24-82.55 (`k=0`), 106.69 (`MTP auto`) | [02](../playbook/02-serving-a-miss.md), [07](../playbook/07-prefill.md), [08](../playbook/08-speculative-decoding.md) |
| 1x RTX 3090, 36K ctx (32K prompt) | 211.4 -> 2,081.0 (9.84x) | 45.10 -> 73.54 (`k=0`, +63.1%) | [02](../playbook/02-serving-a-miss.md), [07](../playbook/07-prefill.md) |
| 1x RTX 3090, 262K ctx (INT8 KV) | 709.7 at 260K | 77.01 (2K prompt), 51.51 at 260K filled (89.0% hits), 100+ with MTP at 2K | [02](../playbook/02-serving-a-miss.md), [07](../playbook/07-prefill.md) |
| 1x RTX 3090, cold decode (EN / Code / Edit) | | 76.01-83.96 (`k=0`) -> 106.06-114.28 (`MTP auto`), 115.15 (`k=2` code) | [08](../playbook/08-speculative-decoding.md) |
| 2x RTX 3090, 8K ctx (2K prompt) | 853.6 -> 1,252.2 (warm stall 0.52 s -> 0.000 s) | 96.68 -> 120.31 (`k=0`, +24.4%), 143.79 (`MTP auto`, +48.7% vs v0) | [02](../playbook/02-serving-a-miss.md), [07](../playbook/07-prefill.md), [08](../playbook/08-speculative-decoding.md) |
| 2x RTX 3090, 36K ctx (32K prompt) | 248.0 -> 3,119.3 (12.58x) | 76.89 -> 102.54 (`k=0`, +33.4%) | [02](../playbook/02-serving-a-miss.md), [07](../playbook/07-prefill.md) |
| 2x RTX 3090, 262K ctx (INT8 KV) | 1,265.6 at 260K; 1,339.3 on 250K NIAH | 102.03 -> 117.83 (2K prompt), 38.63 -> 63.49 at 260K filled (+64.4%) | [02](../playbook/02-serving-a-miss.md), [07](../playbook/07-prefill.md) |
| 2x RTX 3090, cold decode (EN / RU / Code / Edit) | | 102.68-109.23 (`k=0`) -> 116.75-128.95 (`MTP auto`), 125.87 (`k=2` edit) | [08](../playbook/08-speculative-decoding.md) |

Note on baselines: earlier v0 draft notes listed 570.8 / 990.1 tok/s prefill and 83.6 / 89.1 / 102.2 tok/s decode on a synthetic 2K token stream with higher VRAM hit locality. On the same real `ids_2048.txt` prompt, v0 measured 492.7 / 853.6 prefill and 57.95 / 74.18 / 96.68 decode.

Additional verified results:

- **250K Needle-in-a-Haystack (2x RTX 3090, 262K INT8 KV):** 249,995 tokens prefilled at 1,339.3 tok/s, verbatim needle recall (`ZEBRA-7492-QUARTZ`), clean EOS stop.
- **Vision (`qwen3_moe_vit` + `linear_proj`, 2x and 1x RTX 3090):** lent-VRAM block-streaming keeps `mmproj` mmap'd in host RAM (0.00 GiB permanent VRAM), encodes in 221-255 ms/img (cosine 0.999093 vs PyTorch BF16), passes OCR and 4-quadrant spatial recall, and fits full 262K context + image on 1x RTX 3090 at 22.37 / 23.56 GiB VRAM with 6,200 expert slots preserved ([12](../playbook/12-loading-and-big-tables.md)).
- **Multi-turn HTTP KDA prefix cache (2x RTX 3090, 32K ctx, MTP `auto`):** 4-slot host-RAM snapshots (~75-76 MiB/slot, ~6 ms restore) cut TTFT from 1.01 s (1,490 prompt tokens) to 0.21 s (1,517 tokens), 4.8x speedup ([11](../playbook/11-sessions-and-prompt-cache.md)).
- **Quality parity (`Q8_0` 127 GiB oracle and original published FP8 safetensors):**
  - vs `Q8_0` (`124` tokens): final FP16 KV matched `ref_f64` at 113/124 (91.1%, KL 0.0155) and INT8 KV at 117/124 (94.4%, KL 0.0153), on par with `llama.cpp Q8_0` (114/124, KL 0.0187). MTP vs `ref_f64` matched 26/26 (100.0%).
  - vs original published FP8 safetensors (after `if (n_res < n_expert)` guard): `KL = 0.1229`, `100.0%` (`149/149`) confident (`p >= 0.9`) top-1 match, `1.06x` thinking length (`5/5` cleanly closed).
  - Cross-topology parity (`--repeatable` / `--lane-parity`): disabling cross-layer `add2 + rmsnorm` fusion at stage boundaries gave bit-exact greedy hashes (`ee05493bd54bf1c4`) across 1 GPU (0/10 GiB VRAM) and 4 GPUs (0/10 GiB/100% VRAM).

## Final `0b14d202` FP16-KV `--bench`, 4-GPU, VRAM Emulation & NVMe Results (Nov 25, 2026)

| Setup | Metric | Result | Where |
|---|---|---|---|
| 1x RTX 3090 (`./maya.py --bench`, FP16 KV) | Decode / 30K filled | `67.4-69.2` tok/s (`69.1/69.2` FP16 vs `69.1/68.0` INT8; 30K filled `56.14` vs `56.18`) | [01](../playbook/01-cost-model.md), [09](../playbook/09-quants.md) |
| 2x RTX 3090 (`./maya.py --bench`, FP16 KV) | Decode / 8K / 32K prefill | `105.4` decode / `3,044` 8K prefill / `2,523` (up to `2,543`) 32K prefill | [07](../playbook/07-prefill.md), [08](../playbook/08-speculative-decoding.md) |
| 4x RTX 3090 (20,480/20,480 resident, FP16 KV) | Decode / 32K prefill | `124.4` decode / **`5,439` tok/s** 32K prefill (`6.02 s`, `2.44x` over serialized `2,230`, `2.14x` over 2x) | [05](../playbook/05-multi-gpu.md), [07](../playbook/07-prefill.md) |
| 8 / 12 / 16 GB VRAM emulations | MTP start-plan invariance | all start-plans invariant whether `--mtp` is enabled or disabled | [08](../playbook/08-speculative-decoding.md) |
| Cold-cache `cgroup v2` NVMe (`58 GiB`, `0.00%` `mincore()`) | `MemoryMax=8G` / `24G` (`MemorySwapMax=0`) | Buffered `4.80-6.01` (`8G`) and `7.75-9.10` (`24G`) vs `O_DIRECT` `3.16-3.89` and `3.98-4.81` tok/s (`+45-92%`, 0 OOMs) | [02](../playbook/02-serving-a-miss.md), [12](../playbook/12-loading-and-big-tables.md) |

## What worked

- Tiled online-softmax Flash-MLA (`BQ=256, BK=512`), macro-block MoE prefill borrowing unused expert cache tail (`BigScratch`), contiguous `kStage=128` staging ring with 1x `moe_sort`, and multi-GPU micro-batch stage pipelining (including the `32 MiB/GPU` `pf_pipe_x` buffer when `ngpu >= 2` and 100% resident): 32K prefill x9.84 (1 card), x12.58 (2 cards), and `5,439 tok/s` on 4 cards ([05](../playbook/05-multi-gpu.md), [07](../playbook/07-prefill.md)).
- Inline D2D cache warm from `pf_stage` during prefill: eliminated the 0.52-0.95 s post-prefill stall ([04](../playbook/04-live-expert-cache.md), [07](../playbook/07-prefill.md)).
- `TILE=32` WMMA split-K MLA decode + fused residual/RMSNorm/Q8_0 + packed 96-byte CPU route struct + O(N) adaptive fetch + async CPU-lane cache admission: 260K filled decode +64.4% on 2 cards ([02](../playbook/02-serving-a-miss.md), [04](../playbook/04-live-expert-cache.md)).
- `blk.42` MTP with exact KDA state/conv rollback, CUDA-graphed `W=1..4` verify, on-device `0.50` confidence gating, and `--drafting auto` (low `be=0.25` backoff on 1x CPU lane + suffix lookup): +33-41% on 1 card, up to 143.8 tok/s on 2 cards, 256/256 greedy bit-exact parity ([08](../playbook/08-speculative-decoding.md)).
- Lent-VRAM block-streaming Vision, 4-slot RAM KDA prefix cache, and `.lingrp` model-keyed bounded opt-in restore points ([11](../playbook/11-sessions-and-prompt-cache.md), [12](../playbook/12-loading-and-big-tables.md)).
- Buffered page-cache default for `cgroup v2` NVMe expert streaming (`--direct` opt-in, [12](../playbook/12-loading-and-big-tables.md)), `if (n_res < n_expert)` identity slot guard ([03](../playbook/03-expert-profile-and-placement.md)), and `--repeatable` / `--lane-parity` boundary norm-fusion guard ([15](../playbook/15-quality-and-release-gates.md)).

## What did not work, and bugs caught

- **4-GPU `pf_pipe_x` skipped when 100% resident (`PF-21`):** skipping the stage pipe buffer when no H2D eviction was needed forced `use_stage_pipe = false`, serializing all 4 GPU stages (`2,230` vs `5,439 tok/s` at 32K) ([05](../playbook/05-multi-gpu.md), [07](../playbook/07-prefill.md)).
- **Profile permutation when `n_res == n_expert` (`PL-23`):** moving 100%-resident slots away from `slot == expert_id` on 3-4 GPUs broke all-VRAM fast paths (`KL = 5.399`, `11.5%` top-1, `4.48x` unclosed thinking); fixed by `if (n_res < n_expert)` + model-free C++ unit test ([03](../playbook/03-expert-profile-and-placement.md), [15](../playbook/15-quality-and-release-gates.md)).
- **`O_DIRECT` default for cold-cache `cgroup v2` NVMe streaming (`AG-15`):** lost by 45-92% to buffered page-cache reads (`8G` and `24G` caps) because hot MoE experts stay warm in kernel page cache without duplicate block reads. Also caught a Linux `>= 6.8` `tmpfs` `/dev/shm` `O_DIRECT` CI trap ([12](../playbook/12-loading-and-big-tables.md), [14](../playbook/14-benchmarking-and-traps.md)).
- **Cross-GPU stage boundary `add2 + rmsnorm` fusion (`MG-18`):** caused 1-ULP rounding drift between 1-GPU and 4-GPU runs (`710abbff` vs `ee05493b`); gated off under `--repeatable` / `--lane-parity` ([15](../playbook/15-quality-and-release-gates.md)).
- **INT8 KV default on sparse-MLA hybrid (`PL-24`):** 7 MLA layers at 32K saved only `102 MiB` (40/20,480 slots), gave zero speed gain (`69.1/69.2` vs `69.1/68.0`), and flipped 3/4 greedy hashes (`KL 0.0001-0.016`); kept FP16 KV default ([01](../playbook/01-cost-model.md), [09](../playbook/09-quants.md), [15](../playbook/15-quality-and-release-gates.md)).
- **2-GPU EP prefill relay (`--ep-prefill`):** lost to micro-batch stage pipelining when ~73% of experts were resident in VRAM (`--no-ep` stayed default) ([07](../playbook/07-prefill.md)).
- **Splitting 128x128 KDA decode recurrence across 8 thread blocks (`kda_rec_split=8`):** global reduction overhead made it slower than 1-block 256-thread register recurrence ([02](../playbook/02-serving-a-miss.md)).
- **Uncapped 47 CPU threads on Zen 2:** regressed decode by -10 tok/s vs 12-24 threads due to DDR4 controller contention; capped at `min(phys_cores, 24)` ([02](../playbook/02-serving-a-miss.md)).
- **High MTP backoff threshold (`be=0.50`) on 1x GPU:** prematurely paused drafting and dropped `1x_code` from 114.3 to 96.1 tok/s; tuned to `be=0.25` ([08](../playbook/08-speculative-decoding.md)).
- **Bugs caught during parity checks:** conditional `__syncthreads()` inside `kda_rec_window_q8_kernel` (`first_diff=3..22` on greedy MTP); off-by-1 RoPE position in `mtp_draft` (-5-7% acceptance); cross-layer `pf_stage`/`pf_pmap` DMA reuse race (KL `7.70e-3 -> 6.98e-3`); mutable host step buffer and missing reverse-edge P2P sync under `--prefill-chunk 1` CUDA graphs.

Full list with numbers: [ledger](../ledger/hypotheses.md), rows marked LING.
