"""Exact b10 -> b11 admission; preservation services inherit qualified b10."""
from pathlib import Path
import b10_admission as frozen

source=frozen.source
start=source.index('    old_sy, sy =')
stop=source.index('    old_F = (source/',start)
source=source[:start]+"    sy=r.read(build/'symbols.json')\n"+source[stop:]
for before,after in (
    ('import b09_admission as prior','import b10_admission as prior'),
    ('import deployment_b10 as planning','import deployment_b11 as planning'),
    ('import deployment_b10_model as model','import deployment_b11_model as model'),
    ('BUILD/pr04-b09-usb2','BUILD/pr04-b10-wait'),
    ('tmp/pr04-b09-2512-native-plan','tmp/pr04-b10-2512-native-plan'),
    ("adapter_file=HERE/'board_b09_2512.py'","adapter_file=HERE/'board_b10_2512.py'"),
    ('0x8000000A','0x8000000B'),('2.0proto b10','2.0proto b11'),
    ('b10-qualification.json','b11-qualification.json'),('b10-selection-tests.json','b11-selection-tests.json'),
    ('b10-wait-tests.json','b11-wait-tests.json'),('b10-usb-wait-','b11-usb-wait-'),
    ('test_b10.py','test_b11.py'),('test_b10_wait.py','test_b11_wait.py'),('test_b10_usb_wait.py','test_b11_usb_wait.py'),
    ('from qualify_b10 import static_equivalence','from qualify_b11 import static_equivalence'),
    ('== [8,18,19,2510,2511]','== [8,18,19,2511]'),
    ("before[2510:2512] == b'09' and after[2510:2512] == b'10'","before[2510:2512] == b'10' and after[2510:2512] == b'11'"),
    ('source-b09','source-b10'),('target-b10','target-b11'),
    ('test_board_b10_2512.py','test_board_b11_2512.py'),
    ('b10-probe-host-tests.json','b11-probe-host-tests.json'),('test_b10_probe.py','test_b11_probe.py'),
    ("'deployment_b10.py','deployment_b10_model.py','b10_admission.py','qualify_b10.py','build_b10.py'",
     "'deployment_b11.py','deployment_b11_model.py','b11_admission.py','qualify_b11.py','build_b11.py'"),
    ("'firmware.bin','b11-wait-tests.json'}","'firmware.bin','b11-wait-tests.json','b11-help-tests.json'}"),
):
    assert before in source,before
    source=source.replace(before,after)
anchor="    probe=r.read(build/'b11-probe-host-tests.json')"
addition="""    help_proof=r.read(build/'b11-help-tests.json')
    r.require(help_proof['passed'] and help_proof['checks']==24 and help_proof['failures']==0
              and help_proof['checker_sha256']==r.sha((HERE/'test_b11_help.py').read_bytes())
              and help_proof['F_sha256']==r.sha(new_F), 'Help/raw/absent-image CPU proof differs')
    hp=r.read(build/'b11-help-probe-host-tests.json')
    r.require(hp['passed'] and hp['checks']==4 and all(row['passed'] for row in hp['cases'])
              and hp['adapter_sha256']==r.sha(Path(adapter_file).read_bytes())
              and hp['checker_sha256']==r.sha((HERE/'test_b11_help_probe.py').read_bytes()), 'Live help probe proof differs')
"""
assert anchor in source;source=source.replace(anchor,addition+anchor)
exec(compile(source,str(Path(frozen.__file__)),'exec'),globals())
