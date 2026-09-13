"""THROWAWAY: record visually grounded real-page plan before recognition."""
import hashlib,json,sys
from pathlib import Path
root=Path(__file__).resolve().parent
source=Path(sys.argv[1]); manifest=json.loads((source/'manifest.json').read_text())
# All excerpts transcribed from page renders before recognition; not native text output.
specs=[
('01',1,'scan',['第10次專案小組研商會議紀錄','109年12月28日','新北市政府交通局','15公尺為30公尺'],['新北市政府交通局','新北市政府捷運工程局'],[]),
('01',2,'scan',['新北市政府地政局','15公尺為8-9公尺','專案小組初步建議意見'],['新北市政府地政局','新北市政府城鄉發展局','專案小組初步建議意見'],[]),
('02',1,'scan_table',['114年11月20日','下午2時30分','臺南市中西區西賢里活動中心','綜合回覆'],['會議時間','會議地點','會議內容','綜合回覆'],[]),
('02',2,'scan_table',['3.38公頃','20公尺寬道路','30公尺寬之道路'],['陸蟹棲地與生態通道','公園系統與生態跳島','工程設計與施工管理原則'],[]),
('03',3,'mixed',['登入方法','自然人憑證登入或帳號登入'],['登入方法','進入人事服務網','自然人憑證登入或帳號登入'],['我的專區','最新公告']),
('03',4,'mixed',['操作說明','輸入字數請勿超過2000字'],['操作說明','畫面','說明','輸入字數請勿超過2000字'],['儲存','機關代碼','個人簡要自述登打作業']),
('04',6,'mixed',['系統操作介面','首頁及登入','圖2教育部實習機構查詢系統'],['首頁及登入','圖2教育部實習機構查詢系統'],['實習檢核','媒合評估','專案緣起','最新消息']),
('04',7,'mixed',['連續登入錯誤達5次','於15分鐘後會自動解鎖'],['圖3','圖4','開啟瀏覽器','帳號安全防護說明'],['使用者登入','忘記密碼','查詢資料使用注意說明','確認同意']),
('05',1,'historical_scan_supplement',['通告','臨時公報','十二月二十七日'],[],[])
]
byid={c['id']:c for c in manifest['candidates']}; sources=[]
for c in byid.values():
 p=source/c['file'];assert hashlib.sha256(p.read_bytes()).hexdigest()==c['sha256'];sources.append({k:c[k] for k in ['id','file','title','category','source_page','url','sha256','bytes']})
pages=[dict(source_id=i,page=n,category=t,content_anchors=a,ordered_anchors=o,screenshot_only_anchors=s) for i,n,t,a,o,s in specs]
plan=dict(baseline='12ac5a2c4d4d880a9744a743e6fce1e0d3055799',source_manifest_sha256=hashlib.sha256((source/'manifest.json').read_bytes()).hexdigest(),sources=sources,pages=pages,criteria='Diagnostic only: exact anchors after whitespace removal; order of first occurrence separately recorded; no punctuation/hyphen/Traditional-Simplified folding. No universal accuracy threshold or adoption criterion approved. Short anchors do not measure page completeness/CER. Screenshot-only anchors are chosen to avoid credit from native prose.',profiles={'native':{'do_ocr':False,'force_full_page_ocr':False},'mixed':{'do_ocr':True,'force_full_page_ocr':False},'scanned':{'do_ocr':True,'force_full_page_ocr':True}},table_observation='Sources 02 pages1-2 visually have a three-column hearing table, continuing across pages. Inspect table detection, content in cells, and ordering; not full table ground truth.',faulty_layer='No confirmed real faulty-layer fixture; 05 is raster-only historical vertical text, not faulty-layer. Original synthetic controlled regression remains separate.',crop_regions=[{'source_id':i,'page':n,'bbox_points':b,'anchors':a} for i,n,b,a in [('03',3,[63,244,510,570],['我的專區','最新公告']),('03',4,[95,223,536,507],['儲存','機關代碼']),('04',6,[36,108,559,473],['實習檢核','媒合評估','專案緣起','最新消息']),('04',7,[36,40,559,374],['使用者登入','忘記密碼']),('04',7,[185,414,410,530],['查詢資料使用注意說明','確認同意'])]],crop_coordinates='top-left PDF points, visually selected from 1.5x page renders. Bounded independent crop recognition at 3x scale; native text has not been used to set expected excerpts.')
(root/'plan.json').write_text(json.dumps(plan,ensure_ascii=False,indent=2)); print(hashlib.sha256((root/'plan.json').read_bytes()).hexdigest())
