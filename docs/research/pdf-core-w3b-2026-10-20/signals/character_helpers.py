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


def xml_entity_compat(text):
    import html.entities
    from html import escape
    builtins={"amp","lt","gt","apos","quot"}
    def replace(match):
        name=match.group(1)
        if name in builtins:return match.group(0)
        value=html.entities.html5.get(name+";")
        if value is None:raise ValueError("unknown named entity: "+name)
        return escape(value,quote=False)
    text=re.sub(r"&([A-Za-z][A-Za-z0-9]+);",replace,text)
    return re.sub(r"&(?!#(?:[0-9]+|x[0-9A-Fa-f]+);|(?:amp|lt|gt|apos|quot);)","&amp;",text)

def mathml_visible(mathml):
    try:root=etree.fromstring(xml_entity_compat(mathml).encode(),parser=etree.XMLParser(resolve_entities=False,no_network=True))
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


def _tex_syntax_preflight(tex):
    """READY is not syntax success: actual Chrome render remains required."""
    import latex2mathml.commands as commands
    from latex2mathml.symbols_parser import SYMBOLS
    if not tex or not tex.strip():return {"status":"UNKNOWN","pass":None,"reason":"empty input"}
    # Escape-aware control sequences; comments extend to newline only for unescaped %.
    tokens=[];clean=[];i=0
    while i<len(tex):
        if tex[i]=="%":
            j=tex.find("\n",i);i=len(tex) if j<0 else j;continue
        if tex[i]=="\\":
            match=re.match(r"\\(?:[A-Za-z]+|.)",tex[i:],re.S)
            if match:
                token=match.group();tokens.append(token);clean.append(token);i+=len(token);continue
        clean.append(tex[i]);i+=1
    clean="".join(clean)
    known=set(SYMBOLS)
    def collect(v):
        if isinstance(v,str) and v.startswith("\\"):known.add(v)
        elif isinstance(v,(list,tuple,set)): 
            for x in v:collect(x)
        elif isinstance(v,dict):
            for x in list(v)+list(v.values()):collect(x)
    for v in vars(commands).values():collect(v)
    unsupported=sorted(set(t for t in tokens if t not in known or t in {r"\verb",r"\Verb",r"\verbatim"}))
    allowed_env={"matrix","pmatrix","bmatrix","Bmatrix","vmatrix","Vmatrix","smallmatrix","array","aligned","align","align*","split","cases","gathered"}
    envs=re.findall(r"\\(?:begin|end)\{([^{}]+)\}",clean)
    if unsupported or any(e not in allowed_env for e in envs):return {"status":"UNKNOWN","pass":None,"reason":"unsupported commands or environments","unsupported_commands":unsupported,"unsupported_environments":[e for e in envs if e not in allowed_env]}
    alignment_envs={"matrix","pmatrix","bmatrix","Bmatrix","vmatrix","Vmatrix","smallmatrix","array","aligned","align","align*","split","cases","gathered"}
    stack=[]
    token_pattern=re.compile(r"\\begin\{([^{}]+)\}|\\end\{([^{}]+)\}|\\(?:[A-Za-z]+|.)|&",re.S)
    for match in token_pattern.finditer(clean):
        if match.group(1):stack.append(match.group(1));continue
        if match.group(2):
            if stack and stack[-1]==match.group(2):stack.pop()
            continue
        if match.group()=="&" and not any(e in alignment_envs for e in stack):
            if any(t in {r"\matrix",r"\pmatrix",r"\cases",r"\eqalign"} for t in tokens):
                return {"status":"UNKNOWN","pass":None,"reason":"macro alignment grammar not established by environment-stack guard"}
            return {"status":"KNOWN","pass":False,"reason":"misplaced raw TeX alignment tab outside supported alignment environment","syntax_error":"MISPLACED_ALIGNMENT_TAB"}
    # The scanner skips escaped braces (\{, \}) and braces inside comments.
    depth=0;i=0
    while i<len(clean):
        if clean[i]=="\\":
            m=re.match(r"\\(?:[A-Za-z]+|.)",clean[i:],re.S);i+=len(m.group()) if m else 1;continue
        if clean[i]=="{":depth+=1
        elif clean[i]=="}":
            depth-=1
            if depth<0:return {"status":"KNOWN","pass":False,"reason":"unmatched closing TeX brace","syntax_error":"UNBALANCED_BRACES"}
        i+=1
    if depth:return {"status":"KNOWN","pass":False,"reason":"unmatched opening TeX brace","syntax_error":"UNBALANCED_BRACES"}
    definite={"NumeratorNotFoundError","DenominatorNotFoundError","ExtraLeftOrMissingRightError","MissingSuperScriptOrSubscriptError","DoubleSubscriptsError","DoubleSuperscriptsError","NoAvailableTokensError","InvalidStyleForGenfracError","MissingEndError","InvalidAlignmentError","InvalidWidthError","LimitsMustFollowMathOperatorError"}
    try:mathml=convert(clean)
    except Exception as e:
        return {"status":"KNOWN" if type(e).__name__ in definite else "UNKNOWN","pass":False if type(e).__name__ in definite else None,"reason":"supported-grammar parse error: "+type(e).__name__+": "+str(e),"syntax_error":type(e).__name__}
    try:root=etree.fromstring(xml_entity_compat(mathml).encode(),parser=etree.XMLParser(resolve_entities=False,no_network=True))
    except Exception as e:return {"status":"UNKNOWN","pass":None,"reason":"MathML entity/XML parsing unsupported: "+str(e)}
    required=root.xpath('//*[local-name()="mfrac" or local-name()="msqrt" or local-name()="mroot"]')
    if any((etree.QName(node).localname in {"mfrac","mroot"} and len(node)!=2) or (etree.QName(node).localname=="msqrt" and not len(node)) for node in required):
        return {"status":"KNOWN","pass":False,"reason":"invalid supported MathML required-argument arity","syntax_error":"INVALID_MATHML_ARITY","mathml":mathml}
    if any(not "".join(child.itertext()).strip() for node in required for child in list(node)):
        return {"status":"UNKNOWN","pass":None,"reason":"converter produced empty required argument; incomplete grammar vs explicit empty TeX argument unresolved","mathml":mathml}
    check=mathml_visible(mathml)
    if check["status"]!="KNOWN":return {"status":"UNKNOWN","pass":None,"reason":check.get("reason"),"mathml":mathml}
    return {"status":"READY_FOR_ACTUAL_RENDER","pass":None,"mathml":mathml,"visible_text":check["visible_text"],"reason":"conversion/syntax preflight only, not actual render success"}


def tex_syntax_preflight(tex):
    result=_tex_syntax_preflight(tex)
    state=result['status']
    result['raw_tex_syntax']={'status':'KNOWN' if state in {'KNOWN','READY_FOR_ACTUAL_RENDER'} else 'UNKNOWN','pass':False if state=='KNOWN' and result.get('pass') is False else True if state=='READY_FOR_ACTUAL_RENDER' else None,'reason':result.get('reason'),'scope':'Supported subset guards, not an actual TeX compiler.'}
    result['mathml_serialization']={'status':'KNOWN' if state=='READY_FOR_ACTUAL_RENDER' else 'NOT_ATTEMPTED_OR_UNKNOWN','pass':True if state=='READY_FOR_ACTUAL_RENDER' else None,'named_entities':'Known HTML5 names -> equal Unicode; XML builtins retained; unknown names UNKNOWN.','bare_ampersand':'Equivalent XML escape only; never deleting glyphs or overriding raw TeX syntax failure.'}
    result['actual_render']={'status':'UNKNOWN','pass':None,'reason':'Not yet Chrome-rendered; raw syntax failure need not render.'}
    return result
