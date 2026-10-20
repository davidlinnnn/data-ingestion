# G2 exposure audit — 2026-10-15

**No existing local PDF is certified unseen.** Keep prior G1/G2 inputs, labels and outputs in development/regression. This includes controls/synthetic inputs, SEAL, WikiSkill, DGM, old files called holdout, and every version, mirror, crop, scan, translation or derivative of the same original work. Uncertain exposure is ineligible.

The metadata inventory found **46 PDF paths, 35 distinct byte hashes and 32 excluded work IDs**. It covers the 20-paper pilot, all 10 earlier September candidates (WikiSkill overlaps the pilot), the survey/scan family, controls and historical scratch matrix variants. It uses manifests, source provenance and byte hashing; no new source content, pixels, candidate results, inference or network was inspected.

[Machine-readable audit](exposure-audit.json) records every local PDF path and actual SHA-256, provenance file/hash/pointer, G2 input/artifact manifest hashes and derivative ancestry. The controls include survey and NCCU content; generated or normalized controls must clear all ancestor groups. Controls + survey + NCCU are one connected leakage component, leaving at most 30 conservative components. The 32 work IDs are not 32 independent source/template families. No internal grouped CV may split those ancestors, and no independent-family count is certified.

| Excluded original work/group | PDF paths |
| --- | ---: |
| `acl:2024.findings-emnlp.317` — Dual-teacher Knowledge Distillation for Low-frequency Word Translation | 1 |
| `arxiv:2303.18223` — A Survey of Large Language Models | 2 |
| `arxiv:2502.12110` — A-Mem: Agentic Memory for LLM Agents | 1 |
| `arxiv:2504.15228` — A Self-Improving Coding Agent (SICA) | 1 |
| `arxiv:2505.03335` — Absolute Zero: Reinforced Self-play Reasoning with Zero Data | 1 |
| `arxiv:2505.20286` — Alita: Generalist Agent Enabling Scalable Agentic Reasoning with Minimal Predefinition and Maximal Self-Evolution | 1 |
| `arxiv:2505.22954` — Darwin Gödel Machine: Open-Ended Evolution of Self-Improving Agents | 9 |
| `arxiv:2506.10943` — Self-Adapting Language Models (MIT SEAL) | 1 |
| `arxiv:2508.16153` — Memento: Fine-tuning LLM Agents without Fine-tuning LLMs | 1 |
| `arxiv:2508.19828` — Memory-R1: Enhancing Large Language Model Agents to Manage and Utilize Memories via Reinforcement Learning | 1 |
| `arxiv:2509.25140` — ReasoningBank: Scaling Agent Self-Evolving with Reasoning Memory | 1 |
| `arxiv:2509.25164` — YOLO26: Key Architectural Enhancements and Performance Benchmarking for Real-Time Object Detection | 1 |
| `arxiv:2511.10395` — AgentEvolver: Towards Efficient Self-Evolving Agent System | 1 |
| `arxiv:2511.16043` — Agent0: Unleashing Self-Evolving Agents from Zero Data via Tool-Integrated Reasoning | 1 |
| `arxiv:2601.01885` — Agentic Memory: Learning Unified Long-Term and Short-Term Memory Management for Large Language Model Agents (AgeMem) | 1 |
| `arxiv:2602.08234` — SkillRL: Evolving Agents via Recursive Skill-Augmented Reinforcement Learning | 1 |
| `arxiv:2603.02766` — EvoSkill: Automated Skill Discovery for Multi-Agent Systems | 1 |
| `arxiv:2603.25158` — Trace2Skill: Distill Trajectory-Local Lessons into Transferable Agent Skills | 1 |
| `arxiv:2605.23904` — SkillOpt: Executive Strategy for Self-Evolving Agent Skills | 1 |
| `arxiv:2606.14239` — SelfEvoSkill: Paired Execution Audits for Skill Revision without External Outcome Supervision | 1 |
| `arxiv:2607.03726` — SelfMem: Self-Optimizing Memory for AI Agents | 1 |
| `arxiv:2608.27454` — WikiSkill: Compiling Agent Experience into Persistent Knowledge for Skill Evolution | 2 |
| `arxiv:2610.05923` — VERA: Scaling Verifiable Environments for Agentic co-Evolution | 1 |
| `book:aima-third-edition` — Artificial Intelligence: A Modern Approach, 3rd Edition | 1 |
| `local:knowledge-loop-workflow-decision` — Knowledge-Loop-Workflow-Decision | 1 |
| `nccu:personal-statement-manual` — 個人簡要自述—一般公務人員使用手冊 | 1 |
| `ndhu:internship-system-manual` — 實習機構查詢系統操作文件 | 1 |
| `ntpc:fuzhou-meeting-10` — 新北浮洲第10次市小組會議紀錄 | 1 |
| `roc:1912-02-14-gazette-2` — 1912-02-14臨時公報第2號 | 1 |
| `synthetic:g1-controls-2026-10-14` — G1 original and source-derived controls | 2 |
| `tainan:tech-hearing-2` — 臺南科技產業專區第2次公聽會紀錄（更正掃描版） | 1 |
| `uncertain:historical-profile-matrix` — Historical scratch profile-quality matrix variants | 4 |

The frozen [G1 registry](../../fixtures/pdf-core-g1-2026-10-14/cases.json) remains SHA-256 `8b798cdf808d01782b8dce9fabf85c7373effaa63477248dc1e95f8410813c6a`: **57 cases, 44 source-reviewed positive regression references, 11 declarative negative cases and 2 load protocols; V01–V19 retained**. Pool membership and reviewed source labels are separate from candidate output approval. Positive expectations are linked by registry JSON pointer and byte hash; the audit does not regrade outputs.

Required positive regression anchors remain numbered/appendix heading hierarchy (S02/S03), style-only heading recovery (C07), complete formula/code source objects (C01/C02), ordinary inline math and cross-page/threshold meaning (E13/E14), and the existing SEAL body-continuation/caption source contract. A method that emits nothing or rejects every candidate cannot count those positive requirements as passed. The source-boundary diagnostics do not enlarge the frozen G1 denominator.

No local document has a credible no-prior-viewing attestation. Earlier acquisition status, no selected G1 case, a new crop/hash, or AIMA chapter-selection-pending does not establish independence. The scratch matrix variants have insufficient provenance and remain excluded conservatively. Future metadata-only candidates must establish original-work identity, every ancestor, exposure attestation and group separation before content review or method tuning.

Skipped: source rendering/extraction, model/API calls and output regrading. Risk: this is a local repository audit; remote/private copies, agent memory and model pretraining exposure cannot be certified from these records.
