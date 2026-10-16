"""Fresh 2609 references before its backup-bound beta32 native-utility upgrade."""
import json
from pathlib import Path
import upgrade_v2_fleet as f
from rtc_prompt_sync import establish_b3

ROOT=Path('output/qualification/beta32-2026-10-16/2609')


def main():
    ROOT.mkdir(parents=True,exist_ok=True)
    assert not (ROOT/'initial-state.json').exists(), 'Existing capture requires explicit resume review'
    with f.serial_lease('beta32-2609-backup',priority=True),(ROOT/'inventory-serial.jsonl').open('x') as log:
        link=f.Link(f.port('2609'),log)
        try:
            establish_b3(link)
            state=dict(board='2609',port=f.port('2609'),active_page=link.dump(0x7D30,0x7D30)[0],
                       version=link.command('VERSION').decode(),config=link.command('C').decode(),
                       service_descriptor=link.dump(0x7D04,0x7D0B).hex())
            assert state['active_page']==0xB0 and '2.0b27' in state['version'],state
            (ROOT/'initial-state.json').write_text(json.dumps(state,indent=2)+'\n')
        finally:link.serial.close()
        f.call(f.backup,['--board','2609','--port',f.port('2609'),'--out',str(ROOT/'prior-verified')])
    retained=ROOT/'retained';retained.mkdir()
    campaign=f.u.read(f.u.ROOT/'output/qualification/active-rtc-campaign.json')
    with f.serial_lease('beta32-2609-retained-reference',priority=True):
        f.call(f.array,['--root',str(retained),'--board','2609','--port',f.port('2609'),'--stage','prior'])
        f.call(f.devices,['--root',str(retained),'--board','2609','--port',f.port('2609'),'--stage','before',
                          '--baseline-index',campaign['baseline_index'],'--clock-source','sram','--clock-name','CLK',
                          '--clock19-display-transition'])
    print('PASS fresh repeated flash/SRAM and RTC/EEPROM/history references for 2609',flush=True)


if __name__=='__main__':main()
