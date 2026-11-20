# Cases: the rig and the models

Numbers in this repo were taken on the hardware below unless they are marked (ext), (sim) or (calc), or the text names other hardware (the GLM domain atlas was recorded in the cloud). Read this page before you compare any number with your own.

## The rig

| What | Value | Why it matters |
|---|---|---|
| GPU | 4x RTX 3090 24 GB (Ampere sm_86), 96 GB VRAM, no NVLink | VRAM is short for these models, so everything is about offload |
| Bus | PCIe 3.0 x16 on every card (risers), P2P between cards works | 13 GB/s RAM→GPU per card, 52 GB/s for all 4 at once. A miss over the bus is expensive |
| CPU | AMD EPYC 7642 (Zen 2, 48 cores, AVX2, no AVX-512), 16 CCX with 16 MB L3 each | the CPU computes decode misses |
| RAM | DDR4 LRDIMM, the config changed many times (see below) | RAM bandwidth shows directly in decode when the CPU computes misses |
| GPU power | 300 W per card (220 W before Sep 26, 2026) | matters when old and new numbers are compared |

RAM history in 2026:

| Period | Config | STREAM Triad |
|---|---|---|
| until Oct 31 | 2 channels | about 30 GB/s |
| Nov 1 | 4 channels (NPS1, then NPS2) | |
| Nov 1-3 | 8 channels | 66-73 GB/s under load |
| Nov 4-7 | 7 sticks, then 4 sticks (NPS2) | ~41 GB/s on 4 sticks |
| from Nov 8 | 8 channels DDR4-2133, 503 GiB | 82 GB/s on 8 threads |

**Numbers taken on different RAM configs do not compare with each other.** The RAM config changed several times during the work and was the main source of confusion.

## The models

| Model | Experts | Picks per token | Notes | Case |
|---|---|---|---|---|
| DeepSeek V4.1 Flash | 40 layers × 384, top-6 + DSpark drafter (3 blocks × 128, top-3). 15,744 in total | 240 | Engram (n-gram tables) 161 GB | [deepseek-v4.1-flash.md](deepseek-v4.1-flash.md) |
| Qwen3.8-Flash-Next | 48 layers × 512, 24,576 in total | ~6B active parameters per token | n-gram (PLE) table 27-29 GB | [qwen3.8-flash-next.md](qwen3.8-flash-next.md) |
| GLM-5.3-Flash | 42 MoE layers × 288, top-8 + a shared expert, 12,096 in total | 336 | KV is almost free (34 linear attention layers of 45) | [glm-5.3-flash.md](glm-5.3-flash.md) |
| MiniMax-M3.1-Flash | 57 MoE layers × 128, top-4 + shared, 7,296 in total | 228 | an expert at 2 bits is ~15-18 MB, large | [minimax-m3.1-flash.md](minimax-m3.1-flash.md) |
| Hy4 Flash | 512 experts per layer, top-16 | | SWA and DSA attention layers, Engram 59 GiB, built-in MTP drafter, vision projector, 262,144 window | [hy4-flash.md](hy4-flash.md) |

Quants used for the main work:

- DeepSeek: our own Maya-S quant (experts IQ2-IQ3, 10.6-12.6 MB per expert, all experts 169 GB) and unsloth UD-IQ3_S (253 GB).
- Qwen Flash-Next: unsloth UD-IQ4_XS (experts 62 GB).
- GLM: EXL3 2.05 / 3.05 / 4.05 bpw and Maya-M.
- MiniMax: unsloth UD-Q2_K_XL and Maya-S.
- Hy4 Flash: AngelSlim Q3_K GGUF with MTP Q3_K and Q8 KV, plus an IQ2 expert set for the low-RAM modes.

Engines: Strata, its Maya forks (for DeepSeek, GLM, MiniMax, Hy4), our fork of exllamav3, llama.cpp and vLLM.

## Which case is closest to your model

| Your model looks like | Start with |
|---|---|
| Strong routing skew, many experts per layer | Qwen3.8-Flash-Next, DeepSeek V4.1 Flash |
| Weak global skew, few large experts | MiniMax-M3.1-Flash, GLM-5.3-Flash |
| Fits fully in VRAM at low bits on several cards | GLM-5.3-Flash (TP section) |
| A huge side table next to the weights | DeepSeek (Engram 161 GB), Hy4 Flash (Engram on NVMe) |
| A fresh port into a new engine, from parity to release | Hy4 Flash |
| 1 or 2 consumer GPUs and a lot of RAM | Hy4 Flash, Qwen3.8-Flash-Next |
