---
description: A Qwen3-8B case study on chat templates, thinking after fine-tuning, false-premise fabrication, and the difference between configured and served templates.
og_type: article
hide:
  - navigation
---

# How chat templates can affect Qwen3 thinking after fine-tuning

<p class="article-meta">Published July 24, 2026 · Corrected November 17, 2026 · Meldh LLC</p>

!!! abstract "In brief"
    One of our Qwen3-8B fine-tunes stopped returning usable thinking in ordinary chat. Empty `<think>` blocks in the training targets were a possible explanation. In two benchmark comparisons, the configurations with thinking enabled received fewer fabrication ratings on questions with false premises. Other settings changed with thinking mode. A later test on Ollama 0.31.2 showed how a serving template could invalidate a test of the model itself.

Two of our Qwen3-8B fine-tunes behaved differently when we asked for a separate thinking trace before the answer. In ordinary chat, one returned a trace with `think: true` and a direct answer with `think: false`. The other returned no usable trace in those checks. In a separate diagnostic, forcing its thinking block open produced answer-like prose in the thinking field and no separate answer. Training loss looked normal and the voice was intact, so our initial evaluations missed the problem.

The builds differed in more than one way, but the evidence implicated the chat template. A later retrain through the earlier build's tag-free template produced thinking again. That retrain also changed other training conditions, so it did not isolate the template's effect. A controlled study independently demonstrated how empty-think training targets can suppress explicit reasoning traces. Our subsequent serving investigation showed why preserving thinking in a training run was only part of the task.

## Results at a glance

| Model condition | Thinking mode | Answers rated as fabrications |
|---|---:|---:|
| Base Qwen3-8B | Off | 54.0% (94/174) |
| Base Qwen3-8B | On | 40.8% (71/174) |
| Thinking-capable fine-tune | Off | 67.2% (117/174) |
| Thinking-capable fine-tune | On | 56.3% (98/174) |
| Thinking-lost fine-tune | Unavailable | 75.9% (132/174) |

Each row covers the same 58 requests with false premises, run at three random seeds. An answer could challenge the premise and still earn a fabrication rating by inventing a different fact.

## Empty think blocks can suppress explicit thinking

