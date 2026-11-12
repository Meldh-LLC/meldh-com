---
description: A Qwen3-8B case study on chat templates, thinking after fine-tuning, false-premise fabrication, and the difference between configured and served templates.
og_type: article
hide:
  - navigation
---

# Chat template settings determine whether Qwen3's thinking mode survives fine-tuning

<p class="article-meta">Published July 24, 2026 · Updated November 11, 2026 · Meldh LLC</p>

!!! abstract "In brief"
    One of our Qwen3-8B fine-tunes stopped producing thinking in our tests. The evidence pointed to empty `<think>` targets in answer-only Axolotl training. Turning thinking on reduced false-premise fabrication by 11 to 13 percentage points in comparisons on the base model and an earlier thinking-capable fine-tune. A later serving test on Ollama 0.31.2 showed that the configured template was not necessarily the template applied to the model files we tested. Both training targets and served requests need direct inspection.

Two of our Qwen3-8B fine-tunes, built on different versions of the same corpus, differed in whether they would use the model's hybrid thinking mode. In one, passing `think: true` produced deliberation in a separate channel before the answer, while `think: false` produced a direct answer. In the other, the thinking field remained empty across the requests and random seeds we tested. Training loss looked normal and the voice was intact, so our initial evaluations did not detect the loss.

The builds differed in more than one way, but the evidence implicated the chat template. A later retrain through the earlier build's tag-free template produced thinking again. That retrain also changed other training conditions, so it did not isolate the template's effect. A controlled study independently demonstrated how empty-think training targets can suppress explicit reasoning traces. Our subsequent serving investigation showed why preserving thinking in a training run was only part of the task.

## Results at a glance

| Model condition | Thinking mode | Trap fabrication |
|---|---:|---:|
| Base Qwen3-8B | Off | 54.0% (94/174) |
| Base Qwen3-8B | On | 40.8% (71/174) |
| Thinking-capable fine-tune | Off | 67.2% (117/174) |
| Thinking-capable fine-tune | On | 56.3% (98/174) |
| Thinking-lost fine-tune | Unavailable | 75.9% (132/174) |

## Empty think blocks can suppress explicit thinking

Qwen3's hybrid behavior comes from its post-training. The [Qwen3 technical report](https://arxiv.org/html/2505.09388v1) describes a stage called Thinking Mode Fusion that folds non-thinking responses into a thinking model. Its non-thinking format uses an empty think block before the answer:

```
<think>

</think>

Answer text...
```

