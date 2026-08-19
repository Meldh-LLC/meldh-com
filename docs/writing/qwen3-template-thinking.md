---
description: A Qwen3-8B case study on how chat templates can erase thinking during fine-tuning, how deliberation affected false-premise fabrication, and how Ollama serving templates changed the result.
og_type: article
hide:
  - navigation
---

# Chat template settings determine whether Qwen3's thinking mode survives fine-tuning

<p class="article-meta">Published July 24, 2026 · Meldh LLC</p>

!!! abstract "In brief"
    In answer-only Axolotl training, `chat_template: qwen3` rendered empty `<think>` targets that erased thinking in one of our Qwen3-8B fine-tunes. Preserving the capability reduced false-premise fabrication by 11 to 13 points in our benchmark. A serving test on Ollama 0.31.2 also showed that the configured template was not necessarily the template applied to the GGUFs we tested, so both training targets and served requests need to be inspected directly.

Two of our Qwen3-8B fine-tunes, built on different versions of the same corpus, came out with opposite abilities. One kept the model's hybrid thinking mode, where passing `think: true` makes it deliberate in a hidden channel before answering and passing `think: false` makes it answer directly. The other lost thinking entirely. The flag does nothing, and the thinking field comes back empty on every request across every random seed. Training loss looked normal, the voice was intact, and nothing in our evaluations noticed. The builds differed in more than one way, but the cause turned out to be the chat template. A later retrain through the surviving build's template restored the capability, and a recent paper isolated the mechanism.

In Axolotl, answer-only data rendered with `chat_template: qwen3` follows the second build's empty-think pattern by default. This post covers the mechanism and the numbers behind it. On our benchmark, thinking cuts a specific class of fabrication by 11 to 13 points. A full retrain also exposed a serving problem: preserving the capability did not guarantee that the model could use it.

## Results at a glance

| Model condition | Thinking mode | Trap fabrication |
|---|---:|---:|
| Base Qwen3-8B | Off | 54.0% (94/174) |
| Base Qwen3-8B | On | 40.8% (71/174) |
| Thinking-capable fine-tune | Off | 67.2% (117/174) |
| Thinking-capable fine-tune | On | 56.3% (98/174) |
| Thinking-lost fine-tune | Unavailable | 75.9% (132/174) |

## Empty think blocks teach the model not to think

Qwen3's hybrid behavior comes from its post-training. The technical report ([arXiv 2505.09388](https://arxiv.org/abs/2505.09388)) describes a stage called Thinking Mode Fusion that folds non-thinking responses into a thinking model, and the official chat template renders every non-thinking assistant turn with a literal empty think block:

```
<think>

</think>

Answer text...
```

When the model is run, that empty block is how thinking gets switched off, and it's what the model expects to see. In training targets, the same tokens become a lesson. With `chat_template: qwen3` set in axolotl and answer-only training data, every rendered target asserts that the correct content of the think block is nothing. A few thousand conversations later the model has internalized the pattern. Asked to think, it emits an empty block or opens one it never uses. The capability is gone, and the training metrics give no sign of it.

Our second build went through that template and lost thinking completely. Our earlier build had gone through a 202-byte ChatML template that never renders think tags at all:

```jinja
{% for message in messages %}{{ '<|im_start|>' + message['role'] + '\n' + message['content'] + '<|im_end|>' + '\n' }}{% endfor %}{% if add_generation_prompt %}{{ '<|im_start|>assistant\n' }}{% endif %}
```

Both builds used the same base model and domain. The earlier build's thinking survived as a clean runtime toggle. With `think: true` it produced coherent multi-paragraph deliberation across 96 prompts from our own domain and three random seeds, and with `think: false` thinking was fully suppressed.

