import json
from pathlib import Path
import upgrade_v2_fleet as f
from rtc_prompt_sync import establish_b3
root=Path('output/qualification/beta30-2026-10-16/2512');root.mkdir(parents=True,exist_ok=True)
with f.serial_lease('beta30-2512-backup'),(root/'inventory-serial.jsonl').open('a') as log:
 l=f.Link(f.port('2512'),log)
 try:
  establish_b3(l);active=l.dump(0x7D30,0x7D30)[0]
  state=dict(board='2512',port=f.port('2512'),active_page=active,inactive_page=active^0x10,monitor_config=l.command('C').decode(errors='replace'),service_descriptor=l.dump(0x7D04,0x7D0B).hex(),version=l.command('VERSION').decode(errors='replace'))
  assert active==0xB0 and '2.0b29' in state['version'],state
  (root/'initial-state.json').write_text(json.dumps(state,indent=2)+'\n')
 finally:l.serial.close()
 f.call(f.backup,['--board','2512','--port',f.port('2512'),'--out',str(root/'prior-verified')])
retained=root/'retained';retained.mkdir()
campaign=f.u.read(f.u.ROOT/'output/qualification/active-rtc-campaign.json')
with f.serial_lease('beta30-2512-reference'):
 assert bytes.fromhex(state['service_descriptor'])[3]!=0,'EDU mode changed; inspect before continuing'
 f.call(f.array,['--root',str(retained),'--board','2512','--port',f.port('2512'),'--stage','prior'])
 f.call(f.devices,['--root',str(retained),'--board','2512','--port',f.port('2512'),'--stage','before','--baseline-index',campaign['baseline_index'],'--clock-source','sram','--clock-name','CLK','--clock19-display-transition'])
print('PASS fresh flash and retained references',flush=True)
