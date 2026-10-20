# Fixed page reference — OCR crop ablation

Locked before both new OCR arms. Source: arXiv 2303.18223v1 physical page 3, raster fixture physical page 1. Full saved page image visually inspected.

Body order is left column from top to bottom, then right column. There is no legitimate cross-column title. The page number is furniture; footnotes 5 and 6 are checked separately. Paragraph P01 is a continuation and P11 continues on the next page.

The reference keeps the source wording (including “no a formal consensus”). PDFium U+FFFE represents a visual soft-wrap hyphen and is removed in the reference prose only. Original native text and character spans remain in JSON.

## PAGE · page_header · right

3

## P01 · paragraph · left

We are also aware of several related review articles on PLMs or LLMs [32, 36, 38, 39, 43, 48–54]. These papers either discuss PLMs or some specific (or general) aspects of LLMs. Compared with them, we focus on the techniques and methods to develop and use LLMs and provide a relatively comprehensive reference to important aspects of LLMs.

## P02 · paragraph · left

The remainder of the survey is organized as follows: Section 2 introduces the background for the survey article, with the terminology, settings, resources, and organization outline, followed by the summarization of available resources for developing LLMs in Section 3. Sections 4, 5, 6, and 7 review and summarize the recent progress from the four aspects of pre-training, adaptation tuning, utilization, and capacity evaluation, respectively. Finally, we conclude this survey in Section 8 by summarizing the major findings and discuss the remaining issues for future work.

## H01 · section_header · left

2 OVERVIEW

## P03 · paragraph · left

In this section, we introduce the background of LLMs with key terminologies, abilities and techniques.

## P04 · paragraph · left

Background. Typically, large language models (LLMs) refer to language models that contain hundreds of billions (or more) of parameters5, which are trained on massive text data [32], such as GPT-3 [55], PaLM [56], Galactica [35], and LLaMA [57]. Specifically, LLMs are built upon the Transformer architecture [22], where multi-head attention layers are stacked in a very deep neural network. Existing LLMs mainly adopt similar model architectures (i.e., Transformer) and pre-training objectives (i.e., language modeling) as small language models. As the major difference, LLMs largely scale the model size, pre-training data, and total compute (orders of magnification). They can better understand the natural language and generate high-quality text based on the given context (i.e., prompts). Such a capacity improvement can be partially described by the scaling law, where the performance roughly follows a substantial increase with respect to the model size [30]. However, some abilities (e.g., in-context learning [55]) are unpredictable according to the scaling law, which can be observed only when the model size exceeds a certain level (as discussed below).

## P05 · paragraph · left

Emergent Abilities of LLMs. In the literature [31], emergent abilities of LLMs are formally defined as “the abilities that are not present in small models but arise in large models”, which is one of the most distinctive features that distinguish LLMs from previous PLMs. It also introduces a notable characteristic when emergent abilities occur: performance rises significantly above random when the scale reaches a certain level. By analogy, such an emergent pattern has close connections with the phenomenon of phase transition in physics [31, 58]. In principle, emergent abilities can be also defined in relation to some complex tasks [31, 59], while we are more concerned with general abilities that can be applied to solve multiple tasks. Here, we briefly introduce three representative emergent abilities for LLMs, described as follows.

## F05 · footnote · left

5. In existing literature, there is no a formal consensus on the minimum parameter scale for LLMs. In this survey, we mainly focus on discussing LLMs with a model size larger than 10B.

## P06 · paragraph · right

• In-context learning. The in-context learning ability is formally introduced by GPT-3 [55]: assuming that the language model has been provided with a natural language instruction and/or several task demonstrations, it can generate the expected output for the test instances by completing the word sequence of input text, without requiring additional training or gradient updates6.

## P07 · paragraph · right

• Instruction following. By fine-tuning with a mixture of multi-task datasets formatted via natural language descriptions (i.e., instructions), LLMs are shown to perform well on unseen tasks that are also described in the form of instructions [28, 61, 62]. With this ability, instruction tuning enables LLMs to perform new tasks by understanding the task instructions without using explicit examples, which can largely improve the generalization ability.

## P08 · paragraph · right

• Step-by-step reasoning. For small language models, it is usually difficult to solve complex tasks that involve multiple reasoning steps, e.g., mathematical word problems. While, with the chain-of-thought reasoning strategy [33], LLMs can solve such tasks by utilizing the prompting mechanism that involves intermediate reasoning steps for deriving the final answer. This ability is speculated to be potentially obtained by training on code [33, 47].

## P09 · paragraph · right

Key Techniques for LLMs. It has been a long way that LLMs evolve into the current state: general and capable learners. In the development process, a number of important techniques are proposed, which largely improve the capacity of LLMs. Here, we briefly list several important techniques that (potentially) lead to the success of LLMs, as follows.

## P10 · paragraph · right

• Scaling. Scaling is the key factor to increase the model capacity of LLMs. As the initial attempt, GPT-3 firstly increases the model size to an extremely large scale of 175B parameters. Later on, PaLM further raises the parameter scale to a new record of 540B. As discussed before, a large model size is essential to emergent abilities. While, scaling is not only conducted on model size but also related to data size and total compute [34, 63]. A recent study [34] has discussed the optimal schedule among the three aspects of model size, data size, and total compute, given a fixed budget. Further, the quality of the pre-training data plays a key role in achieving good performance, so that data collection and cleaning strategies are very important to consider when scaling the pre-training corpora.

## P11 · paragraph · right

• Training. Due to the huge model size, it is very challenging to successfully train a capable LLM. Distributed training algorithms are needed to learn the network parameters of LLMs, in which various parallel strategies are often jointly utilized. To support distributed training, several optimization frameworks have been released to facilitate the implementation and deployment of parallel algorithms, such as DeepSpeed [64] and Megatron-LM [65]. Besides, optimization tricks are also important for training stability and model performance, e.g., restart with training loss spike [56] and mixed precision training [66]. More recently, GPT-4 [46] proposes to develop special infrastructure and

## F06 · footnote · right

6. In some recent studies [60], it also shows that in-context learning implicitly performs meta-optimization through the attention mechanism.
