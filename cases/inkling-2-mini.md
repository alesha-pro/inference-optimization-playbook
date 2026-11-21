# Inkling 2 Mini

Measured on November 21, 2026 with Maya, Unsloth UD-Q4_K_XL, one RTX 3090 at 300 W and 8-channel DDR4-2133. The GPU uses PCIe 3.0 x16. The 24 physical MoE layers hold 128 experts each and select 8 per token. The middle 12 layers execute 3 times, giving 48 visits per token. The vocabulary has 200,058 entries. Eight global attention visits retain every input position, the other 40 use the model's sliding window. The resident vision encoder shares the same GPU.

Tags: `#decode #kernel #kv #long-context #drafter`

| Experiment | Result |
|---|---|
| Delay physical commitment of global KV | All 3,072 experts fit at short depth with a 1,048,576-token limit. Eager allocation at the same limit left 285 slots. [Placement](../playbook/03-expert-profile-and-placement.md) |
| Two signed-byte activation limbs for NVFP4 | Short greedy decode reached 120.29 tok/s. Mean KL at fixed FP16 KV was 0.00003746 over 199 positions. With FP8 KV the two-limb profile solved 71/96 paired GSM8K questions, versus 73/96 with scalar experts. [Quants](../playbook/09-quants.md) |
| Selected CPU layers at deep context | At 1,048,064 synthetic KV positions, GPU staging 10.55 tok/s, exact arithmetic on 24 EPYC threads for selected layers 18.13. [CPU placement](../playbook/06-cpu-and-ram.md) |
| Signed-half lookup with the scalar reduction | 112.62-112.83 to 116.33-116.60 tok/s in paired short Python continuations. [Quantized products](../playbook/09-quants.md) |
| Copy proposals checked by the target | 488.9 tok/s on a 509-token Python edit, 113.4 on fresh prose and 113.6 on fresh code. [Speculation](../playbook/08-speculative-decoding.md) |

The scalar-expert serving profile retained all 200,058 logits byte for byte across 795 forced positions on five histories. On the 96-question arithmetic panel the old and new services agreed on which questions they solved. Three generated explanations changed wording. All three invoked batched suffix verification.

## The resident engine (maya-ik2 r5, same day)

| Experiment | Result |
|---|---|
| Every expert in VRAM, a token as one CUDA graph, 1,404 → 781 launches | 57 (llama.cpp) → 112 tok/s. [Placement](../playbook/03-expert-profile-and-placement.md) |
| Token attention on tensor cores from the cache | 65K deep 53 → 84 tok/s with FP8 KV |
| NVFP4 experts on tensor cores, 2 FP16 limbs | 121.2 → 127.2 tok/s, GSM8K 74/96. [Quants](../playbook/09-quants.md) |
| Attention residuals grouped, loop messages batched | +2.5% and +0.8%, bit-exact |
| Image encoder on the CPU | 344K context with images |
| Prefill: FP8 flash tiles, cuBLAS loop gates, short prompts by groups | 2,742 tok/s at 4K, 12-token turn 56 ms. [Prefill](../playbook/07-prefill.md) |
| DSpark windows 4-8 | acceptance and window cost in [Speculation](../playbook/08-speculative-decoding.md); not shipped yet |

Final, one RTX 3090, FP8 KV, 344K window: decode 128.7 / 124.2 / 105.6 / 90.6 / 62.3 tok/s after 47 / 4K / 64K / 128K / 340K tokens, prefill 2,742 / 2,361 / 2,079 / 1,473. Engine: github.com/alesha-pro/maya-inkling-mini.
