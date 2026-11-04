"""b10 receipt admission, inheriting byte-identical b09 preservation services."""
from pathlib import Path
import b09_admission as frozen

source=Path(frozen.__file__).read_text()
start=source.index("    b08 = ROOT/")
stop=source.index('    old_sy, sy =',start)
source=source[:start]+'''    from qualify_b10 import static_equivalence
    r.require(qualification['static_equivalence']==static_equivalence(build), 'Exact b09/b10 code equivalence changed')
    new_F=(build/'payload/f-offline-component.bin').read_bytes()
    wait=r.read(build/'b10-wait-tests.json')
    r.require(wait['passed'] and wait['checks']==32 and wait['failures']==0
              and all(row['passed'] for row in wait['cases'])
              and wait['checker_sha256']==r.sha((HERE/'test_b10_wait.py').read_bytes()), 'Receive wait/cancel proof changed')
'''+source[stop:]
line="    r.require(old_F[0x33e:0x540] == new_F[0x33e:0x540], 'Binary handlers changed')\n"
assert line in source;source=source.replace(line,'')
anchor="    host = r.read(build/'native-host-cpu-tests.json')"
assert source.count(anchor)==1
source=source.replace(anchor,'''    probe=r.read(build/'b10-probe-host-tests.json')
    r.require(probe['passed'] and not probe['hardware'] and not probe['serial_access']
              and probe['checks']==3 and all(row['passed'] for row in probe['cases'])
              and probe['adapter_sha256']==r.sha(Path(adapter_file).read_bytes())
              and probe['checker_sha256']==r.sha((HERE/'test_b10_probe.py').read_bytes()), 'Live probe host qualification changed')
'''+anchor)
for before,after in (
    ('import b07_admission as prior','import b09_admission as prior'),
    ('import deployment_b09 as planning','import deployment_b10 as planning'),
    ('import deployment_b09_model as model','import deployment_b10_model as model'),
    ('BUILD/pr04-b07-startup','BUILD/pr04-b09-usb2'),
    ('tmp/pr04-b07-2512-native-plan','tmp/pr04-b09-2512-native-plan'),
    ("adapter_file=HERE/'board_b07_2512.py'","adapter_file=HERE/'board_b09_2512.py'"),
    ('0x80000009','0x8000000A'),('2.0proto b09','2.0proto b10'),
    ('b09-qualification.json','b10-qualification.json'),('b09-selection-tests.json','b10-selection-tests.json'),
    ('b09-usb-wait-','b10-usb-wait-'),('test_b09.py','test_b10.py'),('test_b09_usb_wait.py','test_b10_usb_wait.py'),
    ("'prototype-report.json','firmware.bin'}","'prototype-report.json','firmware.bin','b10-wait-tests.json'}"),
    ("('BOOT_END','_END_CODE')","('BOOT_END','_END_CODE','RL_GOT','P_LONG_63','P_LONG_64','P_LONG_65')"),
    ('== [8,18,19,2511]','== [8,18,19,2510,2511]'),
    ("before[2511] == ord('7') and after[2511] == ord('9')","before[2510:2512] == b'09' and after[2510:2512] == b'10'"),
    ('source-b07','source-b09'),('target-b09','target-b10'),
    ('test_board_b09_2512.py','test_board_b10_2512.py'),
    ("'deployment_b09.py','deployment_b09_model.py','b09_admission.py'", "'deployment_b10.py','deployment_b10_model.py','b10_admission.py','qualify_b10.py','build_b10.py','test_b10_wait.py'"),
):
    assert before in source,before
    source=source.replace(before,after)
exec(compile(source,str(Path(frozen.__file__)),'exec'),globals())
