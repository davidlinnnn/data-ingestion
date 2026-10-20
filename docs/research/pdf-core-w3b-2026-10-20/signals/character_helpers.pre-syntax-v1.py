"""Frozen pre-feature helpers; no cohort discovery, labels, outputs, or R1 reads."""
import re
import unicodedata as ud
from lxml import etree
from latex2mathml.converter import convert
LIGATURES={"ﬀ":"ff","ﬁ":"fi","ﬂ":"fl","ﬃ":"ffi","ﬄ":"ffl","ﬅ":"st","ﬆ":"st"}
OPERATORS=set("+-−×÷*/=<>≤≥≠≈≃≅≡≔∈∉∋⊂⊃⊆⊇∩∪∧∨¬∑∏∫∮√∞±∓→←↔⇒⇐⇔|∥!%&^~:;,()[]{}")
NUMBER=re.compile(r"(?:[0-9]+(?:\.[0-9]+)?|\.[0-9]+)(?:[eE][+−-]?[0-9]+)?")
# Numeric regex intentionally preserves whitespace boundaries and does not merge split digit tokens.
TOKEN_TAGS={"mi","mn","mo","mtext","ms"}
WRAPPERS={"math","semantics","mrow","mstyle","mpadded","mtd","msup","msub","msubsup","mover","munder","munderover","mmultiscripts","none"}
def canonical(text,kind):
    text=ud.normalize("NFC",text.replace("\r\n","\n").replace("\r","\n"))
    if kind=="formula":
        chars=[]
        for c in text:
            # Only mathematical alphanumeric font codepoints, never a global compatibility fold.
            if ud.name(c,"").startswith("MATHEMATICAL ") and 0x1D400<=ord(c)<=0x1D7FF:
                c=ud.normalize("NFKC",c)
            chars.append(LIGATURES.get(c,c))
        text="".join(chars)
    elif kind not in {"code","description"}: raise ValueError("unsupported kind")
    return text

def projection(text,kind):
    s=canonical(text,kind)
    return "".join(s.split()) if kind=="formula" else s

def operators(text,kind):
    # Symbol sequence before style mapping; math alphabet and ligature changes cannot alter these.
    s=ud.normalize("NFC",text.replace("\r\n","\n").replace("\r","\n"))
    return [c for c in s if c in OPERATORS]

def numbers(text,kind):
    # Includes quoted literals. No whitespace/digit concatenation or numeric rounding.
    s=ud.normalize("NFC",text.replace("\r\n","\n").replace("\r","\n"))
    return NUMBER.findall(s)

def levenshtein(a,b):
    if len(a)<len(b):a,b=b,a
    previous=list(range(len(b)+1))
    for i,ca in enumerate(a,1):
        current=[i]
        for j,cb in enumerate(b,1):current.append(min(current[-1]+1,previous[j]+1,previous[j-1]+(ca!=cb)))
        previous=current
    return previous[-1]

def agreement(left,right,kind):
    if left is None or right is None:return {"status":"UNKNOWN","reason":"missing aligned visible text"}
    a,b=projection(left,kind),projection(right,kind)
    if not a or not b:return {"status":"UNKNOWN","reason":"empty aligned visible text"}
    dist=levenshtein(a,b);score=1-dist/max(len(a),len(b));op=operators(left,kind)==operators(right,kind);num=numbers(left,kind)==numbers(right,kind)
    return {"status":"KNOWN","distance":dist,"left_chars":len(a),"right_chars":len(b),"character_similarity":score,"operator_sequence_exact":op,"number_sequence_exact":num,"left_operators":operators(left,kind),"right_operators":operators(right,kind),"left_numbers":numbers(left,kind),"right_numbers":numbers(right,kind),"pass":score>=.95 and op and num}

def mathml_visible(mathml):
    try:root=etree.fromstring(mathml.encode(),parser=etree.XMLParser(resolve_entities=False,no_network=True))
    except Exception as e:return {"status":"UNKNOWN","reason":"MathML parse: "+str(e)}
    unknown=[]
    def walk(n):
        tag=etree.QName(n).localname
        if tag in {"annotation","annotation-xml","mphantom"}:return ""
        if tag in TOKEN_TAGS:return "".join(n.itertext())
        children=list(n)
        if tag=="semantics":return walk(children[0]) if children else ""
        if tag=="mfrac":return "\n".join(walk(c) for c in children)
        if tag=="msqrt":return "√"+"".join(walk(c) for c in children)
        if tag=="mroot" and len(children)==2:return walk(children[1])+"√"+walk(children[0])
        if tag=="mtr":return " ".join(walk(c) for c in children)
        if tag=="mtable":return "\n".join(walk(c) for c in children)
        if tag=="mspace":return " "
        if tag=="mfenced":
            sep=n.get("separators",",");return n.get("open","(")+(sep[0] if sep else "").join(walk(c) for c in children)+n.get("close",")")
        if tag in WRAPPERS:return "".join(walk(c) for c in children)
        unknown.append(tag);return "".join(walk(c) for c in children)
    glyphs=walk(root)
    if unknown or "\\" in glyphs or root.xpath('//*[local-name()="merror"]'):
        return {"status":"UNKNOWN","reason":"unsupported/unresolved MathML or TeX command","unknown_tags":unknown,"visible_text":glyphs}
    return {"status":"KNOWN","visible_text":glyphs,"structural_semantics_verified":False}

def tex_visible(tex):
    try:m=convert(tex)
    except Exception as e:return {"status":"UNKNOWN","reason":"unsupported TeX/converter: "+str(e)}
    r=mathml_visible(m);r["mathml"]=m;return r

def same_region(left,right):
    # Caller must supply source-based identity; never compare reconstruction text to pair items.
    if not left or not right:return False
    if not left.get("pdf_sha256") or left.get("pdf_sha256")!=right.get("pdf_sha256"):return False
    if left.get("page") is None or left.get("page")!=right.get("page"):return False
    for key in ["source_equation_identity","frozen_native_ref_identity","crop_identity"]:
        if left.get(key) and left.get(key)==right.get(key):return True
    return False
