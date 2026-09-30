from pathlib import Path
source = Path(__file__).with_name("cold_window.py").read_text()
old = "SEQUENCE = ('07', '08', 'native')"
if source.count(old) != 1: raise RuntimeError("process-cold sequence seam changed")
source = source.replace(old, "SEQUENCE = ('08', 'native', '07')")
source = source.replace("process-cold-YOLO07-AIMA08-native", 'process-cold-AIMA08-native-YOLO07')
exec(compile(source, __file__, "exec"), globals())
