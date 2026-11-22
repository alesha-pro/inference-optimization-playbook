# Changelog

## 2026-11-21

- Added PL-22, a DSX measurement of next-layer expert prefetch during DeepSeek V4.1 Flash decode on 2 RTX 3090s, to chapter 04 and the DeepSeek case.
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
