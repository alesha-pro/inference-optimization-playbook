# CPU and RAM: channels, NUMA, "near" cores

Covers Qwen3.8-Flash-Next, DeepSeek V4.1 Flash, GLM-5.3-Flash, MiniMax-M3.1-Flash, Hy4 Flash. The CPU is an AMD EPYC 7642 (Zen 2, 48 cores, AVX2 without AVX-512, 16 CCX with 16 MB L3 each). RAM changed many times during the work, see [cases/README.md](../cases/README.md).

> **Read when:** the CPU computes part of the experts, or the RAM, BIOS or DIMM layout changed. **Skip when:** the CPU computes almost nothing in decode. **Ledger tags:** `#cpu-lane` `#ram` `#numa` `#zen2`.

## RAM bandwidth shows only when the CPU is on the path

| Case | Memory change | Effect |
|---|---|---|
| Qwen Flash-Next, Strata, 1 card (hits 74-79%, the CPU computes misses) | 4 → 8 channels (Triad 41 → 82) | decode +7-17% (code +14-18%, essay +8-15%, Russian +8-11%) |
| same, 2 cards (hits 92-95%) | same | 0 |
| same, prefill | same | 0 (experts go to the GPU over PCIe) |
| DeepSeek Maya-S | 4 channels NPS1 → 4 channels NPS2 → 8 channels | decode 46-57 → 67.7 → 82.3 on a short test. On real data the memory effect is about +3% and is not isolated. Re-read barely changed |
| GLM EXL3 4.05, Maya | 2 sticks → 6 sticks without pairs → 4 sticks in pairs | 21.8 → 27.8 → 29.9 tok/s |
| MiniMax, prefill | 2 → 8 channels | 1,120 → 1,130 (not limited by RAM) |

The mechanism: a miss in decode is computed on the CPU, the CPU streams the expert weights from RAM, and that is pure bandwidth. Prefill moves experts to the GPU and is limited by PCIe.

## How to populate the channels

- **The layout of sticks by pairs and channels matters more than their count.** On Rome (by AMD documentation) 6 channels give ~40% of the bandwidth of 8 (28% in the worst case), 7 channels 35% (14%), 4 in pairs 54%. On 7 sticks our Triad was 8.3-8.5 GB/s, unusable.
- **NPS1 on a partial population can split memory into 2 halves with no interleaving.** On 4 sticks the BIOS built 2 rules: channels A, B and channels C, D, with no interleaving between them. A buffer in 1 half gave Triad ~24 GB/s, split evenly across both 41-43. Model from 34 runs: `Triad = min(40, 24 / max(f, 1-f))`, where f is the share of traffic below the seam. Earlier conclusions about "heating" and "2 MB pages are slower than 4 KB" turned out to be this artifact.
- **NPS2 removed the halves and gave DeepSeek decode 67.7 vs 46.5-57.5 on NPS1.** But Linux saw 2 NUMA nodes, numa_balancing turned on, and without NUMA-aware copies (`DS4_COPY_NUMA=1`) it got worse: 31.8 tok/s.
- **LRDIMM overheating without airflow** drops Triad 3-4x within minutes: GLM 22.7 → 6.6 tok/s, Triad 33 → 9.8 GB/s. Airflow brings the speed back in a minute. Constant airflow over the sticks is mandatory.

## "Near memory" and "near" cores: what we checked

The idea: keep warm experts on the memory channels closest to the cores that compute them, and pin the CPU lane threads to "near" CCX. We did not build a separate "near memory" tier (none of the engines we used has one). We checked its necessary condition: do near cores and thread pinning give anything. The DeepSeek numbers below were taken on 4 sticks (Triad ~44), not 8.

