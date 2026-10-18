"""Require clean standalone VERSION replies after an interrupted early transcript."""
import json
from pathlib import Path
import upgrade_v2_fleet as f
from rtc_prompt_sync import establish_b3
root=Path('output/qualification/beta29-2026-10-15/2512')
with f.serial_lease('beta29-2512-version-recheck'),(root/'upgrade/version-recheck-serial.jsonl').open('x') as log:
 link=f.Link(f.port('2512'),log)
 try:
  establish_b3(link)
  for i in range(2):
   text=link.command('VERSION');(root/f'upgrade/version-recheck-{i}.txt').write_bytes(text)
   assert b'MONITOR A gen 00000028 VALID\r\n' in text and b'MONITOR B gen 00000029 VALID default\r\n' in text,text
   assert b'A/B/S,Enter' not in text and b'SSRAM:' not in text and text.count(b'STR8-N 2.0b29')==1,text
   assert link.dump(0x7D30,0x7D30)==b'\xB0'
   print('PASS standalone VERSION without restart',i+1,flush=True)
 finally:link.serial.close()
result=dict(passed=True,clean_standalone_version_queries=2,early_version_transcript_interrupted_by_restart=True,restart_cause='undetermined; not reproduced by subsequent BATCH VERSION or two standalone VERSION queries')
(root/'upgrade/version-recheck.json').write_text(json.dumps(result,indent=2)+'\n')
