| Document | Pages | Component | Requests | Input | Output | Reasoning | Model |
|---|---|---|---|---|---|---|---|
| paper 16 | 64 | picture-interpretation | 8 | 31,488 | 9,096 | — | claude-sonnet-5-5 |
| paper 16 | 64 | formula | 9 | 3,688 | 575 | — | claude-sonnet-5-5 |
| paper 16 | 64 | code | 0 | 0 | 0 | — |  |
| paper 16 | 64 | document-summary | 38 | 89,755 | 11,676 | — | claude-sonnet-5-5 |
| paper 16 | 64 | d3-check | 20 | 12,197 | 0 | — | d3-mini |

| Document | Pages | Tokens | Tokens per page |
|---|---|---|---|
| paper 16 | 64 | 158,475 | 2,476 |

| | Median | Max |
|---|---|---|
| Tokens per document | 158,475 | 158,475 |
| Tokens per page | 2,476 | 2,476 |

| Component | Share of tokens |
|---|---|
| picture-interpretation | 25.6% |
| formula | 2.7% |
| code | 0.0% |
| document-summary | 64.0% |
| d3-check | 7.7% |

| Component | Requests per document | Tokens per request |
|---|---|---|
| picture-interpretation | 8.0 | 5,073 |
| formula | 9.0 | 474 |
| code | 0.0 | — |
| document-summary | 38.0 | 2,669 |
| d3-check | 20.0 | 610 |

| TPM | VLM | Summary | d3 | Total | VLM + summary |
|---|---|---|---|---|---|
| pilot (0.5 documents/min) | 22,424 | 50,716 | 6,098 | 79,238 | 73,139 |
| prod_mean_93 (6.94 documents/min) | 311,238 | 703,931 | 84,647 | 1,099,816 | 1,015,169 |
| prod_peak_93 (20.82 documents/min) | 933,715 | 2,111,793 | 253,942 | 3,299,450 | 3,045,508 |
| prod_peak (50 documents/min) | 2,242,350 | 5,071,550 | 609,850 | 7,923,750 | 7,313,900 |
