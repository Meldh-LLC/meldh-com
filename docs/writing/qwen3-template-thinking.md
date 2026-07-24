# Chat template settings determine whether Qwen3's thinking mode survives fine-tuning

Two of our Qwen3-8B fine-tunes, built on different versions of the same corpus, came out with opposite abilities. One kept the model's hybrid thinking mode, where passing `think: true` makes it deliberate in a hidden channel before answering and passing `think: false` makes it answer directly. The other lost thinking entirely. The flag does nothing, and the thinking field comes back empty on every request across every random seed. Training loss looked normal, the voice was intact, and nothing in our evaluations noticed. The builds differed in more than one way, but the cause turned out to be the chat template. A later retrain through the surviving build's template restored the capability, and a recent paper isolated the mechanism.

Anyone fine-tuning Qwen3 with a standard config is using the second build's template by default. This post covers the mechanism and the numbers behind it. On our benchmark, thinking cuts a specific class of fabrication by 11 to 13 points. It ends with a finding that surfaced only after a full retrain. Preserving the capability is not the same as being able to use it.

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

Same base model, same domain. That build's thinking survived as a clean runtime toggle. With `think: true` it produced coherent multi-paragraph deliberation across 96 prompts from our own domain and three random seeds, and with `think: false` thinking was fully suppressed.

