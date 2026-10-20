"""Lossless PDFium UTF-16 scalar decoding after fixed geometric selection.
No normalization, text matching, region changes, labels or threshold changes.
"""
def decode_selected_utf16(glyphs):
    """Each glyph has page, raw_char_index/raw_index, raw_unicode.
    Keep every original record and its code-unit identity. A complete adjacent
    high/low pair is decoded onto its first record; the second is an explicitly
    retained continuation. An unmatched surrogate is UNKNOWN, never repaired by
    expanding the region or reading an excluded char into the selected text.
    """
    def idx(g):return g.get('raw_char_index',g.get('raw_index'))
    by={(g['page'],idx(g)):g for g in glyphs};out=[];consumed=set();unpaired=[]
    for g in sorted(glyphs,key=lambda g:(g['page'],idx(g))):
        n=idx(g);key=(g['page'],n);u=g['raw_unicode'];g=dict(g)
        if key in consumed:
            g['text']='';g['utf16_role']='LOW_SURROGATE_CONTINUATION';out.append(g);continue
        if 0xD800<=u<=0xDBFF:
            other=by.get((g['page'],n+1));v=other.get('raw_unicode') if other else None
            if v is not None and 0xDC00<=v<=0xDFFF:
                scalar=0x10000+((u-0xD800)<<10)+(v-0xDC00);g['text']=chr(scalar);g['raw_char_indices']=[n,n+1];g['utf16_role']='DECODED_COMPLETE_SURROGATE_PAIR';consumed.add((g['page'],n+1))
            else:g['text']='';g['utf16_role']='UNPAIRED_HIGH_SURROGATE';unpaired.append(key)
        elif 0xDC00<=u<=0xDFFF:g['text']='';g['utf16_role']='UNPAIRED_LOW_SURROGATE';unpaired.append(key)
        else:
            g['text']=chr(u) if u else '';g['raw_char_indices']=[n];g['utf16_role']='BMP_CODE_UNIT'
        out.append(g)
    return {'status':'UNKNOWN' if unpaired else 'KNOWN','glyphs':out,'text':''.join(g['text'] for g in out),'unpaired_surrogate_indices':unpaired,'decoded_pair_count':sum(g['utf16_role']=='DECODED_COMPLETE_SURROGATE_PAIR' for g in out)}
