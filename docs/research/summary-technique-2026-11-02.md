# Document Summary technique: map-reduce, provenance, verify and repair

Research for #155, 2026-11-02. Sources are primary only: framework source code on GitHub
(LangChain, LlamaIndex, MiniCheck, AlignScore) and the official docs that publish it,
Anthropic's platform docs (platform.claude.com, which docs.claude.com redirects to), and
the original papers on the ACL Anthology or arXiv. Statements marked **Inference** are
this document's reasoning, not something a source says.

## Question

#155 builds the document summary in-house as plan → map → reduce → verify → repair.
The input is a list of sections `{section_id, heading, text}` taken from the docling
document's native headings and body text (see `request()` in
`src/kp_processing/methods/document_summary/__init__.py`). The output is at most
`MAX_SENTENCES` (currently 5) sentences, each citing the `section_id`s that support it.
Map-reduce is wanted for task-queue fairness and native provenance, not mainly for
context size. Corpus body text is 31,933 to 136,201 characters (largest about 34k
tokens). DEV uses Claude Sonnet 5.5; PROD is an on-prem model with an unknown context
window.

Which reduce strategy, provenance mechanism, verification granularity, repair policy,
chunk size and summary length does the primary literature and vendor guidance support?

## Short answer

(a) **Reduce strategy: one flat reduce call, no collapse step.** LangChain's recursive
collapse and LlamaIndex's `tree_summarize` both exist only to fit mapped output into one
context window. At our scale it already fits: about 17 to 20 chunks for the largest paper,
each mapping to a few candidate sentences, is a reduce input of a few thousand tokens
(**Inference**). Cap the map output per chunk, for example at `MAX_SENTENCES` candidates,
so the reduce input has a known upper bound. Add a collapse level only if PROD's context
window turns out smaller than that bound. That would be new machinery, so flag it then
rather than build it now. Do not use refine/incremental. It is sequential, which defeats
the fairness goal. BooookScore also finds it less coherent than hierarchical merging
(89.1 vs 82.5 for GPT-4), though it gives more detail.

(b) **Section ids through reduce: carry them as data, not as model memory.** Map
returns `{text, section_ids}` per candidate. Reduce sees the candidates as a numbered
list and returns, for each final sentence, its text plus the **candidate numbers** it
draws on. Code then sets `section_ids` to the union of those candidates' ids. This is
LlamaIndex's `CitationQueryEngine` pattern: global "Source N" numbers kept in the text,
mapped back to source nodes. It adds one id lookup. In return the reduce model cannot
invent a section id. Keep `parse()`'s existing guard that drops ids never sent. Neither
framework carries per-sentence provenance through reduce. LangChain's collapse only joins
metadata strings per group, and LlamaIndex returns `source_nodes` for the whole response.

(c) **Anthropic Citations: do not use it as the transport.** It is Anthropic-only, so
it cannot be the PROD path. The API returns 400 if citations are combined with structured
outputs. It returns interleaved text blocks that would have to be reassembled into
sentences. Prompted inline ids (ALCE, Summary of a Haystack, LlamaIndex) work with any
model and give the section-level provenance we need. A custom-content document with one
block per section *would* give section-level citations natively, as block indices
(`start_block_index`/`end_block_index`) that map 1:1 to `section_id`. A DEV-only
side-by-side comparison of citation quality would be an extra experiment, not part of the
pipeline.

(d) **Verify: one judge call per summary sentence, against the text of its cited
sections only.** Sentence granularity is what SummaC, MiniCheck and LLM-AggreFact use.
MiniCheck finds that decomposing claims into atomic facts "is not needed" (−1.4 / +0.3
points) and only adds cost. The cited-sections-only scope is ALCE's citation-recall
definition: the concatenated cited passages must entail the statement. It therefore
checks support and the citation together. The judge returns `supported | unsupported`
plus a one-line reason, which repair needs. Expect real judge error: the best LLMs score
about 74 to 77% balanced accuracy on LLM-AggreFact, and FABLES finds even full-context
Claude-3-Opus reaches only 0.58 F1 at catching unfaithful claims. Measure judge agreement
on our corpus before trusting the drop rate.

