# Glossary

| Term | Meaning |
|---|---|
| Expert | one FFN subnetwork in an MoE layer. The router picks k experts per token |
| Miss | an expert was picked that is not in VRAM |
| Hit rate | the share of picks served from VRAM |
| Skew | how unevenly the router distributes picks across experts |
| Effective experts | `exp(entropy of the pick distribution)` for a layer |
| Profile | pick counters of experts on a representative load |
| Live cache | the mechanism that changes the set of experts in VRAM while running |
| CPU lane | computing misses on the CPU straight from RAM |
| Layer split | layers are cut into pieces per card, the cards work in turn |
| TP | tensor parallel: every layer is divided between the cards |
| EP | expert parallel: experts of one layer are computed on different cards |
| All-reduce | the exchange that sums partial results of TP ranks |
| Prefill | processing the input that is already known |
| Decode | generating the continuation |
| Re-read | prefill of the new tokens on top of an already processed context |
| TTFT | time from sending the request to the first token at the client |
| KV cache | stored intermediate keys and values of attention |
| Prefix cache / prompt cache | reuse of the state of the common part of a request |
| Expert cache | holds expert weights in VRAM. Not the same as the KV or prefix cache: different keys, memory budgets and hit criteria |
| Chunk / block | how many tokens prefill processes with one load of experts |
| Tile | how many activations are materialized at once inside a block |
| Pinned RAM | page-locked memory that a GPU can reach by DMA without a copy |
| DMA | direct transfer between pinned host memory and the GPU |
| P2P | direct transfer between 2 GPUs over PCIe, without the host |
| THP | transparent huge pages in Linux (2 MB) |
| NPS | NUMA nodes per socket on AMD EPYC. Affects channel interleaving |
| CCD / CCX | chiplet and core complex on AMD EPYC |
| Triad | the STREAM test of memory bandwidth |
| Drafter | a small model or head that proposes several next tokens |
| Verify | the step where the target model checks the drafter's proposals as a batch |
| MTP | multi-token prediction, a drafter head built into the model |
| DFlash2, DSpark, DSpine, DFly2 | drafters used with these models: DFlash2 with Qwen and GLM, DSpark with DeepSeek and MiniMax, DSpine in a Qwen training test, DFly2 in a Hy4 test |
| τ | tokens per speculation round (accepted drafts + 1) |
| Window, rows | the positions verified in one round |
| Teacher forcing | feeding both builds the same token IDs to compare logits |
| KL / KLD | divergence between the distributions of a quant and the reference |
| NLL | negative log-likelihood of the actual token |
| REAP | expert importance score: mean router weight × norm of the output |
| REAM | merging removed experts into the remaining ones |
| bpw | bits per weight |
| Engram, PLE | large n-gram embedding tables that some of these models carry next to the weights |
| SWA, DSA | local (sliding window) attention and sparse attention with an indexer in Hy4 Flash |
| Maya-S, Maya-M, UD-* | names of specific quants: our own Maya quants and unsloth dynamic quants |
