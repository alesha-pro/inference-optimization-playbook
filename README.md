# Inference optimization playbook

97 hypotheses about making huge LLMs fast on consumer GPUs, each one with a verdict: worked, failed, or works only under conditions. With the numbers and the reason.

It comes from running DeepSeek V4.1 Flash, Qwen3.8-Flash-Next, GLM-5.3-Flash, MiniMax-M3.1-Flash and Tencent Hy4 Flash on 4x RTX 3090 with experts offloaded to RAM. These models do not fit in 96 GB of VRAM at the quants we wanted. Engines: Strata, Maya forks, an exllamav3 fork, llama.cpp, vLLM, most of them patched by hand.

It is written for 2 readers:

- **People** who tune local inference and want to know what is worth trying before they spend a week on it.
- **Coding agents** that do the tuning for them. The repo is a ready skill: an agent can find the symptom, read the chapter, check whether an idea was already tried and follow the protocol.

The numbers are from one rig. Yours will be different. The mechanisms are the same on any box with GPUs, a CPU and RAM, and chapters 01-15 each end with a checklist for moving the idea to another model.

## Start

| You want to | Open |
|---|---|
| Find your problem by symptom | [playbook/00-start-here.md](playbook/00-start-here.md) |
| Check if an idea was already tried | [ledger/hypotheses.md](ledger/hypotheses.md) |
| Bring up a new model step by step | [protocol/new-model-checklist.md](protocol/new-model-checklist.md) |
| See how it went on a model like yours | [cases/](cases/README.md) |
| Look up a term | [glossary.md](glossary.md) |

## What is inside

```
playbook/    16 chapters by mechanism
  00  start here: symptom table, 15 findings
  01  cost model: time = constant + misses × cost of a miss
  02  where to serve a miss: CPU lane vs PCIe copy
  03  hot experts: profile, domain, placement
  04  live expert cache
  05  several GPUs: layer split, TP, EP, all-reduce
  06  CPU and RAM: channels, NUMA, threads
  07  prefill and re-reading the prompt
  08  speculative decoding
  09  quants: bits vs experts in VRAM
  10  pruning and merging experts
  11  sessions, KV and the prompt cache in agent work
  12  loading, page cache, THP, big tables on NVMe
  13  the output head
  14  how to benchmark, and the traps
  15  quality and release gates
ledger/      every hypothesis with a verdict and a "revisit when"
cases/       the rig and 5 model case files
protocol/    checklist for a new model, template for a new entry
SKILL.md     entry point for agents
AGENTS.md    rules for editing this repo
```

## A few results

- Decode of an offloaded MoE fits `time per token = constant + misses × cost of one miss` on every engine we used. On DeepSeek the fit of a speculative round has R² 0.9997.
- "Keep the hot experts in VRAM" works on 2 of the first 4 models. On MiniMax a profile gives 64-69% hits and random placement gives 61% (sim).
- A miss in decode was usually cheaper to compute on the CPU than to copy over PCIe 3.0. On Hy4 Flash with 2 cards that took decode from 24.6 to 70.4 tok/s on a short 600-token code answer.
- One build flag made the CPU path 3.6x faster on Zen 2 (PDEP runs in microcode there).
- The build that loads experts once per block of up to 57,600 tokens and runs attention in tiles of 2,048 took single-card prefill from ~420 to ~1,420-1,510 tok/s.
- Training a drafter on our own data gave little or nothing on 3 models. A draft vocabulary for the language took acceptance on Russian from 32% to 54% with no training.
- A short benchmark promised +27% decode. Real generation gave +2%.
- A drafter change matched on 4,400 tokens of the first turn and broke the second turn.

## Use it with an agent

The repo root is a skill directory (`SKILL.md` plus plain markdown, without scripts or dependencies).

Clone it where your agent looks for skills, for example:

```bash
git clone https://github.com/alesha-pro/inference-optimization-playbook ~/.claude/skills/inference-optimization-playbook
```

or into `.agents/skills/` or `.claude/skills/` of a project. Then ask the agent things like:

- "Decode on my 2-GPU box is 20 tok/s with most experts in RAM. What do I check first?"
- "I want to add a drafter to this engine. Was a separate wide drafter worth it?"
- "Plan the bring-up of this new MoE on 1x 24 GB + 128 GB RAM."

Without skills support, point the agent at the repo and tell it to read `SKILL.md` first.

## How it is maintained

This is a living notebook. New models and new results are added as dated entries. When a later check changes a decision, the old result stays next to the new one with the date, so the reason stays visible.

Every number says where it came from: a real run, a simulator on real traces (sim), a calculation (calc), a microbenchmark (micro) or someone else's number (ext).

Tested something from here on other hardware and got a different result? Open an issue with the [entry template](protocol/entry-template.md) filled in.

## Related

- [alesha-pro/4x3090-llm-benchmarks](https://github.com/alesha-pro/4x3090-llm-benchmarks): raw speed numbers with exact launch commands.
- [alesha-pro/qwen38-flashnext-strata-4x3090](https://github.com/alesha-pro/qwen38-flashnext-strata-4x3090): the full Qwen3.8-Flash-Next recipe.
- [alesha-pro/exllamav3-glm53-4x3090](https://github.com/alesha-pro/exllamav3-glm53-4x3090): the exllamav3 fork for GLM-5.3-Flash.
- [alesha-pro/project-maya](https://github.com/alesha-pro/project-maya): the Maya fork, with [Hy4 Flash notes](https://github.com/alesha-pro/project-maya/blob/82a77bf/docs/HY4-FLASH.md).

By [@superalesha](https://x.com/superalesha). MIT license.
