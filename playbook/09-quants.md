# Quants: bits vs the number of experts in VRAM

Covers Qwen3.8-Flash-Next, DeepSeek V4.1 Flash, GLM-5.3-Flash, Hy4 Flash, Mirai quants of Qwen.

Decode speed under offload follows how many experts fit in VRAM and the cost of a miss (the size of an expert). Fewer bits → more experts in VRAM → fewer misses → faster. At the price of quality.

Qwen Flash-Next, Strata, 2 cards, 16K:

| Quant | Experts in VRAM | Prose | Code | KL to Q8_0 (Strata's number, ext) |
|---|---|---|---|---|
| IQ3_S | 16,869 | 138-147 | 164-166 | 0.144 |
| UD-IQ4_XS | 12,949 | 126-130 | 146-149 | 0.101 |
| UD-Q4_K_XL | 9,798 | 102-110 | 117-119 | 0.056 |

DeepSeek: Maya-S (experts 10.6-12.6 MB) vs UD-IQ3_S (13.8-18.8 MB): decode 70.1 vs 53.6 tok/s, full session 720 vs 992 s. The re-read on UD takes 2x longer, exactly by the bytes of the cold experts. The quality gap on our text is small: KL between them 0.029, and a battery of 150 answers did not tell them apart.

## Observations

- **Models lose quality to quantization at different rates.** GLM loses several times more than Qwen Flash-Next: 3 bits of GLM is about 2 bits of Qwen (by turboderp's KL charts, ext: GLM 2.05/3.05/4.05 = 0.19/0.068/0.035, Qwen 0.068/0.018/0.0067).
- **Mixed bits inside an expert.** GLM: gate/up at 2 bits + down at 3 bits gave 79% of experts in VRAM and 69 tok/s at KL 0.096. But "the third bit in down is free quality" was not confirmed: per unit of size, down is only ~17% more useful than gate/up. EXL3 quality is almost linear in the size of the experts.
- **KL and NLL do not catch garbage.** One DeepSeek quant (SAGE-EXL3, 1.62 bits) would have passed on logits, and on live generation it produced garbage in Russian. We caught it only by reading the output.
- **Mirai Flash-Next-S** (a trellis quant, experts at 2.4 bits on average): on 1 card decode 82-88 vs 74-84 for IQ3_S, peak RAM 41-42 GiB vs 53, prefill 20-25% slower. Mirai states KL 0.040 to bf16 (ext). Their Strata patch had a bug on 2 cards: the rotation constants were written only to the first card, and the output was "!!!!". The fix was found on our rig and Mirai accepted it.
- **A model "past VRAM" over PCIe 3.0 barely works.** Mirai 27B XS in llama.cpp with a tail of weights outside VRAM: decode 2.8-4.7 tok/s at 126K even with sparse reads. The author got 16-17 on PCIe 4.0 (ext). A dense model pulls its tail on every token, an MoE pulls only misses.

## Replacing the quant of experts only, and a hybrid (Hy4 Flash)

**The test.** Only the experts of the main trunk were changed. Attention, the output head, Engram and MTP stayed original. 123 expert tensors from an IQ2 file were moved into one GGUF, and the origin of all 1,415 tensors was verified. In the hybrid the most often called experts were kept in the original quant. The price of this decision depends on the *share of calls* that lands on those weights.

| 2 cards, CPU lane | Decode of short code, tok/s | Quality vs the base on 512 positions |
|---|---:|---|
| Original experts | 70 | top-1 88.3%, median KL 0.0047 |
| Hybrid, about a third of calls in the original quant | about 90 | at 37% original calls: top-1 77.0%, KL 0.041 |
| IQ2 | 126 | top-1 75.6%, KL 0.070 |

Speed and quality here were taken on different inputs. A control permutation of the same original experts between 4 cards by itself gave top-1 88.3% and KL 0.0054. The move to IQ2 changed the distribution much more.

On **1** card you can see it in resources too: on 49K of code, Q3 in RAM gave 1,528 / 37.0 tok/s (prefill / decode), IQ2 in RAM 1,534 / 57.6, IQ2 with Engram on NVMe 1,184 / 54.0. For a task that requires the original quant strictly, IQ2 is a separate mode, not a drop-in.

Kernel specialization for IQ2 on 2 cards lifted short decode from 92.6 to 99.2 tok/s. A new SWA kernel for 32 heads gave nothing on the same task: attention was about 2% of the step. Profile the quant, length and head count of the target config before writing kernels.

A hybrid by memory tier (more precise experts in VRAM, coarser ones in RAM) exists only as a calculation: for DeepSeek the scheme "UD in VRAM, Maya-S in RAM" gives KL ~0.078 at a speed between the 2 quants (calc, not run), and the reverse scheme is worse than both. The Hy4 hybrid above is a different split, by call frequency, and it was run: about 90 tok/s and KL 0.041, between the 2 quants, with speed and quality taken on different inputs.

## Lossless compression of experts (Hy4 Flash, stopped)

Idea: compress experts without loss and decode inside the kernel, to keep more of them resident. It freed about 0.725 GiB on the busiest card, and the 470,016 checked values matched. But on 12 Q3 experts latency grew from 21.71 to 326.25 µs, on Q4 from 23.35 to 192.10 µs.

Revisit if there is another way to decode, or if the residency gain covers the decode cost in a full step.

## The control permutation

On an MoE, moving the same experts between devices changes the summation order and can flip a routing decision. On Hy4 the gap between expert 16 and 17 could be about 0.0003. So "same weights, different placement" already gives top-1 88.3% and KL 0.0054 against the base.

Use this as the ruler for reading KL: a quant change that gives KL 0.005 is inside placement noise, one that gives 0.07 is not. See [15](15-quality-and-release-gates.md).

## Transfer checklist

1. Count experts in VRAM for each candidate quant at your context, KV precision and drafter. Use [01](01-cost-model.md) to turn that into misses.
2. Take KL numbers only on one panel (one reference, the same windows). Do not mix panels or sources.
3. Run a control permutation to get the noise floor of your KL.
4. Read real output in every language you serve. Logit metrics missed garbage.
5. If you swap only the experts, verify the origin of every tensor in the resulting file.