The same collapse has been documented independently. "Reasoning-Trace Collapse" ([arXiv 2605.21127](https://arxiv.org/abs/2605.21127)) ran the comparison systematically, using LoRA answer-only supervised fine-tuning on four reasoning models, Qwen3-8B included. For Qwen3-8B the paper measures the share of outputs whose reasoning is structurally valid. Training with empty-think targets drops that share to 58.2% on GSM8K, while omitting the tags entirely holds it at 96.5%. Masking the think region out of the loss does best at 100%, and masking is also the only condition that preserved reasoning on the paper's own training task (82%, against 0% for both alternatives). The paper also explains why the failure goes unnoticed. Models keep producing plausible final answers after the valid reasoning is gone.

The three template choices have different effects. Empty-think targets, which the standard qwen3 chat template renders and axolotl therefore produces by default, actively train the capability away. Tag-free targets preserved it fully in our domain, though the paper's own-task result above says that is no guarantee. Loss-masking preserves it best on paper, but axolotl currently has an open bug for Qwen3 in multi-turn data ([#3088](https://github.com/axolotl-ai-cloud/axolotl/issues/3088)) that misplaces think tokens and mask boundaries. A rendered, masked sample needs auditing before that route can be trusted.

## Deliberation measurably reduces fabrication under false premises

We wanted thinking back because of its effect on fabrication. Our model works in a domain where users bring premises that are sometimes false, such as a misremembered study, a quote attributed to the wrong philosopher, or a term that sounds established but is not. We built a 96-item benchmark for this case. It holds 58 trap items that each carry a plausible false premise and 38 real items with true premises across eight categories including invented fallacy names, misattributed positions, and fake etymologies. Every response is judged blind under shuffled keys with every fabrication verdict receiving an adversarial recheck against a pre-verified answer key, and about 10% of first-pass flags were overturned in that recheck. Each condition ran three random seeds, giving 174 trap trials per condition.

On the base model, deliberation helps substantially. Base Qwen3-8B with thinking off fabricates on 54.0% of trap trials (94/174). With thinking on, the rate falls to 40.8% (71/174). It helps on true premises too, where correct answers rise from 35.1% to 41.2% with no over-hedging cost. The thinking traces make the mechanism visible, since the deliberation channel is where the model questions an attribution ("was that actually Epictetus?") before the answer commits.

The protection survives fine-tuning, with caveats. On our thinking-capable build, trap fabrication runs 67.2% without thinking (117/174) and 56.3% with it (98/174). The 11-point cut matches the 13-point cut on base. On this build, however, thinking reduced true-premise accuracy from 36.8% to 30.7%, so the protection is specific to the trap case. The build that lost thinking fabricates on 75.9% of trap trials (132/174), with no deliberation available to recover any of it.

Two caveats apply to these numbers. The first is that the benchmark is deliberately trap-enriched, built to measure what happens when a user brings a false premise, so its rates compare conditions rather than estimate prevalence. On natural prompt distributions our fine-tuned builds fabricate in the 4 to 8% range. The second is cost. With thinking on we measured roughly twice the median latency, and thinking is verbose enough that even a 4096-token cap left 1 response in 288 truncated. A 2048 cap had truncated 21 of 288.

Fine-tuning is also where the fabrication risk concentrates. Supervised fine-tuning on a warm, confident domain voice suppressed the base model's natural hedging almost entirely, and a model that never says "I can't verify that" commits to the user's false premise with conviction. That mechanism, and what did and did not fix it, is a separate write-up. What matters here is that thinking was the largest recoverable lever we measured, and the default template deletes it.

## The serving stack applies templates silently too

We then retrained through the tag-free template and made a thinking check a condition for accepting the run, which it passed. On simple factual questions, the new build opens a think block, deliberates, closes it, and answers. The capability was preserved and the build moved on to evaluation.

In evaluation, on prompts like the ones our product actually serves, thinking appeared to engage in 0 of 288 trials, and forcing the block open appeared not to help. We nearly published that conclusion. It was wrong, and the error is the same kind as the training-side one. Our harness had asked the server to apply a custom template that opens a think block, and the server never applied it. In Ollama 0.31.2, creating a model from the template-bearing GGUFs we tested silently served the embedded template over the `TEMPLATE` line in the Modelfile. Reading the stored template back from the server showed that none of the forced-open blocks had ever reached the model. The 0-of-288 result measured our serving configuration, not our weights.

This precedence is deliberate. Since Ollama 0.30.0, the server hands prompt rendering to llama.cpp's built-in template engine, and when a model carries both an embedded template and a Modelfile `TEMPLATE`, it serves whichever declares more capabilities. The embedded template usually wins, because it advertises support for thinking, tools, and vision that a hand-written template leaves out. In our case the Modelfile `TEMPLATE` was stored but lost that comparison, so the embedded template was served. Setting `OLLAMA_GO_TEMPLATE=1` in the server's environment forces the Modelfile template instead, for every model on that server. We confirmed this in Ollama's source rather than by re-running the evaluation.

Served correctly, through requests our own runner rendered, the forced-open block inverted the picture. The retrained build deliberates on 20 of 20 probes drawn from the prompts our product serves, at length and in a genuinely deliberative voice. It closes the block and answers on only 2 of the 20. The training template explains this result as well. A template that never renders think tags never renders the closing tag either, so the model learned to deliberate without learning how to stop. The capability and the trigger survived fine-tuning; the close convention did not. The remaining failure is an engineering problem. The next fine-tune can teach the closing convention, or the serving side can treat thinking as a two-step call.

The empty block turned out to matter at serving time in a second way. Rendering it when the model is run measurably shifted style on both builds, raising the frequency of a recurring sentence pattern by roughly 30 to 50 percent. On one build, em-dash and vocabulary regressions (23 and 5 instances with the block) fell to 1 and 0 without it. A comparison between models, stacks, or versions has to hold the render constant, because the serving layer is part of the experiment.

## Recommendations

- Before any Qwen3 fine-tune, dump one fully rendered training sample and search it for `<think>`. Know which of the three cases you are in. Empty-think targets carry the collapse risk and are what the standard template produces. Tag-free targets preserved thinking for us, with no guarantee that transfers, and they carry the cost described above, since a model that never sees the closing tag never learns to emit one. Masked targets do best on paper but need auditing against [#3088](https://github.com/axolotl-ai-cloud/axolotl/issues/3088).
- Read the active template back from your serving stack instead of trusting the one you configured. With Ollama 0.31.2 and the template-bearing GGUFs we tested, `ollama show <model> --template` was the difference between a real experiment and a configuration error mistaken for a result.
- Test thinking survival on the prompts your product actually serves, with a forced-open think block you have confirmed reaches the model, since a pass on simple factual questions says little about them. Require the block to open, fill, and close, and treat open-without-close as its own failure.
- Hold the render constant in every comparison. The empty think block shifts style measurably when the model is run, so an A/B where one side carries the block and the other does not is measuring the render, not the models.
- When you run the model, always pass the think flag explicitly. Ollama's qwen3 handling defaults to thinking on, and an unset flag is a silent behavior change.
- Budget for the costs. For us that meant roughly twice the median latency and a 4096-token cap, and even at 4096 one response in 288 was cut off.
- If deliberation matters to your task, measure it. Ours was worth 11 to 13 points against false premises, and yours may differ.

The benchmark behind these numbers and its scoring pipeline will be the subject of our next post. The dataset will ship with it. We found these failures while building an on-device model for philosophical counsel; more on that when it is ready.
