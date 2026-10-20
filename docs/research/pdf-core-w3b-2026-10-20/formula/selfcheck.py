from lxml import html
import build_oracle as b
m=html.fromstring(r'<math alttext="A=\begin{pmatrix}1&amp;2\\3&amp;4\end{pmatrix}"><semantics><mrow><mtable><mtr><mtd>1</mtd><mtd>2</mtd></mtr><mtr><mtd>3</mtd><mtd>4</mtd></mtr></mtable></mrow></semantics></math>')
assert len(b.split_math(m))==1
m=html.fromstring(r'<math alttext="\begin{aligned}a&amp;=b\\c&amp;=d\end{aligned}"><semantics><mtable><mtr><mtd>a=b</mtd></mtr><mtr><mtd>c=d</mtd></mtr></mtable></semantics></math>')
r=b.split_math(m);assert len(r)==2 and r[0]['latex']=='a =b'and r[1]['latex']=='c =d'
assert b.row_tex_split(r'\begin{aligned}A&amp;=\begin{matrix}1&amp;2\\3&amp;4\end{matrix}\\b&amp;=c\end{aligned}','aligned')==[r'A&amp;=\begin{matrix}1&amp;2\\3&amp;4\end{matrix}',r'b&amp;=c']
print('PASS matrix atomic / align two rows / nested matrix rows not split')

assert b.row_tex_split(r'\begin{array}[]{rl}a&=b\\c&=d\end{array}','array')==['a&=b','c&=d']
assert b.standalone_row(r'A&=\begin{matrix}1&2\\3&4\end{matrix}')==r'A =\begin{matrix}1&2\\3&4\end{matrix}'