| Check | Result |
|---|---|
| 23 "near" threads vs 47 on 1 cold expert (DeepSeek) | -10 to +3% |
| same on 4 and 12 experts | worse by 9-38% |
| all 94 threads with SMT vs 47 | worse everywhere, by 2-148% |
| pinning CPU lane threads to cores/CCX (MiniMax, 46 threads) | worse: 21.7 vs 23.7 tok/s (not the best variant: the main thread was not pinned) |
| `DS4_LANE_CCX` (pinning parts of the work to CCX) on 8 channels | almost nothing (-6.4% vs -7.9% of call time) |
| software prefetch in the CPU lane | -1 to +3% |
| latency to memory from different CCDs | CCD 0-3 139-149 ns, CCD 4-7 168-172 ns |

Why it does not work: 1 expert is read as a stream, and the bandwidth of 1-2 channels is not enough. One thread gets ~21-23 GB/s here and bandwidth plateaus at 4-8 threads. Our estimate (calc, we did not read the fabric frequency) is that the limit is the link between the CCD die and the memory controller, not the distance to the channel. It is better to spread every expert over all channels (interleaving) and read it with all threads than to pin it to "its own" channels.

On a 2-socket machine or with NPS4 this can be different (the cross-socket link is much slower). We did not test that.

## What worked for the CPU lane

- The PDEP fix ([02](02-serving-a-miss.md)): ×3.6.
- A set of CPU lane fixes for DeepSeek (shorter serial part of the call: input quantization, output sum, copies on 2 MB pages): short test +7.8% (Maya-S), +5.7% (UD). On real generation inside the noise (66.0 → 70.1).
- Splitting CPU lane work by dot products instead of by rows (MiniMax): +16-23% in speculation windows. The reason: 40% of the lane time was waiting for the slowest thread (groups with a repeated expert are 2-3x heavier).
- Thread count: Strata 0.1.45 on 1 card set 46 threads on 48 cores by itself and dropped to 20-60 tok/s. 32 threads gave ~75, version 0.2 sets 32 itself and holds ~87. **The CPU lane thread count is critical.** SMT does not help.
- Row prefetch on deep context (Hy4 Flash): at depth, the time of a request to the CPU lane grew from 0.39 to 0.88 ms. Prefetching rows brought it back to 0.33 ms. With 40, 46 and 80 threads the results were close, 67-70 tok/s. If one more thread gives nothing, look at RAM bandwidth and CPU cache misses on a long request.
- AVX2+FMA CPU offload lane on Zen 2 (`MS-17`, 2026-11-26): when an engine ships only AVX-512 plus a scalar fallback for 2-bit/3-bit expert offload, AMD Zen 2 (EPYC 7642) and AVX2-only desktops drop onto the scalar path, losing 9-12x on prefill and 2x+ on decode (observed on a 280B 2.3 bpw MoE). Implement an explicit AVX2+FMA lane and verify dispatch at build or startup so AVX-512-only code never degrades silently to scalar.

Note the 2 prefetch results. Software prefetch in the DeepSeek CPU lane gave -1 to +3%. Row prefetch on Hy4 at depth took a CPU lane request from 0.88 back to 0.33 ms. We did not test why they differ.

## Place whole layers on the CPU at deep context (Inkling 2 Mini, 2026-11-21)

Inkling 2 Mini has 24 physical MoE layers. The middle 12 run 3 times per token. At large depths an FP8 global KV cache alone can occupy 16 GiB on one RTX 3090. A host implementation ranked whole layers by visits per byte of expert weights. It chose layers with the lowest ratio until enough VRAM was free. AVX2, FMA and F16C executed the gate, up and down dot products on 24 EPYC 7642 threads. The GPU applied routing, SwiGLU and its FP16 rounding. Copy traffic per selected layer consisted of activations, outputs and 8 expert IDs.

With 15,995 actual input tokens and a synthetic KV tail, GPU staging alone gave 32.35, 16.94 and 10.55 tok/s at 524,288, 786,432 and 1,048,064 positions. The selected host layers gave 41.63, 26.14 and 18.13. Sending all layers to the CPU at the last depth gave 13.38. These controlled placement tests used 8-channel DDR4-2133, PCIe 3.0 x16 and a 300 W GPU. The production service keeps this host path disabled below 524,288 positions.

## A hand-written Q8_0 matvec on 1 pinned Zen 1 die (llm.asm, 2026-11-26)

