from pathlib import Path
source = Path(__file__).with_name("qualify_cold.py").read_text()
old = "enumerate(('07', '08', 'native'))"
if source.count(old) != 1: raise RuntimeError("process-cold qualification sequence seam changed")
source = source.replace(old, "enumerate(('native', '07', '08'))")
exec(compile(source, __file__, "exec"), globals())