The same collapse has been documented independently. "Reasoning-Trace Collapse" ([arXiv 2605.21127](https://arxiv.org/abs/2605.21127)) ran the comparison systematically, using LoRA answer-only supervised fine-tuning on four reasoning models, Qwen3-8B included. For Qwen3-8B the paper measures the share of outputs whose reasoning is structurally valid. Training with empty-think targets drops that share to 58.2% on GSM8K, while omitting the tags entirely holds it at 96.5%. Masking the think region out of the loss does best at 100%, and masking is also the only condition that preserved reasoning on the paper's own training task (82%, against 0% for both alternatives). The paper also explains why the failure goes unnoticed. Models keep producing plausible final answers after the valid reasoning is gone.

So there are three template choices, and they are not interchangeable. Empty-think targets, which the standard qwen3 chat template renders and axolotl therefore produces by default, actively train the capability away. Tag-free targets preserved it fully in our domain, though the paper's own-task result above says that is no guarantee. Loss-masking preserves it best on paper, but axolotl currently has an open bug for Qwen3 in multi-turn data ([#3088](https://github.com/axolotl-ai-cloud/axolotl/issues/3088)) that misplaces think tokens and mask boundaries. A rendered, masked sample needs auditing before that route can be trusted.

## Deliberation measurably reduces fabrication under false premises

We wanted thinking back because of its effect on fabrication. Our model works in a domain where users bring premises that are sometimes false, such as a misremembered study, a quote attributed to the wrong philosopher, or a term that sounds established but is not. We built a 96-item benchmark for this case. It holds 58 trap items that each carry a plausible false premise and 38 real items with true premises across eight categories including invented fallacy names, misattributed positions, and fake etymologies. Every response is judged blind under shuffled keys with every fabrication verdict receiving an adversarial recheck against pre-verified ground truth, and about 10% of first-pass flags were overturned in that recheck. Each condition ran three random seeds, giving 174 trap trials per condition.

On the base model, deliberation helps substantially. Base Qwen3-8B with thinking off fabricates on 54.0% of trap trials (94/174). With thinking on, the rate falls to 40.8% (71/174). It helps on true premises too, where correct answers rise from 35.1% to 41.2% with no over-hedging cost. The thinking traces make the mechanism visible, since the deliberation channel is where the model questions an attribution ("was that actually Epictetus?") before the answer commits.

The protection survives fine-tuning, with caveats. On our thinking-capable build, trap fabrication runs 67.2% without thinking (117/174) and 56.3% with it (98/174). The 11-point cut matches the 13-point cut on base. The same comparison carries a cost, though. On this build, thinking gave up some true-premise accuracy (36.8% down to 30.7% correct), so the protection is specific to the trap case. The build that lost thinking fabricates on 75.9% of trap trials (132/174), with no deliberation available to recover any of it.

Two caveats apply to these numbers. The first is that the benchmark is deliberately trap-enriched, built to measure what happens when a user brings a false premise, so its rates compare conditions rather than estimate prevalence. On natural prompt distributions our fine-tuned builds fabricate in the 4 to 8% range. The second is cost. With thinking on we measured roughly twice the median latency, and thinking is verbose enough that even a 4096-token cap left 1 response in 288 truncated. A 2048 cap had truncated 21 of 288.

Fine-tuning is also where the fabrication risk concentrates. Supervised fine-tuning on a warm, confident domain voice suppressed the base model's natural hedging almost entirely, and a model that never says "I can't verify that" commits to the user's false premise with conviction. That mechanism, and what did and did not fix it, is a separate write-up. What matters here is that thinking was the largest recoverable lever we measured, and the default template deletes it.

## The serving stack applies templates silently too

With all of this in hand, we retrained through the tag-free template and made a thinking check a condition for accepting the run, which it then passed. On simple factual questions, the new build opens a think block, deliberates, closes it, and answers. The capability was preserved and the build moved on to evaluation.

In evaluation, on prompts like the ones our product actually serves, thinking appeared to engage in 0 of 288 trials, and forcing the block open appeared not to help. We nearly published that conclusion. It was wrong, and the error is the same kind as the training-side one. Our harness had asked the server to apply a custom template that opens a think block, and the server never applied it. In the Ollama version we tested, creating a model from a GGUF file (the packaged model-file format) that carries an embedded chat template silently keeps the embedded template and ignores the TEMPLATE line in the Modelfile. Reading the stored template back from the server showed that none of the forced-open blocks had ever reached the model. The 0-of-288 result measured our serving configuration, not our weights.

Served correctly, through requests our own runner rendered, the forced-open block inverted the picture. The retrained build deliberates on 20 of 20 probes drawn from the prompts our product serves, at length and in a genuinely deliberative voice. It closes the block and answers on only 2 of the 20. The explanation is the training template again, from its other side. A template that never renders think tags never renders the closing tag either, so the model learned to deliberate without learning how to stop. The capability and the trigger survived fine-tuning; the close convention did not. That is an engineering problem rather than the dead capability the broken harness had reported. The next fine-tune can teach the closing convention, or the serving side can treat thinking as a two-step call.

The empty block turned out to matter at serving time in a second way. Rendering it when the model is run measurably shifted style on both builds, raising the frequency of a recurring sentence pattern by roughly 30 to 50 percent. On one build, em-dash and vocabulary regressions (23 and 5 instances with the block) fell to 1 and 0 without it. A comparison between models, stacks, or versions has to hold the render constant, because the serving layer is part of the experiment.

## Recommendations

- Before any Qwen3 fine-tune, dump one fully rendered training sample and search it for `<think>`. Know which of the three cases you are in. Empty-think targets carry the collapse risk and are what the standard template produces. Tag-free targets preserved thinking for us, with no guarantee that transfers, and they carry the cost described above, since a model that never sees the closing tag never learns to emit one. Masked targets do best on paper but need auditing against [#3088](https://github.com/axolotl-ai-cloud/axolotl/issues/3088).
- Read the active template back from your serving stack instead of trusting the one you configured. In the Ollama version we tested, `ollama show <model> --template` was the difference between a real experiment and a configuration error mistaken for a result.
- Test thinking survival on the prompts your product actually serves, with a forced-open think block you have confirmed reaches the model, since a pass on simple factual questions says little about them. Require the block to open, fill, and close, and treat open-without-close as its own failure.
- Hold the render constant in every comparison. The empty think block shifts style measurably when the model is run, so an A/B where one side carries the block and the other does not is measuring the render, not the models.
- When you run the model, always pass the think flag explicitly. Ollama's qwen3 handling defaults to thinking on, and an unset flag is a silent behavior change.
- Budget for the costs. For us that meant roughly twice the median latency and a 4096-token cap, and even at 4096 one response in 288 was cut off.
- If deliberation matters to your task, measure it. Ours was worth 11 to 13 points against false premises, and yours may differ.

The benchmark behind these numbers, with its ground truth and scoring pipeline, is the subject of our next post, and the dataset ships with it. This work comes from building an on-device philosophical counsel model; more on that when it is ready.