(e) **Repair prompt shape.** Inputs: the failed sentence, the judge's reason, and the
text of the sentence's cited sections, wrapped in XML tags with their `section_id`.
Instructions: first quote the passages that support any part of the sentence (Anthropic's
quote-first grounding). Then rewrite the sentence minimally so every claim is supported
by those quotes (RARR's "preserve the original output as much as possible"), citing only
the given ids. If nothing in the sections supports it, return an empty sentence. Then run
verify once more and drop the sentence if it still fails. Anthropic's own guidance is the
retract-if-no-quote half of this ("If it can't find a quote, it must retract the claim").
No primary source tests exactly "rewrite once, then drop", and no source reports a
success rate for it. Self-correction works only with external feedback (Huang et al.),
which the judge's reason supplies, but that feedback is itself imperfect.

(f) **Starting values: about 8,000 characters per chunk (about 2k tokens) and
`MAX_SENTENCES = 5`, both as defaults to measure, not as findings.** 2,048-token chunks
are what BooookScore and FABLES used for hierarchical merging. BooookScore finds chunk
size "does not improve hierarchical merging" (91.1 at 2,048 vs 90.3 at 88K for Claude 2),
so chunk size can be chosen for fairness and latency. Pack whole consecutive sections up
to the limit, as LangChain `split_list_of_docs` and LlamaIndex `repack` do. Split an
oversized section at paragraph breaks under the same `section_id`. LangChain raises an
error on a single oversized document, so the plan step needs its own rule for this. No
primary source prescribes a sentence count for paper summaries; 5 is a product choice.
Measure on the 20-paper corpus: map latency per chunk on the PROD model, verify pass rate,
repair success rate, drop rate, final sentence count, and judge agreement with a human
spot check of the 100 or so final sentences.

## Findings

### Q1. Map-reduce in LangChain and LlamaIndex

**LangChain.** The summarization tutorial (v0.3, the last to cover document
summarization) names two approaches: "Stuff", which concatenates documents into one
prompt, and "Map-reduce", which "splits documents into batches, summarizes those, and
then summarizes the summaries". It says map-reduce "is especially effective when
understanding of a sub-document does not rely on preceding context". For "a body of text
with an inherent sequence", it says iterative refinement "may be more effective".
([tutorial notebook](https://github.com/langchain-ai/langchain/blob/v0.3/docs/docs/tutorials/summarization.ipynb))

- Chunking: the tutorial splits text with `CharacterTextSplitter.from_tiktoken_encoder(chunk_size=1000, chunk_overlap=0)`
  and sets `token_max = 1000` for the reduce. These are demonstration values, not
  guidance. (same notebook)
- When mapped outputs are too long: "Here we implement a recursive 'collapsing' of the
  summaries: the inputs are partitioned based on a token limit, and summaries are
  generated of the partitions. This step is repeated until the total length of the
  summaries is within a desired limit." The LangGraph version has a `collapse_summaries`
  node and a conditional edge that loops back to it. (same notebook)
- Source of the collapse (`langchain_classic`, commit `aa13e9c0e94c`):
  `split_list_of_docs` packs documents greedily in order while the cumulative
  `length_func` stays ≤ `token_max`. A single document over the limit raises
  `ValueError("A single document was longer than the context length, we cannot handle this.")`.
  `ReduceDocumentsChain._collapse` loops `while num_tokens > _token_max`. `token_max`
  defaults to 3000. `collapse_max_retries` defaults to `None` ("it will keep trying").
  ([reduce.py](https://github.com/langchain-ai/langchain/blob/aa13e9c0e94c/libs/langchain/langchain_classic/chains/combine_documents/reduce.py))
- Provenance: `collapse_docs` returns one `Document` whose metadata merges the inputs'
  metadata. "All metadata values are strings, and where there are overlapping keys across
  documents the values are joined by `', '`." That is group-level provenance, not
  per-sentence. (same file)
- `ReduceDocumentsChain` and `RefineDocumentsChain` are `@deprecated(since="0.3.1", removal="2.0.0")`.
  ([reduce.py](https://github.com/langchain-ai/langchain/blob/aa13e9c0e94c/libs/langchain/langchain_classic/chains/combine_documents/reduce.py),
  [refine.py](https://github.com/langchain-ai/langchain/blob/aa13e9c0e94c/libs/langchain/langchain_classic/chains/combine_documents/refine.py))
  Refine passes the first document in, then each later document "as well as the previous
  response". It is sequential by construction. (refine.py docstring)

**LlamaIndex** (`llama-index-core`, commit `619d74664e84`):

- `tree_summarize`: "at each recursively step: 1. we repack the text chunks so that each
  chunk fills the context window of the LLM 2. if there is only one chunk, we give the
  final response 3. otherwise, we summarize each chunk and recursively summarize the
  summaries." With `use_async`, the per-chunk summaries run under `asyncio.gather`.
  ([tree_summarize.py](https://github.com/run-llama/llama_index/blob/619d74664e84/llama-index-core/llama_index/core/response_synthesizers/tree_summarize.py))
- `refine`: "We refine through N-1 nodes, where N is the total number of nodes."
  `compact`: "first combine text chunks into larger consolidated chunks that more fully
  utilize the available context window, then refine answers across them."
  ([type.py](https://github.com/run-llama/llama_index/blob/619d74664e84/llama-index-core/llama_index/core/response_synthesizers/type.py))
- Chunking is "repack to fill the window". `PromptHelper` computes the available chunk
  size from the context window minus the prompt, with a default padding of 5 and a
  default `chunk_overlap_ratio = 0.1`.
  ([prompt_helper.py](https://github.com/run-llama/llama_index/blob/619d74664e84/llama-index-core/llama_index/core/indices/prompt_helper.py))
- Provenance: synthesizers return `source_nodes` for the whole response
  ([base.py](https://github.com/run-llama/llama_index/blob/619d74664e84/llama-index-core/llama_index/core/response_synthesizers/base.py)).
  Per-statement provenance exists only in `CitationQueryEngine`. It re-splits nodes into
  512-token pieces labelled globally `"Source {len(new_nodes) + 1}:"`. It prompts "cite
  the appropriate source(s) using their corresponding numbers" with the example "[2] …
  [1]". It defaults to `ResponseMode.COMPACT`, so the numbers travel through the refine
  steps as text.
  ([citation_query_engine.py](https://github.com/run-llama/llama_index/blob/619d74664e84/llama-index-core/llama_index/core/query_engine/citation_query_engine.py))

**Inference.** Both frameworks recurse only for context fit, and neither tracks ids
through a reduce except as model-written text. Stable global ids in the prompt, plus a
code-side mapping, is the only provenance pattern either ships. Short (b) applies it to
candidates, so ids never have to be retyped correctly by the reduce model.

### Q2. Single-pass vs hierarchical vs incremental quality

- **BooookScore** (Chang, Lo, Goyal, Iyyer; ICLR 2024) compares hierarchical merging
  with incremental updating on 100 recent books.
  ([arXiv 2310.00785](https://arxiv.org/abs/2310.00785))
  - Setup: chunks "end at a sentence boundary". Merging joins "as many preceding
    summaries from the same level as possible". The incremental summary is compressed when
    it exceeds 900 tokens. Chunk size is 2,048 tokens, plus one Claude 2 run at 88K.
  - BooookScore, hierarchical vs incremental: GPT-4 89.1 vs 82.5; Claude 2 91.1 vs 78.6;
    Claude 2 (88K) 90.3 vs 90.9; GPT-3.5-Turbo 84.2 vs 67.0; Mixtral 81.5 vs 64.5.
    "Incremental summaries are almost always less coherent than their hierarchical
    counterparts." Chunk size "does not improve hierarchical merging but does
    substantially benefit Claude 2 when using incremental updating."
  - Errors per sentence (%), GPT-4, incremental / hierarchical: entity omission 7.3 /
    3.71, event omission 4.25 / 2.27, causal omission 2.75 / 1.21, discontinuity 2.23 /
    1.56, salience 1.42 / 1.03, duplication 2.12 / 1.18, inconsistency 0.97 / 1.03.
    "Omission errors are the most common" under both. "Hierarchical summarization
    potentially drops long-range dependencies, but its instructions are generally
    simpler."
  - Detail trade-off: annotators preferred incremental for level of detail (83% vs 11%),
    and hierarchical for structure (59% vs 35%) and logic (53% vs 38%).
  - Mitigations reported: prior-context joining during merges, a post-processing prompt
    that removes artifacts such as "in this section", and regeneration of over-length
    merges. None closes the gap. BooookScore measures **coherence**, not faithfulness.
- **FABLES** (Kim et al. 2024) annotates the faithfulness of book summaries produced by
  hierarchical merging, with chunks of 2,048 tokens for GPT-3.5/GPT-4/Mixtral, 100K for
  GPT-4-Turbo and 180K for Claude-3-Opus. Faithful claims: Claude-3-Opus 90.89%, GPT-4
  78.15%, GPT-4-Turbo 77.62%, GPT-3.5-Turbo 71.52%, Mixtral 68.67%. "A majority of
  unfaithful claims require indirect reasoning to refute (50.2%)." All models "were also
  criticized for omitting important information". Claude-3-Opus showed an over-emphasis
  on the book's ending in at least 20% of summaries.
  ([arXiv 2404.01261](https://arxiv.org/abs/2404.01261))
- **Lost in the Middle** (Liu et al., TACL): performance is highest when relevant
  information is at the start or end of the input and degrades in the middle, "even for
  explicitly long-context models".
  ([ACL Anthology 2024.tacl-1.9](https://aclanthology.org/2024.tacl-1.9/))
- **Summary of a Haystack** (Laban et al., EMNLP 2024) studies summarization with
  bracketed document-id citations over about 100k tokens. Full-context Claude 3 Opus
  scores 18.0 and GPT-4o 11.4 on the Joint Score; with a reranker RAG, the top models
  score 30.8 to 36.0; humans 56.1. "The lowest citation score often occurs in the
  full-context setting." Position bias is confirmed: Claude 3 Opus scores 20.4 with the
  relevant documents at the top and 28.0 at the bottom.
  ([ACL Anthology 2024.emnlp-main.552](https://aclanthology.org/2024.emnlp-main.552/))
- **Recursive book summarization** (Wu et al. 2021, OpenAI): summarize sections, then
  summaries of summaries. The summaries match human quality in about 5% of books.
  ([arXiv 2109.10862](https://arxiv.org/abs/2109.10862))

**Inference.** No study finds hierarchical merging less coherent than single-pass at
chunk sizes like ours. BooookScore's 88K hierarchical run is no better than its 2,048
run. Our papers (≤34k tokens) are an order of magnitude shorter than these books, and
our reduce has one level, not a deep tree, so multi-level merge loss mostly does not
arise. The residual risks are what the studies count most: **omission** and
**salience**, because a map call cannot see what matters globally, and **duplication**
across chunks. Both are the reduce prompt's job: select and deduplicate across all
candidates. A cheap mitigation is to give each map call the paper title and the heading
outline (prompt text only, no new step). SummHay's finding that citation quality is worst
in full context supports citing from short map chunks. It is a different task
(multi-document), so treat this as weak evidence.

### Q3. Cited summaries: Anthropic Citations and prompted ids

From [Citations](https://platform.claude.com/docs/en/build-with-claude/citations):

- Chunking: "Document contents are 'chunked' to define the minimum granularity of
  possible citations." "For plain text documents: Content is chunked into sentences that
  can be cited from." "For custom content documents: Your provided content blocks are
  used as-is and no further chunking is done."
- Citation format: plain text gives character ranges (0-indexed, exclusive end). Custom
  content gives "the content block index range (0-indexed) corresponding to the original
  content list provided", as `type: "content_block_location"` with `start_block_index`,
  `end_block_index`, `document_index` and `cited_text`. "Citations must be enabled on
  all or none of the documents within a request."
- `title` and `context` "are passed to the model but not used toward cited content".
  `context` is suggested for "document metadata as text or stringified JSON".
- Reliability: "citations are guaranteed to contain valid pointers to the provided
  documents". "In Anthropic's evaluations, the citations feature is significantly more
  likely to cite the most relevant quotes from documents than purely prompt-based
  approaches." No numbers are given. `cited_text` "does not count toward output tokens".
- **Structured outputs**: "Citations cannot be used together with structured outputs. If
  you enable citations … and also include the `output_config.format` parameter … the API
  returns a 400 error." The page also warns that prompts asking "for only JSON" may yield
  "few or no citations". Its workaround is one line per field, parsed in code.
- Response shape: "multiple text blocks where each text block can contain a claim … and
  a list of citations". "Citations are available on every model" (Claude models).

So custom content with one block per section (heading and text in the block) gives
section-level citations natively: block index i is `sections[i].section_id`.
**Inference:** that would work in DEV, but it is Anthropic-specific, it forbids
structured output, and its text-block boundaries are not our sentence boundaries. The
portable alternative is the prompted approach that ALCE, SummHay and LlamaIndex use.

From [Prompting best practices, long context](https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/claude-prompting-best-practices)
(the long-context-tips URL redirects here):

- "Put long-form data at the top … above your query, instructions, and examples."
  "Queries at the end can improve response quality by up to 30 percent in tests,
  especially with complex, multidocument inputs." The guidance is framed for inputs of
  "20k+ tokens".
- "Wrap each document in `<document>` tags with `<document_content>` and `<source>` (and
  other metadata) subtags."
- "Ground responses in quotes: … ask Claude to quote relevant parts of the documents
  first before carrying out its task."

**ALCE** (Gao, Yen, Yu, Chen; EMNLP 2023), the primary study of prompting for inline
source ids: passages are labelled "Document [1](Title: …)" and the model cites "[1][2]"
at the end of each statement (at most 3). On ELI5, "even the best models lack complete
citation support 50% of the time". Automatic citation recall agrees with humans at
Cohen's κ 0.698 and precision at 0.525.
([ACL Anthology 2023.emnlp-main.398](https://aclanthology.org/2023.emnlp-main.398/))
LlamaIndex's `CitationQueryEngine` (Q1) is the framework version of the same idea.

### Q4. Sentence-level faithfulness verification

- **SummaC** (Laban et al., TACL 2022): NLI models looked weak at inconsistency
  detection because of a "mismatch in input granularity" (sentence-level NLI vs
  document-level task). The fix is "segmenting documents into sentence units and
  aggregating scores between pairs of sentences". SummaCConv reaches 74.4% balanced
  accuracy on their benchmark.
  ([ACL Anthology 2022.tacl-1.10](https://aclanthology.org/2022.tacl-1.10/))
- **AlignScore** (Zha et al., ACL 2023)
  ([Anthology 2023.acl-long.634](https://aclanthology.org/2023.acl-long.634/)): the
  reference code splits the context into sentence-aligned chunks of about 350 words
  (`len(premise.split()) // 350 + 1` chunks), splits the claim into sentences, takes the
  max over chunks per claim sentence, and then the mean over sentences.
  ([inference.py @ a0936d5afee6](https://github.com/yuh-zha/AlignScore/blob/a0936d5afee6/src/alignscore/inference.py))
- **MiniCheck** (Tang, Laban, Durrett; EMNLP 2024): it checks a claim (typically one
  sentence) against grounding documents; a claim is supported if some document supports
  it. "We find that claim decomposition is not needed in our settings". Decomposition
  changed MiniCheck-FT5 by −1.4 and GPT-4 by +0.3 while adding cost.
  ([Anthology 2024.emnlp-main.499](https://aclanthology.org/2024.emnlp-main.499/),
  [arXiv 2404.10774](https://arxiv.org/abs/2404.10774))
  - LLM-AggreFact (10 datasets in the paper, sentence-level human labels), average
    balanced accuracy at threshold 0.5: GPT-4 75.3, MiniCheck-FT5 74.7, Claude-3 Opus
    74.1, Mistral-Large 73.4, AlignScore 70.4, SummaC-ZS 67.9, SummaC-CV 62.1. Test-set
    cost: $0.24 for MiniCheck-FT5 vs $107 for GPT-4 ("400x lower cost").
  - The code packs document sentences into chunks up to the model length, scores each
    chunk, and takes the max support probability.
    ([inference.py @ b58b9fa69acb](https://github.com/Liyan06/MiniCheck/blob/b58b9fa69acb/minicheck/inference.py))
  - The live leaderboard (now 11 datasets) has a top score of 79.5, Bespoke-MiniCheck-7B
    at 77.4, Claude-3.5 Sonnet at 77.2 and gpt-4o-2024-05-13 at 75.9. No newer Claude is
    listed. ([LLM-AggreFact leaderboard](https://llm-aggrefact.github.io/))
- **FActScore** (Min et al., EMNLP 2023) splits a generation into "a series of atomic
  facts" and scores the supported fraction. Its automated estimator has "less than a 2%
  error rate" on the aggregate score (biographies, against Wikipedia).
  ([Anthology 2023.emnlp-main.741](https://aclanthology.org/2023.emnlp-main.741/))
- **LLM judges are imperfect.** On SummEdits, most LLMs are "close to random chance" and
  GPT-4 is "still 8% below estimated human performance"
  ([arXiv 2305.14540](https://arxiv.org/abs/2305.14540)). On TofuEval (sentence-level
  dialogue summaries), LLM judges including GPT-4 "perform poorly and can be outperformed
  by prevailing state-of-the-art specialized factuality evaluation metrics"
  ([arXiv 2402.13249](https://arxiv.org/abs/2402.13249)). In FABLES, auto-raters
  detecting unfaithful claims score F1 0.167 with no evidence and 0.249 with BM25
  evidence; with the entire book they score 0.386 (GPT-4-Turbo) and 0.582
  (Claude-3-Opus), still "too poorly to be a reliable auto-rater"
  ([arXiv 2404.01261](https://arxiv.org/abs/2404.01261)).
- Evidence scope: ALCE's citation recall counts a statement as supported only if "the
  concatenated cited passages" entail it, judged by an NLI model (TRUE, T5-11B).
  Automatic citation recall is 85.1% accurate against human labels.
  ([Anthology 2023.emnlp-main.398](https://aclanthology.org/2023.emnlp-main.398/))
  FABLES points the other way for book-length claims: wider evidence (the whole book)
  beat retrieved evidence.

**Inference.** Sentence granularity is the common choice, and MiniCheck's ablation says
atomic decomposition does not pay for a check like ours. Cited-sections-only is the
right scope for #155. It tests the claim and the citation in one call, and it is what
ALCE measures. Its known cost is the FABLES case: a sentence that synthesizes across
sections but cites too few of them fails. Repair (Q5) handles that by narrowing the
claim, or the sentence is dropped. Our cited sections are short; whole-document
verification would reintroduce a 34k-token call per sentence. A small dedicated checker
(MiniCheck-class) is a credible on-prem option, but it is extra machinery. Choose it only
if the PROD LLM judges poorly on our spot check.

### Q5. Repair of unsupported content

- **RARR** (Gao et al., ACL 2023): research then revise. It generates questions, retrieves
  evidence, an agreement model detects disagreement, and an edit model "minimally" alters
  the text, one evidence snippet at a time, in a single pass over the retrievals. Edits
  over 50 characters, or over 0.5× the original length, are rejected. It "tends to
  preserve rather than delete claims that it cannot attribute". On PaLM outputs for NQ,
  auto-AIS attribution rises from 45.6 to 54.9 with intent preservation around 90%.
  ([Anthology 2023.acl-long.910](https://aclanthology.org/2023.acl-long.910/),
  [arXiv 2210.08726](https://arxiv.org/abs/2210.08726))
- **Compression-based post-editing** (Fabbri et al., EMNLP 2022) deletes unsupported
  (extrinsic) entities from summaries instead of rewriting them. It improves "entity
  precision by up to 30% on XSum" while keeping ROUGE, and 38% stacked on another
  post-editor. ([arXiv 2211.06196](https://arxiv.org/abs/2211.06196))
- **Self-correction needs external feedback** (Huang et al., ICLR 2024): without it,
  performance "even degrades after self-correction". Reported gains "result from using
  oracle labels to guide the self-correction process". "When valid external feedback is
  available, it is beneficial to leverage it properly."
  ([arXiv 2310.01798](https://arxiv.org/abs/2310.01798))
- **Anthropic's guidance**: "Verify with citations: … have Claude verify each claim by
  finding a supporting quote after it generates a response. If it can't find a quote, it
  must retract the claim." The worked example removes unsupported claims and marks them
  with "[]".
  ([Reduce hallucinations](https://platform.claude.com/docs/en/test-and-evaluate/strengthen-guardrails/reduce-hallucinations))

**Inference.** The literature has the two halves of #155's policy: minimal evidence-bound
rewrite (RARR) and deletion (Fabbri et al.; Anthropic's retract rule). It does not test
the combination "one rewrite, re-verify, else drop", and no source reports a revision
success rate for that setting. The judge's reason is external feedback in Huang et al.'s
sense, but not an oracle, so a rewrite may "pass" because of a judge error. The
re-verify step bounds this but does not remove it. Taking RARR's preservation constraint
into the prompt ("change as little as possible", "do not add claims") is free. A
code-side edit-distance cap is optional.

### Q6. Chunk size and summary length

- Chunk sizes used in the primary studies: 2,048 tokens for hierarchical merging in
  BooookScore and FABLES (with 88K/100K/180K long-context variants). BooookScore finds
  no coherence gain for hierarchical merging from larger chunks.
  ([BooookScore](https://arxiv.org/abs/2310.00785), [FABLES](https://arxiv.org/abs/2404.01261))
- Framework defaults are about fitting the window, not about quality. LangChain's
  `token_max` is 3000, and its tutorial uses 1000 for demonstration. LlamaIndex repacks
  to fill the window, and `CitationQueryEngine` uses 512-token citation chunks (Q1).
  Checkers chunk the evidence side at about 350 words (AlignScore) or up to model length
  (MiniCheck) (Q4).
- OpenAI's cookbook (vendor guidance, not a study): a single-call summary "isn't
  proportional to the length of the document". "By controlling the number of text chunks
  and their sizes, we can ultimately control the level of detail in the output."
  ([Summarizing long documents](https://github.com/openai/openai-cookbook/blob/main/examples/Summarizing_long_documents.ipynb))
- Summary length: Chain of Density (Adams et al. 2023) holds length fixed and adds
  entities. Readers preferred denser summaries, "almost as dense as human written
  summaries", and the paper names a trade-off between "informativeness and readability".
  ([arXiv 2309.04269](https://arxiv.org/abs/2309.04269)) No primary source found
  prescribes a sentence count for a paper summary.

**Inference.** 8,000 characters is about 2k tokens at the corpus's own ratio (136,201
characters ≈ 34k tokens). That matches the studies' 2,048-token chunks. It gives roughly
4 to 17 chunks per corpus paper, plus extra from section boundaries. Detail is controlled
by the per-chunk candidate cap and `MAX_SENTENCES`, not by chunk size.

## What the sources do not say (measure on the corpus, or ask)

- PROD's context window, and whether the on-prem serving stack supports JSON-schema
  constrained output. Ask the platform owners. This decides whether a collapse level or
  a parse-and-retry fallback is needed.
- The success rate of a single evidence-bound rewrite followed by re-verification, and
  the drop rate it implies. Measure per paper.
- How well Claude Sonnet 5.5, or the PROD model, works as a sentence-vs-section judge.
  It is not on LLM-AggreFact. Spot-check about 100 final sentences by hand.
- Whether Anthropic Citations is more accurate than prompted section ids. Anthropic's
  claim of "significantly more likely" comes with no numbers.
- Any chunk-size or sentence-count guidance specific to academic papers or to summaries
  of five sentences or fewer.
- Whether giving map calls the heading outline reduces omission or salience errors.
  This is untested here and would be an A/B on the corpus.

## Sources

Vendor documentation:
- Anthropic, Citations — https://platform.claude.com/docs/en/build-with-claude/citations
- Anthropic, Prompting best practices (long context) — https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/claude-prompting-best-practices
- Anthropic, Reduce hallucinations — https://platform.claude.com/docs/en/test-and-evaluate/strengthen-guardrails/reduce-hallucinations
- LangChain, Summarize Text tutorial (v0.3 notebook) — https://github.com/langchain-ai/langchain/blob/v0.3/docs/docs/tutorials/summarization.ipynb
- OpenAI Cookbook, Summarizing long documents — https://github.com/openai/openai-cookbook/blob/main/examples/Summarizing_long_documents.ipynb
- LLM-AggreFact leaderboard (MiniCheck authors) — https://llm-aggrefact.github.io/

Source code:
- LangChain `langchain_classic` combine_documents `reduce.py`, `refine.py` @ aa13e9c0e94c — https://github.com/langchain-ai/langchain/tree/aa13e9c0e94c/libs/langchain/langchain_classic/chains/combine_documents
- LlamaIndex core `tree_summarize.py`, `refine.py`, `compact_and_refine.py`, `type.py`, `base.py`, `prompt_helper.py`, `citation_query_engine.py` @ 619d74664e84 — https://github.com/run-llama/llama_index/tree/619d74664e84/llama-index-core/llama_index/core
- MiniCheck `minicheck/inference.py` @ b58b9fa69acb — https://github.com/Liyan06/MiniCheck
- AlignScore `src/alignscore/inference.py` @ a0936d5afee6 — https://github.com/yuh-zha/AlignScore

Papers:
- Chang et al., BooookScore, ICLR 2024 — https://arxiv.org/abs/2310.00785
- Kim et al., FABLES, 2024 — https://arxiv.org/abs/2404.01261
- Liu et al., Lost in the Middle, TACL — https://aclanthology.org/2024.tacl-1.9/
- Laban et al., Summary of a Haystack, EMNLP 2024 — https://aclanthology.org/2024.emnlp-main.552/
- Wu et al., Recursively Summarizing Books with Human Feedback, 2021 — https://arxiv.org/abs/2109.10862
- Gao et al., ALCE: Enabling LLMs to Generate Text with Citations, EMNLP 2023 — https://aclanthology.org/2023.emnlp-main.398/
- Laban et al., SummaC, TACL 2022 — https://aclanthology.org/2022.tacl-1.10/
- Zha et al., AlignScore, ACL 2023 — https://aclanthology.org/2023.acl-long.634/
- Tang, Laban, Durrett, MiniCheck, EMNLP 2024 — https://aclanthology.org/2024.emnlp-main.499/
- Min et al., FActScore, EMNLP 2023 — https://aclanthology.org/2023.emnlp-main.741/
- Laban et al., LLMs as Factual Reasoners (SummEdits), 2023 — https://arxiv.org/abs/2305.14540
- Tang et al., TofuEval, NAACL 2024 — https://arxiv.org/abs/2402.13249
- Gao et al., RARR, ACL 2023 — https://aclanthology.org/2023.acl-long.910/
- Fabbri et al., Compression-Based Post-Editing, EMNLP 2022 — https://arxiv.org/abs/2211.06196
- Huang et al., LLMs Cannot Self-Correct Reasoning Yet, ICLR 2024 — https://arxiv.org/abs/2310.01798
- Adams et al., Chain of Density, 2023 — https://arxiv.org/abs/2309.04269

Not relied on: blog posts on chunk-size tuning and on LLM-AggreFact (the MiniCheck
README links one) turned up in search. They are secondary or vendor marketing, so this
document cites the code, papers and leaderboard instead.
