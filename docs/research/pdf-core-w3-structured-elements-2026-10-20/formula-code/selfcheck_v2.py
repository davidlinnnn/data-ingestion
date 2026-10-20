import scoring as s
assert s.math_tokens(r'\mathbf{x}_i+\mathrm{y}\hspace{2em}')==s.math_tokens('x_i+y')
assert s.math_tokens(r'\mathbb{R}\vspace{1pt}')==s.math_tokens('R')
assert s.math_tokens('x<y')!=s.math_tokens('x<=y')
assert s.math_tokens('x_i')!=s.math_tokens('x_j')
assert s.math_tokens(r'\$10')!=s.math_tokens('§10')
assert s.math_tokens('$10')!=s.math_tokens('§10')
assert s.code_tokens('"①"')!=s.code_tokens('"1"')
d={'body':{'children':[{'$ref':'#/texts/1'},{'$ref':'#/pictures/0'}]},'texts':[{'self_ref':'#/texts/0','text':'A'},{'self_ref':'#/texts/1','text':'B'}],'pictures':[{'children':[{'$ref':'#/texts/0'}],'captions':[{'$ref':'#/texts/0'}]}]}
assert s.body_order(d)==['#/texts/1','#/texts/0']
assert [x['text']for x in s.ordered_items(d,d['texts'])]==['B','A']
assert s.text_source({'env':'verbatim','raw':'\n  x = 1\n'})=='  x = 1'
print('PASS font/spacing, inequality/index/currency, Unicode literal, body tree/picture/caption dedup')
