---
name: inference-optimization-playbook
description: Use when the task is to make local LLM inference faster or to explain why it is slow, especially large MoE models that do not fit in VRAM: expert offload to RAM, hot expert placement, live expert cache, CPU lane vs PCIe copy, multi-GPU (layer split, tensor parallel, expert parallel, all-reduce), prefill and re-read speed, speculative decoding and drafters, quant choice for speed, expert pruning, KV, prompt cache and session snapshots for agents, big n-gram tables on NVMe, output head cost, benchmark methodology and quality gates for engine changes. Also for porting a new model into an inference engine or planning its bring-up on given hardware. 97 tested hypotheses with verdicts and numbers from DeepSeek V4.1 Flash, Qwen3.8-Flash-Next, GLM-5.3-Flash, MiniMax-M3.1-Flash and Hy4 Flash on 4x RTX 3090. Not for training, prompt engineering or cloud API cost questions.
---

# Inference optimization playbook

A record of real experiments on speeding up LLM inference on consumer GPUs: what was tried, what the numbers were, what the decision was and why. Plain markdown without scripts. All paths below are relative to the directory this file is in.

Use it to avoid repeating experiments that already have an answer, to pick the cheapest next test, and to get ideas when you are stuck.

## How to work with it

1. **Name the symptom, then read one chapter.** Open `playbook/00-start-here.md`, find the row that matches what the user sees, and read the chapter it points to. Do not load every chapter: they are 3-12 KB each.
2. **Before you propose or build an idea, look it up in the ledger.** `ledger/hypotheses.md` has every hypothesis with a verdict (✅ ❌ ◐ ○), the numbers, the reason and a "revisit when". Grep it by keyword:
   ```bash
   grep -n -i "prefetch\|pinning\|NUMA" ledger/hypotheses.md
   grep -n "❌" ledger/hypotheses.md        # everything that failed
   grep -n "| HY\|HY:" ledger/hypotheses.md  # one model
   ```
3. **For a new model, follow the protocol.** `protocol/new-model-checklist.md`, Part A (set up the experiment) then Part B (order of technical steps). The table "The cheapest first tests" at its end tells you what to run in an hour before you write engine code.
4. **Find the closest case.** `cases/README.md` has the rig, the model shapes and a table "Which case is closest to your model". Each case file lists what worked and what did not for that model.
5. **When you finish an experiment, write it down** with `protocol/entry-template.md`. If you are working inside this repo, follow `AGENTS.md`.

## Routing table

| The user's problem | Read |
|---|---|
| Will offload be fast at all, how many experts fit, where does token time go | `playbook/01-cost-model.md` |
| Misses in decode: CPU or PCIe, memory tiers | `playbook/02-serving-a-miss.md` |
| Which experts to keep in VRAM, profiles, domains | `playbook/03-expert-profile-and-placement.md` |
| Cache policy, capacity, warming, predicting experts | `playbook/04-live-expert-cache.md` |
| 2-4 GPUs: layer split vs TP vs EP, exchange between cards, padding | `playbook/05-multi-gpu.md` |
| RAM channels, NUMA, thread count, pinning | `playbook/06-cpu-and-ram.md` |
| Slow prompt reading, chunk size, DMA, CUDA graphs | `playbook/07-prefill.md` |
| Drafters, MTP, acceptance, window policy, drafter training | `playbook/08-speculative-decoding.md` |
| Which quant, hybrids, KL noise floor | `playbook/09-quants.md` |
| Dropping, masking or merging experts | `playbook/10-pruning-and-merging.md` |
| Agent turns are slow, prompt cache misses, A → B → A | `playbook/11-sessions-and-prompt-cache.md` |
| Load time, THP stalls, a table too big for RAM | `playbook/12-loading-and-big-tables.md` |
| Vocabulary projection cost | `playbook/13-output-head.md` |
| Building a reference, replay, why a benchmark lied | `playbook/14-benchmarking-and-traps.md` |
| Did the change keep quality, should this build ship | `playbook/15-quality-and-release-gates.md` |
| A term is unclear | `glossary.md` |

## Rules for using these numbers

- **Transfer mechanisms, not numbers.** Everything was taken on 4x RTX 3090 (PCIe 3.0, no NVLink), an EPYC 7642 and DDR4 whose channel count changed during the work. Before you quote a number to the user, say which model, engine and hardware it is from. Never present it as what they will get.
- **A ❌ is local.** It means "did not pay on that model, engine and hardware". Read the "why" and "revisit when" columns. Several ideas flipped between models: the CPU lane lost to PCIe on GLM and won on 3 other models, TP under offload was dropped on DeepSeek and worked on Hy4 Flash with a CPU lane serving the missing experts.
- **Respect the evidence labels.** No label means a real run. (sim) is a simulator on real traces, (calc) a calculation, (micro) a microbenchmark of one operation, (ext) someone else's number, (1 run) not repeated. Do not turn a (calc) into a promise.
- **Reproduce the bottleneck first.** Each chapter says what to record on the user's setup to know whether the trick applies. Do that before you implement anything.
- **Prefer the cheapest test.** Several decisions here were made on a trace plus a simulator, or on a fit, before engine work started (for example the branch tree for drafters on Hy4 Flash).
- **Do not skip the quality gate.** Any change in chunk size, quant, placement, exchange packing or drafter acceptance is a numeric change until shown otherwise. Use the 3 levels in chapter 15 and always test a second turn.
- **Short benchmarks are for debugging.** Decide on a replay of real sessions and free generation, with the threshold written down before the run.

## The model in one paragraph

Decode of an offloaded MoE costs `constant + misses per token × cost of one miss`. So there are 4 levers: fewer misses at the same VRAM (profile, live cache), more experts in VRAM (fewer bits, smaller buffers), a cheaper miss (CPU lane, faster RAM, better CPU code), and a smaller constant (kernels, exchange, drafter). Fit the model first and work on the larger term. Prefill is a different regime: almost every expert is needed per chunk, so the lever is bytes moved over PCIe per token. Agent workloads are a third regime: most time is generation and short re-reads, so caches and snapshots matter more than cold prefill speed.

## When the playbook has no answer

Say so. Then use the closest mechanism to design the cheapest test that would answer it, run it if you can, and record the result with the entry template. A new row in the ledger with a clear verdict is the most useful contribution.
