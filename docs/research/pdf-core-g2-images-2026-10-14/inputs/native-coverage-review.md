# Native layout image coverage review

2026-10-14. Read-only visual review of six actual PictureItem boxes rerendered from the pinned PDFs, compared with the six frozen target inputs. All six native crops preserve the necessary selected content. Their boxes are distinct from the frozen envelopes; only NCCU contains the entire frozen envelope. This is source coverage, not image-understanding or pipeline acceptance.

| Frozen case | Actual picture | Frozen envelope area covered | Necessary content |
|---|---|---:|---|
| G1-S05 | `#/pictures/0` / `wikiskill-p4-0.png` | 96.32% | Covered |
| G1-C03 | `#/pictures/0` / `controls-p2-0.png` | 66.94% | Covered |
| G1-C04 | `#/pictures/2` / `controls-p2-2.png` | 75.73% | Covered |
| G1-C05 | `#/pictures/1` / `controls-p2-1.png` | 68.52% | Covered |
| G1-C06 | `#/pictures/3` / `controls-p2-3.png` | 51.57% | Covered |
| G1-S07 | `#/pictures/0` / `nccu-p3-0.png` | 100.00% | Covered |

The overlap percentages describe geometry only. They are not a new IoU threshold: the frozen/manual panel envelopes include margins and partly clipped headings, while the necessary source content is judged from the saved PNGs.

## G1-S05

Bottom green return-loop stroke touches the crop edge; its path and upward arrow to Step1 remain visible. Native box omits fixed-envelope margin but no required relation or label is lost.

Visible required content: Skill/Wiki/Raw layer names and skills/wiki/raw paths; Reversible conditional skill update, compounding/never-reset wiki, permanent/write-once immutable traces; Four numbered agents/steps with Step1->Step2->Step3->Step4 directions; Inject Skills/Write Traces, Sample Traces/Consolidate Patterns, Read Skill Wiki Traces, Update Skill if Better/Update Wiki Logs labels and corresponding directional arrows; Step4->next iteration->Step1 return loop and Next Iteration label.

Original Figure2 caption is below both model graphic crops; source-caption provenance remains separate.

## G1-C03

Right end of horizontal axis is slightly truncated at the image edge (native right239.709 versus generator endpoint240 points); no value/category/scale content is lost. Panel title is outside native crop.

Visible required content: Score (%) axis unit and 0/10/20 ticks; Both complete bars with printed values 10 and 20; A/B category labels bound to their bars.

Panel heading is not a numeric observation and is not needed to bind these bars.

## G1-C04

All six data points and both legends are within crop. Panel title is outside native crop.

Visible required content: Score (%) axis and 0/50/100 ticks; Step axis with 1/2/3 labels; Both complete crossing series and endpoint markers; Blue/Orange color legends and their source association.

Do not count overlapping step2 values as one source observation; the fixed oracle has two coincident series points.

## G1-C05

Rightmost step3 label lies close to right edge but remains visibly complete. Panel title is outside native crop.

Visible required content: Value (log10) axis label and 1/10/100 ticks; Step axis and source step1/2/3 labels; All three plotted markers and equal plotted intervals.

No linear-axis substitution; category association and logarithmic scale remain required.

## G1-C06

A and B labels are visibly complete at bottom. Pie circle is fully inside native crop. Panel title is outside native crop.

Visible required content: Complete blue and orange sectors, including shared radial boundaries and complete circle; Color-matched A/B category labels below pie.

Sector values remain unprinted; source labels A/B must not be replaced by unlabeled colors.

## G1-S07

Native crop includes the entire fixed selected panel and additional screenshot context. It is a larger-scope input than the frozen selected-panel PNG.

Visible required content: Complete fixed selected panel within full screenshot; Breadcrumb with 首頁/我的專區/應用系統 in source order; Both central headings plus complete selection/link instruction and B5A label.

Additional visible screenshot text/photos do not expand the fixed S07 oracle or authorize invented follow-up outcomes.

## Offline output review ready

Awaiting saved description/API output paths. The next review will use the exact input IDs/hashes and `oracle-references.json`, evaluate every fixed relation/condition/prohibition/critical comparison, and retain raw output separately from the reviewer verdict. Classifier labels alone cannot satisfy V09.

C03 has 2 exact printed observations; C04 has 6 unprinted series observations, C05 has 3 unprinted log-axis observations and C06 has 2 unprinted sectors. Estimated-value flags, source associations and the existing tolerances remain required. This is 13 observations with fixed per-case checks, not a pooled new acceptance rule.

No native crop, G1 fixture, oracle or production file was changed. No model was run.
