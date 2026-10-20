Figure 6: Performance gains of Answer Agent increase when paired with stronger Memory Managers, showing compounding benefits from higher memory quality.

<!-- image -->

Table 2: Reward Design Choice Comparison. PPO with J-based reward achieves higher J scores but lower F1 and B1 due to verbose outputs, while the EM-based reward yields balanced performance across metrics.

|                             |   F1↑ |   B1↑ |    J↑ |
|-----------------------------|-------|-------|-------|
| PPO (J-based reward model)  | 33.69 | 23.36 | 63.58 |
| PPO (EM-based reward model) | 41.05 | 32.91 | 57.54 |

exact match against ground-truth answers as the reward signal. As shown in Figure 7, GRPO exhibits faster initial convergence, likely due to its grouped return normalization providing stronger early guidance. However, as training progresses, both methods steadily improve and ultimately reach comparable final reward levels.

Reward Design Analysis We experimented with different reward models for fine-tuning the Answer Agent. As shown in Table 2, using the LLMas-a-Judge value as reward leads to the highest J score (63.58), but performs poorly on F1 and BLEU-1. This is because the reward encourages longer, descriptive answers, which misaligns with string-overlap metrics. For example, when asked "Did John and James study together?", the EMbased model outputs "Yes", while the LLM-as-aJudge–based model produces "Yes, John and James studied together, as they were part of the same online programming group, as implied by the memories above." Although both are semantically correct, the latter is penalized under F1 and BLEU-1. This makes direct comparison with baselines difficult, since responses are no longer length-controlled. To avoid bias from relying on a single metric, we adopt the EM reward, which yields balanced improvements across all three metrics.

Figure 7: Training reward curves for PPO and GRPO on the Answer Agent using exact match as the reward. GRPO converges faster initially, and both reach similar final rewards.

<!-- image -->

Figure 8: Accuracy and latency comparison across different inference pipelines: Base, Base + Reranker, and Memory-R1 (GRPO).

<!-- image -->

Comparison of Learned Memory Distillation and Reranking We compare learned memory distillation in Memory-R1 with reranker-based pipelines in terms of accuracy and inference latency across three settings: Base, Base + Reranker, and Memory-R1 with a GRPO-trained Answer Agent (Figure 8). While reranking provides modest accuracy gains, it incurs substantial latency overhead. In contrast, Memory-R1 achieves higher accuracy with lower median and tail latency, demonstrating a more favorable accuracy–latency trade-off. Additional analyses are provided in Appendix G .

## 5 Conclusion

We presented Memory-R1, a reinforcement learning framework that enables LLM-based agents to effectively manage and utilize external memory. Unlike heuristic pipelines, Memory-R1 learns memory operations as well as memory distillation and usage for answering. With only 152 training examples, it achieves state-of-the-art results on LoCoMo, scales across model sizes, and generalizes to MSC and LongMemEval without retraining. Ablation studies confirm that reinforcement learning improves every component of the system. Overall, Memory-R1 highlights reinforcement learning as a promising direction for adaptive and agentic memory in LLMs.