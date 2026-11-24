# Case: Ling-3.2-air

Runs on `maya-ling` (the `ling32-air` branch of Maya, draft PR [#1224](https://github.com/mw00/project-maya/pull/1224)) with a float64 reference and `llama.cpp Q8_0` parity gate on November 24, 2026. The hardware is the rig in [README.md](README.md): 1x or 2x RTX 3090 (24 GB, 300 W, PCIe 3.0 x16 at ~13 GB/s per GPU), AMD EPYC 7642 (47 active cores, AVX2), and 512 GB 8-channel DDR4-2133.

## Shape and situation card

- **Parameters:** 124.4B total, 5.1B active per token. 42 trunk layers: 2 dense MLP lead layers (0, 1), 35 KDA linear attention layers (32 heads x 128), and 7 gated MLA layers (5, 11, 17, 23, 29, 35, 41) with 64-dim RoPE, head-wise sigmoid gate and no DSA indexer.
- **MoE:** 40 MoE layers (2..41) x 512 small experts (3 x 768 x 2,560 = 5.9M parameters each, 20,480 trunk experts) + shared expert + 8-group / top-4 / top-8 sigmoid router with renorm. Post-SiLU SwiGLU clamp on layers 34-41.
- **Drafter and vision:** optional `blk.42` MTP (512 experts) and `qwen3_moe_vit` + `linear_proj` Vision tower (`mmproj` BF16 829.1 MiB, 333 tensors) with 3D M-RoPE (`[8, 12, 12]`).
- **Vocabulary:** 157,184 entries.
- **Main test quant:** `Ling-3.2-air-R3-test.gguf` (58 GiB: IQ3_XXS routed gate/up + Q4_K down, edge layers 2, 3, 38-41 in Q4_K, ~2.61 MB average per expert). Oracle: `Ling-3.2-air-Q8_0.gguf` (127 GiB).
- **Placement and miss path:** layer split on 1 or 2 GPUs with an adaptive VRAM expert cache (~31-33% resident on 1 card, ~72-74% on 2 cards) and an AVX2 CPU lane (`kCpu` on 1 card, CUDA-graphed `kGpu` on 2 cards). Decode VRAM hit rates on R3: 83-88% cold / 89.0% at 260K filled / 94.9-96.1% warm on 1 card; 97-99.8% on 2 cards.

Tag line: `#offload #cpu-lane #1gpu #multi-gpu #layer-split #drafter #long-context #pcie3 #zen2`

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
- **Quality parity (`Q8_0` 127 GiB oracle, 124 tokens):** final FP16 KV matched `ref_f64` at 113/124 (91.1%, KL 0.0155) and INT8 KV at 117/124 (94.4%, KL 0.0153), on par with `llama.cpp Q8_0` (114/124, KL 0.0187). MTP vs `ref_f64` matched 26/26 (100.0%).

## What worked

- Tiled online-softmax Flash-MLA (`BQ=256, BK=512`), macro-block MoE prefill borrowing unused expert cache tail (`BigScratch`), contiguous `kStage=128` staging ring with 1x `moe_sort`, and 2-GPU micro-batch stage pipelining: 32K prefill x9.84 (1 card) and x12.58 (2 cards) ([07](../playbook/07-prefill.md)).
- Inline D2D cache warm from `pf_stage` during prefill: eliminated the 0.52-0.95 s post-prefill stall ([04](../playbook/04-live-expert-cache.md), [07](../playbook/07-prefill.md)).
- `TILE=32` WMMA split-K MLA decode + fused residual/RMSNorm/Q8_0 + packed 96-byte CPU route struct + O(N) adaptive fetch + async CPU-lane cache admission: 260K filled decode +64.4% on 2 cards ([02](../playbook/02-serving-a-miss.md), [04](../playbook/04-live-expert-cache.md)).
- `blk.42` MTP with exact KDA state/conv rollback, CUDA-graphed `W=1..4` verify, on-device `0.50` confidence gating, and `spec=auto` (low `be=0.25` backoff on 1x CPU lane): +33-41% on 1 card, up to 143.8 tok/s on 2 cards, 256/256 greedy bit-exact parity ([08](../playbook/08-speculative-decoding.md)).
- Lent-VRAM block-streaming Vision and 4-slot RAM KDA prefix cache ([11](../playbook/11-sessions-and-prompt-cache.md), [12](../playbook/12-loading-and-big-tables.md)).

## What did not work, and bugs caught

- **2-GPU EP prefill relay (`--ep-prefill`):** lost to micro-batch stage pipelining when ~73% of experts were resident in VRAM (`--no-ep` stayed default) ([07](../playbook/07-prefill.md)).
- **Splitting 128x128 KDA decode recurrence across 8 thread blocks (`kda_rec_split=8`):** global reduction overhead made it slower than 1-block 256-thread register recurrence ([02](../playbook/02-serving-a-miss.md)).
- **Uncapped 47 CPU threads on Zen 2:** regressed decode by -10 tok/s vs 12-24 threads due to DDR4 controller contention; capped at `min(phys_cores, 24)` ([02](../playbook/02-serving-a-miss.md)).
- **High MTP backoff threshold (`be=0.50`) on 1x GPU:** prematurely paused drafting and dropped `1x_code` from 114.3 to 96.1 tok/s; tuned to `be=0.25` ([08](../playbook/08-speculative-decoding.md)).
- **Bugs caught during parity checks:** conditional `__syncthreads()` inside `kda_rec_window_q8_kernel` (`first_diff=3..22` on greedy MTP); off-by-1 RoPE position in `mtp_draft` (-5-7% acceptance); cross-layer `pf_stage`/`pf_pmap` DMA reuse race (KL `7.70e-3 -> 6.98e-3`); mutable host step buffer and missing reverse-edge P2P sync under `--prefill-chunk 1` CUDA graphs.

Full list with numbers: [ledger](../ledger/hypotheses.md), rows marked LING.
