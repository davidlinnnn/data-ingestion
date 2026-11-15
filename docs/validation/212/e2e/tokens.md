| Document | Pages | Component | Requests | Input | Output | Reasoning | Model |
|---|---|---|---|---|---|---|---|
| paper 16 | 64 | picture-interpretation | 8 | 31,488 | 9,385 | — | claude-sonnet-5-5 |
| paper 16 | 64 | formula | 9 | 3,688 | 557 | — | claude-sonnet-5-5 |
| paper 16 | 64 | code | 0 | 0 | 0 | — |  |
| paper 16 | 64 | document-summary | 38 | 88,172 | 10,699 | — | claude-sonnet-5-5 |
| paper 16 | 64 | d3-check | 20 | 12,189 | 0 | — | d3-mini |

| Document | Pages | Tokens | Tokens per page |
|---|---|---|---|
| paper 16 | 64 | 156,178 | 2,440 |

| | Median | Max |
|---|---|---|
| Tokens per document | 156,178 | 156,178 |
| Tokens per page | 2,440 | 2,440 |

| Component | Share of tokens |
|---|---|
| picture-interpretation | 26.2% |
| formula | 2.7% |
| code | 0.0% |
| document-summary | 63.3% |
| d3-check | 7.8% |

| Component | Requests per document | Tokens per request |
|---|---|---|
| picture-interpretation | 8.0 | 5,109 |
| formula | 9.0 | 472 |
| code | 0.0 | — |
| document-summary | 38.0 | 2,602 |
| d3-check | 20.0 | 609 |

| TPM | VLM | Summary | d3 | Total | VLM + summary |
|---|---|---|---|---|---|
| pilot (0.5 documents/min) | 22,559 | 49,436 | 6,094 | 78,089 | 71,994 |
| prod_mean_93 (6.94 documents/min) | 313,119 | 686,165 | 84,592 | 1,083,875 | 999,284 |
| prod_peak_93 (20.82 documents/min) | 939,357 | 2,058,494 | 253,775 | 3,251,626 | 2,997,851 |
| prod_peak (50 documents/min) | 2,255,900 | 4,943,550 | 609,450 | 7,808,900 | 7,199,450 |