When the model is run, this block signals that the answer should proceed without a thinking trace. In training targets, the same tokens reward an empty block. Answer-only data rendered through the Qwen3 template can therefore teach a pattern that conflicts with the intended use of thinking. The exact placement depends on the template and conversation structure. The [official template](https://huggingface.co/Qwen/Qwen3-8B/blob/main/tokenizer_config.json) does not add the block to every historical assistant turn.

The build that stopped producing thinking used `chat_template: qwen3` in Axolotl. Our earlier build had used a 202-byte ChatML template that never renders think tags:

```jinja
{% for message in messages %}{{ '<|im_start|>' + message['role'] + '\n' + message['content'] + '<|im_end|>' + '\n' }}{% endfor %}{% if add_generation_prompt %}{{ '<|im_start|>assistant\n' }}{% endif %}
```

Both builds used the same base model and domain. The earlier build retained thinking as a runtime toggle. With `think: true`, it produced coherent multi-paragraph deliberation across 96 prompts from our domain and three random seeds. With `think: false`, thinking was suppressed. These observations establish behavior in those tests, rather than the presence or absence of every underlying reasoning ability.

The independent study, [“Reasoning-Trace Collapse,” v1](https://arxiv.org/html/2605.21127v1), compared answer-only LoRA fine-tuning formats on four reasoning models, including Qwen3-8B. Its Table 2 reports the share of outputs with structurally valid traces at the end of training. For Qwen3-8B on GSM8K, empty-think targets yielded 58.2%, tag-free targets 96.5%, and masking the think region out of the training loss 100%. On the Chemistry task used for training, the corresponding figures were 0%, 0%, and 82%. These are three of the study's conditions, and the measure concerns complete, nonempty, separable traces, not whether the reasoning is correct or faithful. Plausible final answers can survive even when valid traces do not.

The three choices therefore carry different evidence. Empty-think targets can suppress explicit thinking. Tag-free targets preserved it in our earlier domain tests, but the paper's Chemistry result shows that this does not always transfer. Masking, which excludes the relevant tokens from the training loss, had the highest structural validity among these three conditions in the cited comparison. Implementation still needs checking: an open [Axolotl issue, #3088](https://github.com/axolotl-ai-cloud/axolotl/issues/3088), reports misplaced think tokens and mask boundaries in a multi-turn Qwen3 configuration. It is a reason to inspect actual samples and masks, not a finding about every masking route.

## Deliberation measurably reduces fabrication under false premises

We wanted thinking back because of its effect on fabrication. Our model works in a domain where users bring premises that are sometimes false, such as a misremembered study, a quote attributed to the wrong philosopher, or a term that sounds established but is not. We built a 96-item benchmark for this case: 58 trap items with plausible false premises and 38 items with true premises. It spans eight categories, including invented fallacy names, misattributed positions, and fake etymologies.

Responses were judged blind under shuffled keys. Flagged fabrication and factual-error verdicts received an adversarial recheck against a pre-verified answer key. That recheck overturned about 10% of first-pass flags in the original comparison of the base model and thinking-lost build. We used language-model judging, so these rates also depend on the judging setup. Each condition ran three random seeds, giving 174 trap trials from 58 items and 114 true-premise trials from 38 items.

On the base model, thinking reduced trap fabrication from 54.0% (94/174) to 40.8% (71/174). True-premise accuracy rose from 35.1% to 41.2%, while over-hedging changed from 10.5% to 11.4%. The traces suggested one way thinking could help: the model sometimes questioned an attribution before committing to it in the answer.

On the earlier thinking-capable fine-tune, trap fabrication fell from 67.2% (117/174) to 56.3% (98/174). That 11-point reduction was similar to the 13-point reduction on base. The tradeoff differed, however: true-premise accuracy fell from 36.8% to 30.7%. Thinking helped with false premises in this comparison while making correct answers to true premises less frequent. The build without usable thinking fabricated on 75.9% of trap trials (132/174). Comparisons across builds also involved different training and run settings, so they cannot isolate the effects of any single training choice.

The benchmark is deliberately trap-enriched. Its rates compare responses to false premises and do not estimate how often fabrication occurs in ordinary use. In our separate natural-prompt evaluation sets, fine-tuned builds had measured rates in the 4 to 8% range. Those sets also do not establish deployment prevalence.

Thinking had costs. Median latency was roughly twice as long in the base comparison and 1.8 times as long in the fine-tune comparison. A 4096-token cap still left 1 response in 288 truncated in the fine-tune run. A separate base-model run on a different setup had truncated 21 of 288 at a 2048-token cap. The two runs show the need to check completion, but they do not isolate the effect of changing the cap.

The thinking-lost build also showed a sharp change in uncertainty expression. Over-hedging on true-premise items fell from 10.5% on base to 0.9%, alongside higher false-premise fabrication. We suspected that training for a warm, confident domain voice had weakened uncertainty expression, but the builds differed in several ways and did not isolate voice as the cause. That question belongs in a separate write-up. The result here is narrower: thinking reduced trap fabrication within both models that could use it, making its preservation worth testing directly.

## The serving stack applies templates silently too

We later retrained through the tag-free template and made a thinking check a condition for accepting the run. This was a new build, separate from the earlier fine-tune in the fabrication comparison. On simple factual questions, it opened a think block, deliberated, closed it, and answered. It passed that check and moved on to evaluation.

On prompts like the ones our product serves, thinking then appeared to engage in 0 of 288 trials, and forcing the block open appeared not to help. We nearly published that conclusion. Our harness had asked the server to apply a custom template that opens a think block, but the server never applied it. In Ollama 0.31.2, importing the template-bearing GGUF model files we tested caused the embedded template to be served over the `TEMPLATE` line in the Modelfile. Reading the stored template back exposed the mismatch: our forced-open blocks had not reached the model. The 0-of-288 result did not test the intended forced-open condition.

The precedence was deliberate in the version we examined. Ollama's [0.31.2 template-selection code](https://github.com/ollama/ollama/blob/v0.31.2/server/images.go) considers the capabilities declared by the embedded template and the Modelfile's Go template, along with other conditions. In our case the embedded template took precedence, although the Modelfile template was stored. The [serving code](https://github.com/ollama/ollama/blob/v0.31.2/server/routes.go) also provides a server-side override: `OLLAMA_GO_TEMPLATE=1` selects the Go-template path for models that have a Go template. We confirmed the override in source, without repeating the evaluation under that setting. This describes the version and rendering path examined, rather than a rule for every Ollama model or later release.

With requests rendered by our own runner, the forced-open test produced nonempty deliberation on all 20 probes drawn from the kinds of prompts our product serves. Only 2 of the 20 closed the block and supplied an answer. The tag-free training supplied no examples of the closing convention, which may have contributed to unreliable completion. It does not establish that the model had never learned to close: the same build closed on factual questions and on two of these probes. Training with explicit closing examples or using a two-step serving call are possible approaches to test. Neither was established as a remedy by this result.

The empty block also mattered to style at serving time. In a matched comparison with 200 responses per condition, rendering it increased the count per response of a recurring sentence pattern by roughly 30 to 50 percent across the two builds. Those are relative increases in a measured pattern, not an overall prose-quality score. On one build, em-dash occurrences fell from 23 with the block to 1 without it, and matches to a predefined vocabulary screen fell from 5 to 0. Rendering differences can therefore confound comparisons of models, stacks, or versions.

## Recommendations

- Before a Qwen3 fine-tune, inspect fully rendered training samples and their loss masks, including multi-turn examples. Empty-think targets carry a collapse risk. Tag-free targets preserved thinking in our earlier tests, but did not ensure reliable completion in the later build. Masked targets had the best structural validity among the three cited paper conditions and need implementation checks, including the case reported in [#3088](https://github.com/axolotl-ai-cloud/axolotl/issues/3088).
- Read the active template back from the serving stack and check the rendered request. With Ollama 0.31.2 and the template-bearing GGUFs we tested, `ollama show <model> --template` helped expose the mismatch between the intended and served template.
- Test thinking on the prompts the product serves, with a forced-open block confirmed to reach the model. A pass on simple factual questions did not predict reliable completion in our product-prompt probes. Require the block to open, fill, and close, and treat open-without-close as its own failure.
- Hold rendering constant where feasible, or account explicitly for its differences. An A/B where one side carries an empty think block and the other does not cannot separate model differences from rendering effects.
- Pass the think flag explicitly when the serving interface supports it. An unset flag leaves the mode to the model's default, as described in [Ollama's thinking documentation](https://docs.ollama.com/capabilities/thinking).
- Budget for latency and completion. For us, thinking meant roughly twice the median latency, and even a 4096-token cap left one response in 288 truncated in the fine-tune run.
- Measure the effect on the task, including its tradeoffs. Thinking reduced trap fabrication by 11 to 13 percentage points in our comparisons, but true-premise accuracy moved in opposite directions on the base model and the thinking-capable fine-tune.

The benchmark behind these numbers and its scoring pipeline will be the subject of our next post. The dataset will ship with it. We found these failures while building an on-device model for philosophical counsel. We will share more about the model when it is ready.
