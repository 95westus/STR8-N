"""Bind beta17 installed hardware evidence; raw images remain owner-local."""
import argparse,hashlib,json
from pathlib import Path
from prepare_v2_storage_upgrade import records
ROOT=Path(__file__).resolve().parents[1]
read=lambda p:json.loads(p.read_text())
sha=lambda b:hashlib.sha256(b).hexdigest()

def main():
    p=argparse.ArgumentParser();p.add_argument('--root',required=True,type=Path);a=p.parse_args();results=[]
    for board in ('2512','2205','2609'):
        root=a.root/board;plan=read(root/'upgrade/plan.json');model=read(root/'upgrade/model-check.json');install=read(root/'upgrade/install/reset-pending.json');check=read(root/'installed-check/report.json')
        assert model['passed'] and model['stale_preimage_refused'] and model['corrupt_payload_refused'] and install['device_sectors_verified'] and check['passed']
        assert check['installed_hashes']==plan['expected_hashes'] and not check['clock_set'] and not check['trim_changed']
        images=[]
        for bank in range(4):
            b=(root/f'installed-check/b{bank}.bin').read_bytes();assert b==(root/f'upgrade/expected-b{bank}.bin').read_bytes() and sha(b)==plan['expected_hashes'][bank];images.append(b)
        assert images[0]==(root/'prior/b0.bin').read_bytes() and images[3][0x7000:]==(root/'prior/b3.bin').read_bytes()[0x7000:]
        assert images[3][0x1C00:0x2000]==(root/'prior/b3.bin').read_bytes()[0x1C00:0x2000]
        assert not [r for r in records(images[2]) if r[1] in ('DEMO','DEMO2')]
        row=dict(board=board,port=check['port'] if 'port' in check else {'2512':'COM4','2205':'COM3','2609':'COM8'}[board],passed=True,edu=plan['edu_mode'],ram_top='66FF' if board=='2512' else '64FF',flash_hashes=plan['expected_hashes'],checks=check['checks'])
        if board!='2512':
            before=(root/'sram-prior/array-0.bin').read_bytes();after=(root/'sram-final/array-0.bin').read_bytes();assert len(before)==131072 and before==after and read(root/'sram-final/report.json')['passed']
            row['sram_sha256']=sha(after);row['sram_preserved']=True
        if board=='2609':
            via=read(root/'via-final/report.json');setup=read(root/'via-final-setup/report.json')
            assert via['IFR']&0x18 and not via['IER']&0x18 and setup['port_read_acknowledged'] and not setup['IFR_after']&0x18
            row.update(spi_startup_limitation='Disabled VIA CB flags after RESET; verified idle-port acknowledgment needed',unattended_spi_startup_qualified=False)
        results.append(row)
    report=dict(passed=True,version='2.0b17',boards=results,work='1.2',sram='1.2',maint='1.8',edu='1.2',clock='1.5',demos_installed=False,clock_set=False,trim_changed=False,board_backups_local=True)
    (a.root/'hardware-acceptance.json').write_text(json.dumps(report,indent=2)+'\n')
    print('PASS installed beta17 on all boards, exact flash and retained SRAM/UTC/trim/EEPROM/EUI; no DEMO/DEMO2')

if __name__=='__main__':main()
