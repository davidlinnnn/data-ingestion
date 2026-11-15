| Document | Pages | Component | Requests | Input | Output | Reasoning | Model |
|---|---|---|---|---|---|---|---|
| paper 1 | 28 | picture-interpretation | 11 | 47,427 | 4,340 | — | claude-sonnet-5-5 |
| paper 1 | 28 | formula | 8 | 3,347 | 614 | — | claude-sonnet-5-5 |
| paper 1 | 28 | code | 0 | 0 | 0 | — |  |
| paper 1 | 28 | document-summary | 50 | 109,749 | 14,079 | — | claude-sonnet-5-5 |
| paper 1 | 28 | d3-check | 24 | 16,051 | 0 | — | d3-mini |
| paper 3 | 25 | picture-interpretation | 8 | 35,056 | 6,696 | — | claude-sonnet-5-5 |
| paper 3 | 25 | formula | 6 | 2,493 | 910 | — | claude-sonnet-5-5 |
| paper 3 | 25 | code | 0 | 0 | 0 | — |  |
| paper 3 | 25 | document-summary | 51 | 102,169 | 12,631 | — | claude-sonnet-5-5 |
| paper 3 | 25 | d3-check | 28 | 21,514 | 0 | — | d3-mini |
| paper 4 | 27 | picture-interpretation | 4 | 18,199 | 4,673 | — | claude-sonnet-5-5 |
| paper 4 | 27 | formula | 3 | 1,277 | 285 | — | claude-sonnet-5-5 |
| paper 4 | 27 | code | 0 | 0 | 0 | — |  |
| paper 4 | 27 | document-summary | 47 | 107,783 | 13,968 | — | claude-sonnet-5-5 |
| paper 4 | 27 | d3-check | 13 | 15,031 | 0 | — | d3-mini |
| paper 7 | 18 | picture-interpretation | 6 | 26,392 | 4,563 | — | claude-sonnet-5-5 |
| paper 7 | 18 | formula | 2 | 826 | 223 | — | claude-sonnet-5-5 |
| paper 7 | 18 | code | 0 | 0 | 0 | — |  |
| paper 7 | 18 | document-summary | 39 | 75,277 | 10,104 | — | claude-sonnet-5-5 |
| paper 7 | 18 | d3-check | 9 | 6,533 | 0 | — | d3-mini |

| Document | Pages | Tokens | Tokens per page |
|---|---|---|---|
| paper 1 | 28 | 195,607 | 6,986 |
| paper 3 | 25 | 181,469 | 7,259 |
| paper 4 | 27 | 161,216 | 5,971 |
| paper 7 | 18 | 123,918 | 6,884 |

| | Median | Max |
|---|---|---|
| Tokens per document | 171,342 | 195,607 |
| Tokens per page | 6,935 | 7,259 |

| Component | Share of tokens |
|---|---|
| picture-interpretation | 22.3% |
| formula | 1.5% |
| code | 0.0% |
| document-summary | 67.3% |
| d3-check | 8.9% |

| Component | Requests per document | Tokens per request |
|---|---|---|
| picture-interpretation | 7.2 | 5,081 |
| formula | 4.8 | 525 |
| code | 0.0 | — |
| document-summary | 46.8 | 2,384 |
| d3-check | 18.5 | 799 |

| TPM | VLM | Summary | d3 | Total | VLM + summary |
|---|---|---|---|---|---|
| pilot (0.5 documents/min) | 19,665 | 55,720 | 7,391 | 82,776 | 75,385 |
| prod_mean_93 (6.94 documents/min) | 272,952 | 773,394 | 102,589 | 1,148,934 | 1,046,346 |
| prod_peak_93 (20.82 documents/min) | 818,856 | 2,320,181 | 307,766 | 3,446,803 | 3,139,037 |
| prod_peak (50 documents/min) | 1,966,512 | 5,572,000 | 739,112 | 8,277,625 | 7,538,512 |
