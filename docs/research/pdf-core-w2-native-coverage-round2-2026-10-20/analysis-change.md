# Analysis v2 correction

Preserved first metrics in `analysis-v1/`. Source oracle and geometry unchanged.

The independent geometry arxiv_stamp candidate used an arXiv substring without requiring page margins. Bibliography references consequently generated raw alerts. Frozen metrics require PDF-margin furniture/stamp. Analysis v2 keeps every raw alert in candidate-catalog under furniture_in_body and adds eligible_pdf_margin. Main furniture_contamination counts only alerts whose independent PDF bbox touches x<45pt, x>width-45pt, y<50pt or y>height-45pt (same boundary used for body-region exclusion in round 1); raw matches and reason breakdown remain separate. All counts are candidates, not confirmed pollution/Q4. This correction does not use output content to alter the source oracle.

Analysis v3 preserves analysis-v2. Native body matching now excludes descendants of picture/table nodes even when layer=body and label=text/list_item. Native visible and Markdown remain unchanged. Caption anchors in picture/table text descendants are counted separately as picture_text_separate, not caption-labelled correct_role and not prose contamination. Their label remains a metadata mismatch, without automatically claiming a Q4 error. Audit sample IDs are unchanged in the independent root audit selection.
