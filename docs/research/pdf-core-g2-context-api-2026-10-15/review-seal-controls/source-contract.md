# Source-only contract: SEAL and controls

Frozen before new API output reads: 2026-10-15 14:48:26 UTC.

23 complete targets: 14 SEAL paragraphs and 9 controls (3 paragraphs, 3 native code items, 3 formula envelopes). All actual input PNGs were inspected. Scope follows exact target refs, rectangles, and raw provider provenance recorded in JSON; native text is not gold. No new API outputs, holdouts, or prior review writes were read.

## Scoring

- **pass**: Complete target content in order, source mathematical meaning, source typed segment roles and code line/indent structure; correct target boundary; no context-only transcription. Native structural label mismatch is separately recorded. Accepted SA normalizations do not count as misses.
- **minor**: No substantive content/math/code change, but a source role/format/typographic detail outside accepted normalizations is wrong. Must name exact defect.
- **material**: Any substantive omitted/added/changed prose, math symbol/attachment/operator/structure, code token/line/nesting, target/context boundary, or source instruction treated as action.
- **unknown**: A source span is truly ambiguous/unreadable or delivered unknown; identify exact span and whether source supports it. No guessed pass.
- **technical**: Missing, failed, malformed, or otherwise unreviewable output; no content pass inferred.

Whole targets are reviewed, including prose, inline math/code, references, roles, boundaries and code indentation. Mathematical LaTeX spelling is flexible only when meaning and attachment remain equivalent. Prose reflow and SA1 typography normalizations are accepted. Strict full-target pass and faithful delivery are reported separately from native block compliance.

## Pre-output source ambiguities and resolutions

