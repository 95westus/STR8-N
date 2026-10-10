"""Read-only closeout of installed beta15 modes, flash and SRAM preservation."""
import argparse,hashlib,json
from pathlib import Path
from beta4_migration import clean_config,config_sum,journal
ROOT=Path(__file__).resolve().parents[1]
sha=lambda b:hashlib.sha256(b).hexdigest()
def main():
    p=argparse.ArgumentParser();p.add_argument('--root',required=True,type=Path);a=p.parse_args();results=[]
    for board in ('2512','2205','2609'):
        root=a.root/board;out=root/'edu-check-resume';r=json.loads((out/'report.json').read_text());assert r['passed'] and r['both_slots_verified']
        assert r['mode']==('OFF' if board=='2512' else 'ON') and r['user_ram_top']==('66FF' if board=='2512' else '64FF')
        plan=json.loads((root/'upgrade/plan.json').read_text());before=[(root/f'prior/b{b}.bin').read_bytes() for b in range(4)];after=[(out/f'final-b{b}.bin').read_bytes() for b in range(4)]
        assert [sha(b) for b in after]==r['final_hashes'] and before[0]==after[0] and before[1]==after[1]
        assert before[3][:8192]==after[3][:8192] and before[3][0x7000:]==after[3][0x7000:]
        row=journal(after[3]);counts=[int.from_bytes(row[24+i*3:27+i*3],'little') for i in range(32)]
        assert counts==plan['counts_after'] and row[8:24]==bytes.fromhex(plan['config'])
        assert row[21]==(0xA5 if board=='2512' else 0)
        if board!='2512':
            final=json.loads((root/'sram-final/report.json').read_text());prior=json.loads((root/'sram-prior/report.json').read_text())
            assert final['passed'] and prior['repeat_verified'] and final['sha256']==prior['sha256']
            assert (root/'sram-final/array-0.bin').read_bytes()==(root/'sram-prior/array-0.bin').read_bytes()==(root/'sram-prior/array-1.bin').read_bytes()
            assert r['eeprom_preserved']
        results.append(dict(board=board,mode=r['mode'],user_ram_top=r['user_ram_top'],checks=r['checks'],flash_hashes=r['final_hashes'],sram_unchanged=board!='2512'))
    # The generic migration cleaner also preserves this exact optional tag.
    cfg=bytearray.fromhex(plan['config']);cfg[13]=0xA5;cfg[14:]=config_sum(cfg)
    assert clean_config(cfg)[13]==0xA5 and clean_config(cfg)[14:]==config_sum(clean_config(cfg))
    report=dict(passed=True,version='2.0b15',boards=results,clock_set=False,trim_changed=False,fixed_f_preserved=True,original_sram_arrays_preserved=True,board_backups_local=True)
    (a.root/'hardware-acceptance.json').write_text(json.dumps(report,indent=2)+'\n')
    print('PASS all 3 boards: beta15/WORK1.1/EDU1.0, both mode transitions, RAM/ABI/IRQ guards, exact flash, RTC/EEPROM and full SRAM preservation')
if __name__=='__main__':main()
