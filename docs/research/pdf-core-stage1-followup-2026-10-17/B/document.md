Body before target tables

Synthetic source caption 1

| Method     | Value                                |
|------------|--------------------------------------|
| Literal 1  | &lt;s&gt;                            |
| Literal 2  | &amp;lt;s&amp;gt;                    |
| Literal 3  | &amp; x &lt; 7 &#124; y              |
| Literal 4  | &#42;literal&#42;                    |
| Literal 5  | &#42;&#42;bold&#42;&#42;             |
| Literal 6  | a&#95;b&#95;c                        |
| Literal 7  | &#96;x&#96;                          |
| Literal 8  | &#91;x&#93;(https://example.invalid) |
| Literal 9  | !&#91;x&#93;(file.png)               |
| Literal 10 | &#92;&#42;x&#92;&#42;                |
| Literal 11 | a&#92;b                              |
| Literal 12 | 001.20                               |
| Literal 13 | 0                                    |
| Literal 14 |                                      |
| Literal 15 | —                                    |
| Literal 16 | CR line                              |
| Literal 17 | CRLF line                            |
| Literal 18 | LF line                              |

Body after target 1

Synthetic source caption 2

| Method      | Setting       | A - Score   | A - Spread   | B - Score   | B - Spread   |
|-------------|---------------|-------------|--------------|-------------|--------------|
| Group alpha | Group alpha   | Group alpha | Group alpha  | Group alpha | Group alpha  |
| Method X    | Setting one   | 001.20      | 0            |             | 1.2 ± 0.3    |
| Method X    | Setting two   | —           | -0.0         | 1e-3        | 10 / 20      |
| Group beta  | Group beta    | Group beta  | Group beta   | Group beta  | Group beta   |
| Method Y    | Setting three | 9           | 0.00         | 8           | 2.0 ± 0.4    |

Body after target 2

| Untouched rich text   |
|-----------------------|

Body after non-target rich table