The Qwen team calls the stage in which it taught its larger models to operate with or without a thinking trace *Thinking Mode Fusion*. Qwen3-8B learned the two modes through distillation from those teachers. In the shared format, an answer in non-thinking mode begins with an empty think block. [Qwen3 Technical Report, §§4.3 and 4.5](https://arxiv.org/html/2505.09388v1#S4.SS5)

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

Both builds used the same base model and domain. On the earlier build, all 288 trials with `think: true` returned a nonempty, multi-paragraph trace across 96 requests and three random seeds. Switching thinking off suppressed the trace. Those observations tell us when this build produced visible deliberation. Whether its reasoning was sound requires reading the answers.

The independent study, [“Reasoning-Trace Collapse,” v1](https://arxiv.org/html/2605.21127v1), compared answer-only LoRA fine-tuning formats on four reasoning models, including Qwen3-8B. Its Table 2 reports the share of outputs with structurally valid traces at the end of training. For Qwen3-8B on GSM8K, empty-think targets yielded 58.2%, tag-free targets 96.5%, and masking the think region out of the training loss 100%. On the Chemistry task used for training, the corresponding figures were 0%, 0%, and 82%. These are three of the study's conditions, and the measure concerns complete, nonempty, separable traces, not whether the reasoning is correct or faithful. Plausible final answers can survive even when valid traces do not.

The three choices therefore carry different evidence. Empty-think targets can suppress explicit thinking. Tag-free targets preserved it in our earlier domain tests, but the paper's Chemistry result shows that this does not always transfer. Masking, which excludes the relevant tokens from the training loss, had the highest structural validity among these three conditions in the cited comparison. Implementation still needs checking: an open [Axolotl issue, #3088](https://github.com/axolotl-ai-cloud/axolotl/issues/3088), reports misplaced think tokens and mask boundaries in a multi-turn Qwen3 configuration. It is a reason to inspect actual samples and masks, not a finding about every masking route.

## How we tested answers to false premises

A person who misremembers a quotation may be asking a perfectly reasonable question about its meaning. A model can answer fluently while inventing a source for it. To test that problem, we built a benchmark of 96 requests across eight categories. Fifty-eight contained plausible false premises, including invented fallacy names, misattributed positions, and fake etymologies. The remaining 38 had true premises. Without those 38, a model that doubted every attribution could look better simply by never committing to an answer.

We checked the answer key before scoring. Language-model judges saw responses under shuffled identifiers that concealed which configuration produced them. A second review challenged fabrication and factual-error ratings against the key. In the original three-condition comparison, 308 of 864 trials initially received a fabrication label and 176 a factual-error label. The recheck cleared 17 of those 484 flags (3.5%). Revisiting the explanation for a flag could leave the error rating in place. A separate check identified two previously unflagged errors. These rates depend in part on the judgments made under that procedure.

## Fewer answers received a fabrication rating with thinking enabled

On the base model, the rate fell from 54.0% (94/174) with thinking off to 40.8% (71/174) with it on. Looking at the same request and seed under both settings, 47 answers lost the fabrication label and 24 acquired it. On the 114 true-premise trials, accuracy rose from 35.1% to 41.2%, while over-hedging changed from 10.5% to 11.4%. Some traces showed the model questioning an attribution before it answered.

On the earlier thinking-capable fine-tune, the fabrication rate fell from 67.2% (117/174) to 56.3% (98/174). True-premise accuracy went the other way, from 36.8% to 30.7%. Enabling thinking changed the rendered request and, on this fine-tune, allowed a larger output budget. The 11- and 13-point differences describe the configurations we tested. Estimating the contribution of deliberation alone would require controlling for those other changes. The build without usable thinking received a fabrication rating on 75.9% of trap trials (132/174).

The benchmark is deliberately trap-enriched. Its rates compare responses to false premises and do not estimate how often fabrication occurs in ordinary use. In our separate natural-prompt evaluation sets, fine-tuned builds had measured rates in the 4 to 8% range. Those sets also do not establish deployment prevalence.

Median latency with thinking enabled was roughly twice as long on the base model and 1.8 times as long on the earlier fine-tune. The historical screens flagged 21 of 288 base responses and one of 288 fine-tune responses as possibly cut short. The fine-tune screen checked terminal punctuation. Applying that rule to the base texts reproduced only 17 of its 21 flags. The saved generations lack the server's stop reason, so we cannot say how many hit the token limit.

The thinking-lost build also showed a sharp change in uncertainty expression. Over-hedging on true-premise items fell from 10.5% on base to 0.9%, alongside higher false-premise fabrication. We suspected that training for a warm, confident domain voice had weakened uncertainty expression, but the builds differed in several ways and did not isolate voice as the cause. That question belongs in a separate write-up.

## The serving stack applies templates silently too

We later retrained through the tag-free template and made a thinking check a condition for accepting the run. This later build did not appear in the fabrication table. On simple factual questions, it opened a think block, deliberated, closed it, and answered. It passed that check and moved on to evaluation.

On requests like the ones our product serves, thinking appeared to engage in 0 of 288 trials. Our harness had asked Ollama to apply a custom template that opened a think block. On the template-bearing GGUF files we tested, Ollama 0.31.2 selected the embedded template over the one in our Modelfile. Inspecting the template returned by the show API exposed the mismatch. The 288 trials never tested the forced-open condition we intended.

In the version we examined, Ollama compared the capabilities declared by the embedded template and the Modelfile's Go template. On the path that chooses between them, the server setting `OLLAMA_GO_TEMPLATE=1` selects an available Go template. A configured renderer can take precedence. We verified the override in source. We did not repeat the evaluation with the override enabled. [Template selection in 0.31.2](https://github.com/ollama/ollama/blob/v0.31.2/server/images.go) · [Renderer precedence](https://github.com/ollama/ollama/blob/v0.31.2/server/prompt.go#L135-L152)

With requests rendered by our own runner, the forced-open test produced nonempty deliberation on all 20 probes drawn from the kinds of prompts our product serves. Only 2 of the 20 closed the block and supplied an answer. The tag-free training supplied no examples of the closing convention, which may have contributed to unreliable completion. It does not establish that the model had never learned to close: the same build closed on factual questions and on two of these probes. Training with explicit closing examples or using a two-step serving call are possible approaches to test. Neither was established as a remedy by this result.

Rendering also affected style on the fine-tune that lost usable thinking and on the later retrain. We compared 200 responses with the empty block against 200 without it on each build. With the block, a recurring sentence pattern appeared about 30 to 50 percent more often per response across the two comparisons. On one build we counted 23 em dashes with the block and one without it. Matches to a predefined vocabulary screen fell from four to zero. These counts measure particular features of the text. They give us a reason to check the rendering before attributing a style difference to a change of model.

## Recommendations

- Before a Qwen3 fine-tune, inspect fully rendered training samples and their loss masks, including multi-turn examples. Empty-think targets carry a collapse risk. Tag-free targets preserved thinking in our earlier tests, but did not ensure reliable completion in the later build. Masked targets had the best structural validity among the three cited paper conditions and need implementation checks, including the case reported in [#3088](https://github.com/axolotl-ai-cloud/axolotl/issues/3088).
- Inspect the template the server reports, then verify the request the model receives. In Ollama 0.31.2, `ollama show <model> --template` prints the template field from the show API we used. That field describes the selected template. Rendering the request ourselves let us check the actual input. [CLI display](https://github.com/ollama/ollama/blob/v0.31.2/cmd/cmd.go#L1243-L1260) · [Show API](https://github.com/ollama/ollama/blob/v0.31.2/server/routes.go#L1616-L1623)
- Test thinking on the prompts the product serves, with a forced-open block confirmed to reach the model. A pass on simple factual questions did not predict reliable completion in our product-prompt probes. Require the block to open, fill, and close, and treat open-without-close as its own failure.
- Hold rendering constant where feasible, or account explicitly for its differences. An A/B where one side carries an empty think block and the other does not cannot separate model differences from rendering effects.
- Pass the think flag explicitly when the serving interface supports it. An unset flag leaves the mode to the model's default, as described in [Ollama's thinking documentation](https://docs.ollama.com/capabilities/thinking).
- Budget for latency and record why generation stopped. A response that ends abruptly warrants a closer look. A recorded stop reason helps determine whether a larger token budget would address it.
- Include true premises when testing a model's response to false ones. Both thinking-enabled configurations received fewer fabrication ratings on the trap items, yet only the base model also answered more true-premise trials correctly.

We found these failures while building an on-device model for philosophical counsel. We will share more about the model when it is ready.

*Correction, November 17, 2026. An earlier version said the recheck overturned about 10% of initial flags. It cleared 17 of 484 (3.5%). We also reported five vocabulary matches with the empty block. The correct count is four. We have clarified which settings changed with thinking mode and how we screened for incomplete answers. We previously said we would release the benchmark dataset with a follow-up post. We have included the scoring method here and will keep the individual benchmark questions and answer key private.*
