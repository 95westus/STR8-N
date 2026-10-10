"""Bind SPI prototype models, complete SRAM archives and preserved board state."""
import argparse,hashlib,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];BUILD=ROOT/'BUILD/v2-spi-phase2'
read=lambda p:json.loads(p.read_text())
sha=lambda b:hashlib.sha256(b).hexdigest()

def main():
    p=argparse.ArgumentParser();p.add_argument('--root',required=True,type=Path);a=p.parse_args()
    meta=read(BUILD/'build.json');model=read(BUILD/'test-results.json')
    assert model['passed'] and model['sha256']==meta['sha256']==sha((BUILD/'spi-prototype.bin').read_bytes())
    assert model['client_sha256']==meta['client']['sha256']==sha((BUILD/'spi-client.bin').read_bytes())
    assert meta['size_groups']['main']<=640 and meta['size_groups']['shared_helpers']<=237 and model['max_stack_bytes']<=16
    result=dict(passed=True,phase=2,prototype_bytes=meta['bytes'],main_bytes=meta['size_groups']['main'],shared_helper_bytes=meta['size_groups']['shared_helpers'],
                prototype_sha256=meta['sha256'],client_sha256=meta['client']['sha256'],boards=[],flash_changed=False,crypto_accessed=False,resident_spi_installed=False)
    for board in ('2512','2205','2609'):
        root=a.root/board;stages=read(root/'spi-stages.json');prior=read(root/'prior/manifest.json');assert prior['repeat_verified']
        reports={}
        for stage in ('archive','exercise','final'):
            folder=root/stages.get(stage,'spi-'+stage);report=read(folder/'report.json');assert report['passed']
            reports[stage]=report
            tx=b''.join(bytes.fromhex(json.loads(line)['hex']) for line in (folder/'serial.jsonl').read_text().splitlines() if json.loads(line)['direction']=='TX')
            for image in ('spi-prototype.s19','spi-client.s19'):
                assert all(line+b'\r\n' in tx for line in (BUILD/image).read_bytes().splitlines() if line.startswith(b'S1')),f'{board} {stage} loaded image mismatch'
            assert not report['flash_written'] and not report['rtc_set'] and not report['trim_changed'] and not report['crypto_accessed']
            assert all(c['before_pcr']==c['after_pcr'] and c['ddr_before']==c['ddr_after'] for c in report['calls'])
        final=root/stages['final']
        for b in range(4):
            before=(root/f'prior/b{b}.bin').read_bytes();assert before==(root/f'prior/b{b}-repeat.bin').read_bytes()==(final/f'b{b}.bin').read_bytes()
            assert sha(before)==prior['banks'][b]['sha256']==reports['final']['final_flash_hashes'][b]
        state=read(root/'rtc-eeprom-final/report.json');assert state['passed'] and not state['clock_set'] and not state['trim_changed']
        if board!='2512':
            archive=root/stages.get('archive','spi-archive');data=(archive/'array.bin').read_bytes()
            assert len(data)==131072 and data==(archive/'array-repeat.bin').read_bytes()==(final/'array-final.bin').read_bytes()
            assert sha(data)==reports['archive']['array_sha256']==reports['final']['array_sha256']
            assert reports['final']['mode_preserved'] and reports['archive']['mode']==0x40
            ee=(root/'rtc-eeprom-final/inventory-0.bin').read_bytes();assert ee==(root/'rtc-eeprom-final/inventory-1.bin').read_bytes()
            assert ee[:128]==(root/'eeprom-prior/array.bin').read_bytes() and ee[0x80:0x89]==(root/'eeprom-prior/status-factory.bin').read_bytes()
        else:assert reports['archive']['absent_sram']
        result['boards'].append(dict(board=board,passed=True,array_sha256=reports['archive'].get('array_sha256'),mode=reports['archive']['mode'],checks=reports['exercise']['checks']))
        print('PASS',board,'matched loaded image, SRAM/archive/final equality, flash/EEPROM/trim and caller state')
    setup=read(a.root/'2609/via-ack-setup/report.json');assert setup['IFR']==0x1A and setup['IER']==0x80 and setup['IFR_after']==2 and setup['port_read_acknowledged']
    result['qualification_setup']={'2609_disabled_cb_flags_archived_and_acknowledged':True}
    baseline=read(ROOT/'output/qualification/rtc-utc-sync-2026-10-06/baseline-index.json')
    for b in baseline['boards']:
        assert sha(Path(b['sync_report']).read_bytes())==b['sync_sha256'] and sha(Path(b['baseline_report']).read_bytes())==b['baseline_sha256']
    result['original_drift_baselines_preserved']=True
    (a.root/'acceptance.json').write_text(json.dumps(result,indent=2)+'\n')

if __name__=='__main__':main()