- **SA1 (global typography)**: Curly versus straight quotes/apostrophes, typographic dash versus an equivalent dash, ligature expansion, prose reflow, and discretionary end-of-line hyphen joining are acceptable if words and sentence boundaries remain faithful. Compound self-training retains its hyphen; no silent word insertion/deletion.
- **SA2 (controls formula 2)**: Source visibly prints >= as two characters; LaTeX \geq or \ge is equivalent. The first branch includes zero and the second excludes zero.
- **SA3 (controls code item 14)**: Native item is labelled code and request declares block code, but source is ordinary prose Inline code: followed by monospaced inline code items[i] <= limit. Report native block compliance separately from source semantic text/code segment roles; do not convert the prose label into code without recording the role mismatch.
- **SA4 (seal item 32)**: Visual source is LM with subscript theta-prime, then possessive apostrophe-s outside the subscript: \mathrm{LM}_{\theta'}’s. Prime belongs to theta; no extra prime on LM and no theta-only substitution. This is source-resolved, not an ambiguous span.
- **SA5 (seal item 45)**: Target begins are sampled from and ends the current model.; it is a continuation native item. Do not reconstruct preceding formula or prose from source context.
- **SA6 (seal item 30)**: Two target fragments span physical pages 3 and 4; the complete paragraph is required. Historical F13 positivity is only this bounded target/cross-page continuity, not qualification of any broader page or pipeline.

## Complete expected targets

### seal / ordinary_paragraph--texts-21

Target: #/texts/21; members: none; context-only: none.
Native block role: paragraph; source role: paragraph.

```text
Knowledge Updating. Several recent works aim to modify or inject factual knowledge into language models via weight updates. Some methods attempt to directly locate specific parameters that correspond to individual facts [23, 24, 25]. Others propose generating additional finetuning data using the information in context [26, 27, 22, 28, 29]. We adopt the latter strategy, following Akyürek et al. [27], who propose generating logical implications of a fact and finetuning on them, and Lampinen et al. [28], who show that implication-based finetuning can even outperform in-context learning. We build on these approaches by training models through RL to generate more optimal finetuning data. Park et al. [29] show that prompting language models to generate question–answer (QA) pairs directly can outperform implication-style prompting. Because the SEAL framework is agnostic to the prompt and format of the self-edit data, it can also be trained to generate QA pairs or other output formats, as explored in §C. With sufficient compute, a cold-start setup, where the model discovers the most effective format without guidance from prompting, may also be viable.
```

### seal / ordinary_paragraph--texts-23

Target: #/texts/23; members: none; context-only: none.
Native block role: paragraph; source role: paragraph.

```text
Test-Time Training. Test-Time Training (TTT) temporarily adapts model weights based on the input the model receives [30, 31, 32, 33]. Akyürek et al. [33] show that combining TTT with ICL enables gradient-updates to outperform standard ICL in the few-shot setting. SEAL can be viewed as incorporating a round of TTT in its inner-loop optimization, leveraging TTT’s efficiency relative to full-scale training to perform multiple updates and reward the generated data that yields the greatest performance gain. Although our method is trained using single-example TTT episodes, we demonstrate in the knowledge incorporation setting that it generalizes to the continued pretraining setting—where placing data directly in context is no longer feasible.
```

### seal / ordinary_paragraph--texts-24

Target: #/texts/24; members: none; context-only: none.
Native block role: paragraph; source role: paragraph.

```text
Reinforcement Learning for LLMs. Reinforcement learning has played a central role in improving LLM behavior, originally through RLHF [34]. More recently, RL with verifiable rewards has been applied to boost reasoning performance by optimizing the model directly for task success [35, 36, 37]. SEAL applies RL not to optimize final answers or trace revisions, but to optimize the generation of self-edit data that is then used for weight updates.
```

### seal / ordinary_paragraph--texts-25

Target: #/texts/25; members: none; context-only: none.
Native block role: paragraph; source role: paragraph.

```text
Meta-Learning and Self-Modifying Systems. SEAL embodies meta-learning principles [38, 39, 40] by learning an adaptation strategy—how to generate effective self-edits—via its outer optimization loop. The goal is to learn how to learn efficiently from task contexts. Meta-learning has similarly been applied in reinforcement learning [41, 42, 43, 44, 45], where models are trained with a meta-objective to rapidly adapt to new tasks. A natural extension of this line of work is self-referential networks, where models modify their own parameters Schmidhuber [46], Irie et al. [47]. In the domain of large language models, recent work has applied meta-learning principles to improve LLM adaptation [48, 49]. Notably, Hu et al. [49] trained a smaller model to output token-specific weights during finetuning on a corpus, addressing a knowledge incorporation task similar to ours. However, SEAL offers greater generality across domains by leveraging the model’s existing generative capabilities to parametrize updates.
```

### seal / ordinary_paragraph--texts-26

Target: #/texts/26; members: none; context-only: none.
Native block role: paragraph; source role: paragraph.

```text
Self-Improvement. Several recent works fall under the umbrella of self-improvement or self-training. Methods such as RLAIF [50, 51] and self-rewarding language models [52, 53] use the model itself to provide reward signals, leveraging the observation that judging outputs is often easier than generating them [54]. Other recent works improve performance on mathematical tasks by using majority-vote or model confidence as reinforcement learning rewards, enabling performance improvement without access to ground-truth labels [55, 56, 57, 58, 59]. However, all of these methods are fundamentally limited by the model’s current evaluation abilities and self-consistency. In contrast, we view self-improvement through interaction with external data as a more powerful and scalable path. SEAL learns how to best utilize this external data for self-improvement.
```

### seal / ordinary_paragraph--texts-28

Target: #/texts/28; members: none; context-only: none.
Native block role: paragraph; source role: paragraph.

```text
We propose Self-Adapting LLMs (SEAL), a framework that enables language models to improve themselves by generating their own synthetic data and optimization parameters (“self-edits”) in response to new data. The model is trained to produce these self-edits directly through token generation with the data provided in the model’s context. Self-edit generation is learned via reinforcement learning (RL) where the model is rewarded for generating self-edits (SE) that, when applied, improve the model’s performance at the target task. SEAL can therefore be interpreted as an algorithm with two nested loops: an outer RL loop, which optimizes the self-edit generation, and an inner update loop, which uses the generated self-edit to update the model via gradient descent. Our method can be seen as an instance of meta-learning where we meta-learn how to generate effective self-edits.
```

Required math, in source order: `\mathrm{SE}`.

### seal / ordinary_paragraph--texts-30

Target: #/texts/30; members: none; context-only: none.
Native block role: paragraph; source role: paragraph.

```text
Let \theta denote the parameters of the language model \mathrm{LM}_{\theta}. SEAL operates on individual task instances (C,\tau) where C is a context containing information relevant to the task, and \tau defines the downstream evaluation used to assess the model’s adaptation. For example, in knowledge incorporation, C is the passage intended to be integrated into the model’s internal knowledge, and \tau is a set of questions and associated answers about the passage. In few-shot learning, C includes few-shot demonstrations of a novel task, and \tau is the query input and ground-truth output. Given C, the model generates a self-edit SE—the form of which varies by domain (see §3.2)—and updates its parameters via supervised finetuning: \theta' \leftarrow \mathrm{SFT}(\theta,\mathrm{SE}).
```

Required math, in source order: `\theta`; `\mathrm{LM}_{\theta}`; `(C,\tau)`; `C`; `\tau`; `C`; `\tau`; `C`; `\tau`; `C`; `\mathrm{SE}`; `\theta' \leftarrow \mathrm{SFT}(\theta,\mathrm{SE})`.

### seal / ordinary_paragraph--texts-32

Target: #/texts/32; members: none; context-only: none.
Native block role: paragraph; source role: paragraph.

```text
We optimize the self-edit generation process using reinforcement learning: the model takes an action (generating SE), receives a reward r based on \mathrm{LM}_{\theta'}’s performance on \tau, and updates its policy to maximize expected reward:
```

Required math, in source order: `\mathrm{SE}`; `r`; `\mathrm{LM}_{\theta'}`; `\tau`.

### seal / ordinary_paragraph--texts-45

Target: #/texts/45; members: none; context-only: none.
Native block role: paragraph; source role: paragraph.

```text
are sampled from—and, crucially, rewards are computed using—the current model.
```

### seal / ordinary_paragraph--texts-46

Target: #/texts/46; members: none; context-only: none.
Native block role: paragraph; source role: paragraph.

```text
We experimented with various on-policy methods such as Group Relative Policy Optimization (GRPO) [60] and Proximal Policy Optimization (PPO) [61], but found the training to be unstable. Instead, we adopt \mathrm{ReST}^{EM} [36], a simpler approach based on filtered behavior cloning—also known as “rejection sampling + SFT” [62, 63, 64, 35, 65].
```

Required math, in source order: `\mathrm{ReST}^{EM}`.

### seal / ordinary_paragraph--texts-47

Target: #/texts/47; members: none; context-only: none.
Native block role: paragraph; source role: paragraph.

```text
\mathrm{ReST}^{EM} can be viewed as an expectation-maximization (EM) procedure: the E-step samples candidate outputs from the current model policy, and the M-step reinforces only those samples that receive positive reward through supervised finetuning. This approach optimizes an approximation of our objective (1) under the binary reward:
```

Required math, in source order: `\mathrm{ReST}^{EM}`.

### seal / ordinary_paragraph--texts-49

Target: #/texts/49; members: none; context-only: none.
Native block role: paragraph; source role: paragraph.

```text
More precisely, in optimizing (1), we must compute the gradient \nabla_{\theta_t}\mathcal{L}_{\mathrm{RL}}. However, as we noted, the reward term r(\mathrm{SE},\tau,\theta_t) depends on \theta_t in our setup but is not differentiable. We address this by treating the reward as fixed with respect to \theta_t. With this approximation, the Monte-Carlo estimator for a minibatch of N contexts and M sampled self-edits per context becomes
```

Required math, in source order: `\nabla_{\theta_t}\mathcal{L}_{\mathrm{RL}}`; `r(\mathrm{SE},\tau,\theta_t)`; `\theta_t`; `\theta_t`; `N`; `M`.

### seal / ordinary_paragraph--texts-52

Target: #/texts/52; members: none; context-only: none.
Native block role: paragraph; source role: paragraph.

```text
where p_{\theta_t} denotes the model’s autoregressive distribution and y_s^{(i,j)} is the s^{th} token of self-edit \mathrm{SE}_{ij}, the j^{th} sample for context C_i. Since sequences with r = 0 can be ignored in (4), we have shown that \mathrm{ReST}^{EM}, with simple “SFT on good self-edits,” indeed optimizes (1) under the binary reward (2) (with a stop-gradient applied to the reward term). The SEAL training loop is summarized in Alg. 1.
```

Required math, in source order: `p_{\theta_t}`; `y_s^{(i,j)}`; `s^{th}`; `\mathrm{SE}_{ij}`; `j^{th}`; `C_i`; `r=0`; `\mathrm{ReST}^{EM}`.

### seal / ordinary_paragraph--texts-53

Target: #/texts/53; members: none; context-only: none.
Native block role: paragraph; source role: paragraph.

```text
Finally, we note that while the implementation in this work uses a single model for both generating self-edits and learning from these self-edits, it is also possible to decouple these roles. In such a “teacher-student” formulation [66], a student model would be updated using edits proposed by a separate teacher model. The teacher would then be trained via RL to generate edits that maximize student improvement.
```

### controls / formula_envelope--pictures-0

Target: #/pictures/0; members: #/texts/6; context-only: none.
Native block role: formula; source role: formula.

```text
M=\begin{bmatrix}1&-2\\3&4\end{bmatrix}
```

Required math, in source order: `M=\begin{bmatrix}1&-2\\3&4\end{bmatrix}`.

M equals bracketed 2 by 2 matrix; row 1 is 1, -2; row 2 is 3, 4. Preserve negative sign and row/column positions.

### controls / formula_envelope--pictures-1

Target: #/pictures/1; members: #/texts/8; context-only: none.
Native block role: formula; source role: formula.

```text
g(x)=\frac{1}{x+1}
```

Required math, in source order: `g(x)=\frac{1}{x+1}`.

g(x) equals fraction with numerator 1 and denominator entire x+1; not 1/x+1.

### controls / formula_envelope--pictures-2

Target: #/pictures/2; members: #/texts/10; context-only: none.
Native block role: formula; source role: formula.

```text
f(x)=\begin{cases}x^2&\text{if }x\geq0\\0&\text{if }x<0\end{cases}
```

Required math, in source order: `f(x)=\begin{cases}x^2&\text{if }x\geq0\\0&\text{if }x<0\end{cases}`.

f(x) equals two aligned cases under a left brace: x squared if x >= 0; 0 if x < 0. Preserve exponent, branch order, conditions and zero boundary.

### controls / ordinary_paragraph--texts-1

Target: #/texts/1; members: none; context-only: none.
Native block role: paragraph; source role: paragraph.

```text
Original toy source. It supplements real papers; it does not prove real-document quality.
```

### controls / ordinary_paragraph--texts-4

Target: #/texts/4; members: none; context-only: none.
Native block role: paragraph; source role: paragraph.

```text
Let y = x^2 + 1. This is part of the sentence.
```

Required math, in source order: `y=x^2+1`.

### controls / code_item--texts-12

Target: #/texts/12; members: none; context-only: #/texts/13.
Native block role: code; source role: code.

```text
# keep the boundary and block nesting
```

Item 12 includes only the comment; item 13 includes only the six body lines. Other item is context only and must not be transcribed.

### controls / code_item--texts-13

Target: #/texts/13; members: none; context-only: #/texts/12.
Native block role: code; source role: code.

```text
if x <= limit:
    total += x
    if ready:
        emit("ok")
else:
    emit("skip")
```

Required six-line indent levels: 0, 4, 4, 8, 0, 4 spaces.

Item 12 includes only the comment; item 13 includes only the six body lines. Other item is context only and must not be transcribed.

### controls / code_item--texts-14

Target: #/texts/14; members: none; context-only: none.
Native block role: code; source role: paragraph_with_inline_code.

```text
Inline code: items[i] <= limit
```

Source segments must distinguish prose `Inline code: ` from inline code `items[i] <= limit`.

### controls / ordinary_paragraph--texts-15

Target: #/texts/15; members: none; context-only: none.
Native block role: paragraph; source role: paragraph.

```text
Read the source faithfully; preserve operators and nesting. [1]
```