External result (ext) from a homelab, not this rig.

Load and criterion. CPU-only decode and prompt reading on a small dense model, Qwen3-0.6B Q8_0. Both engines use Qwen's release: llama.cpp reads Qwen's Q8_0 GGUF, llm.asm reads its own Q8_0 export of the same safetensors.

Control. llama.cpp master `074f1f3`, `llama-bench -ngl 0` (tg64 at depth 0, pp34, pp512). llm.asm `48feccb`, `make inference FAST_Q8=1`, 64 tokens after a 34-token chat prompt. AMD EPYC 7601 (Zen 1, AVX2, no AVX-512, 8 NUMA nodes). Both engines on 1 die: `taskset` to 1 CPU per physical core on node 0, 2 DDR4 channels, both model files rewritten from node 0 so their page cache is local. 3 runs each, interleaved, spread under 0.5%.

| Threads | llm.asm decode | llama.cpp tg64 | Ratio | llm.asm pp512 | llama.cpp pp512 | Ratio |
|---:|---:|---:|---:|---:|---:|---:|
| 1 | 18.58 | 16.62 | 1.12x | 22.38 | 27.99 | 0.80x |
| 4 | 48.38 | 42.30 | 1.14x | 56.98 | 90.96 | 0.63x |
| 8 | 48.76 | 46.78 | 1.04x | 58.46 | 175.37 | 0.33x |

The llm.asm README reports 1.24x / 1.36x / 1.28x decode on an EPYC 7642 (ext).

Why. At 8 threads llm.asm moves about 30.9 GB/s of weights and llama.cpp about 29.6 GB/s (calc: bytes a token x tok/s), about what 2 DDR4 channels give, so the kernel stops mattering there. The integer core is the same in both engines (`vpsignb`, `vpmaddubsw`, `vpmaddwd`). The differences: llama.cpp's x86 decode dot `ggml_vec_dot_q8_0_q8_0` runs 1 block an iteration into 1 accumulator with 2 scalar fp16 scale converts a block, while llm.asm runs 4 blocks into 4 independent accumulators, converts 4 scales in 1 `vcvtph2ps`, keeps the int8 weights of a row contiguous and 64-byte aligned with the scales after them, and runs Q+K+V and gate+up as 1 fused matmul behind 1 barrier. This run did not split the 4-14% between the kernel and the fusion. Prompts go the other way: llm.asm runs 1 GEMV pass a prompt token and saturates at about 58 tok/s from 4 threads, while llama.cpp runs a tiled GEMM that reuses each weight block across tokens.

The trap. The first pinned run, with the model files' pages left where the download wrote them, gave llm.asm 8.93 / 11.29 / 11.43 tok/s and llama.cpp 16.81 / 41.94 / 45.57. The same binaries gave llm.asm 48.76 once the file was rewritten from node 0. That run measured where the pages sat on an 8-node box, not the kernel. Pinning threads is not enough when the engine maps a file: read or rewrite it from the pinned node first and check `numa_maps`.

Not settled. On a Ryzen 9 9950X3D (AVX-512 VNNI) the runs had no exclusive cores and spread 10-28%, so they do not separate the engines. There llama.cpp's native build compiles the same dot to `vpdpbusd`, and llm.asm has no VNNI path.

Decision: microtest only. Transfer: the 4-accumulator unroll and the vector scale handling fit into `ggml_vec_dot_q8_0_q8_0` with no format change. The split-row layout is a format change, an x86 branch of the Q8_0 CPU repack buffer. Measure on 1 die with local pages and stop at the bandwidth wall.

## Transfer checklist

1. Run STREAM Triad by thread count before anything else. Find the plateau.
2. Check the DIMM population against the platform's channel rules. Check the NUMA layout the BIOS built (`numactl -H`, interleaving rules).
3. Run Triad before and after every benchmark series. If it dropped, the series does not count (heat).
4. Sweep the CPU lane thread count on your real load. Do not use SMT threads.
5. More RAM channels help decode only if the CPU computes a meaningful share of experts. Check the hit rate first.
