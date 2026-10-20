# Source-only HTML formula audit — trace share

固定清單後10案，10張原PDF頁PNG均實看。10案局部 TRUSTED_HTML_FORMULA，0已確認LaTeXML誤轉，0定位錯誤，0UNKNOWN。逐案核對alttext、Presentation MathML樹與頁圖，不讀模型輸出。

HTML未以瀏覽器render，render_syntax維持UNKNOWN；內容局部核對不證整篇版本完全一致。P19 cases保留完整原子區塊，LightGCN取有完整LHS/RHS的推導第一列，MatrixCalculus取無矩陣括號的獨立scalar方程行；均不以matrix/cases內部列增加公式分母。

**P-19-2511.10395v1:html-formula:S4.Ex1.m2:r1**

PDF p11 式(17)下面where區塊：兩個importance ratios 的i/v與j/e、new/old policy分子分母皆一致；epsilon_j兩支為hat epsilon_high if hat A_j^(e)>0、epsilon_high otherwise。MathML兩個mfrac與mtable cases分支/條件配對正確。此單位含多個相關定義及完整cases，兩個cases列不是兩個獨立公式。

**P-13-2601.01885v3:html-formula:A1.E12.m1:r1**

PDF p13左欄式(12) Update：m_i左箭頭(c prime,enc(c prime),metadata prime)三元組全部正確；MathML三處prime及enc括號歸屬保留。相鄰式(10)/(11)/(13)未混入，頁碼身分正確。

**F-acm_lightgcn:html-formula:S3.E12X:r1**

PDF p5左欄式(12)第一列確實完整為E^(K)=beta E^(0)+(1-beta) A_tilde E^(K-1)。HTML原式被拆左右math cells，合併同一HTML row後LHS/RHS完整，MathML E的K、0、K-1冪與A tilde正確。下一兩列是此式的推導延續，未宣稱它們在本單位也已評完或是新的獨立公式。

**P-19-2511.10395v1:html-formula:S3.E9.m1:r1**

PDF p6式(9)的Phi: E times pi times S -> T及where rho=Phi(E,pi_explore,s_0)完整對應；MathML domain/codomain、times、箭頭與初始狀態下標0正確；沒有混到式(8)的transition。

**P-16-2505.22954v1:html-formula:A1.E5.m2:r1**

PDF p22附錄Parent Selection式(5) unnormalized weight w_i=s_i h_i，所有三個i下標與乘法正確。周圍式(3) sigmoid、式(4) novelty及式(6) normalized probability均未錯配成本單位。

**F-acm_ngcf:html-formula:S2.E10.m1:r1**

PDF p4右欄式(10) y_hat_NGCF(u,i)=(e_u star)^T e_i star；HTML alttext及MathML保留hat、NGCF、u/i、兩處star與u向量轉置。MathML mmultiscripts把star與T作兩組post-superscript，是同一starred embedding再轉置，未變成item轉置。

**P-20-2505.03335v1:html-formula:A1.E9.m1:r1**

PDF p21附錄A式(9) PPO objective：expectation下q~P(Q),o~pi_old(O|q)，1/|o|、t=1..|o|求和、min兩支、clip的1-epsilon/1+epsilon、兩支A_norm_(f,q)及最外方括號全部相符。MathML的mfrac/munderover/min/clip各層範圍正確。

**F-arxiv_matrixcalculus:html-formula:S4.Ex9.m1:r1**

PDF p7 Generalization of the Jacobian 中央scalar-valued-functions列表第一行為y_1=f_1(bold x)，HTML MathML row三欄合併後一致且有完整LHS/equality/RHS。原array沒有matrix括號或cases共同條件，而是多個scalar方程逐行列出；此行可獨立定位，並非從真正矩陣取元素冒稱公式。ellipsis及其餘y_2/y_m未計入本單位。

**P-20-2505.03335v1:html-formula:S3.E5.m1:r1**

PDF p5式(5) solve reward是indicator_(y=y star)，HTML I的下標條件、等號與y star都保留，MathML的msub涵蓋整個(y=y star)；未錯配到相鄰式(4)/(6)cases。

**P-18-2511.16043v1:html-formula:S3.E6.m1:r1**

PDF p4右欄式(6) majority-vote confidence與y_tilde定義同列：1/k及兩個sum i=1..k、第一indicator o_i=y_tilde、第二indicator o_i=y、argmax下標y皆一致。MathML hat p、tilde y、兩組munderover與argmax munder對象正確；兩個相關定義仍共一source unit，不額外拆兩個樣本。
