"""Bind installed board evidence without tracking owner-local backup contents."""
import argparse,hashlib,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];BUILD=ROOT/'BUILD/v2-spi-resident'
read=lambda p:json.loads(p.read_text())
sha=lambda b:hashlib.sha256(b).hexdigest()

def main():
    p=argparse.ArgumentParser();p.add_argument('--root',required=True,type=Path);p.add_argument('--reset-capture',type=Path);a=p.parse_args()
    candidate=read(BUILD/'build.json');ws=read(BUILD/'workspace/candidate-check.json');assert ws['passed']
    resolution_index=a.root/'reset-resolution-index.json'
    if not a.reset_capture and resolution_index.exists():a.reset_capture=Path(read(resolution_index)['capture_root'])
    boards=[]
    for board in ('2512','2205','2609'):
        root=a.root/board;archive=read(root/'prior/manifest.json');plan=read(root/'upgrade/plan.json')
        assert archive['repeat_verified'] and plan['prior_hashes']==[b['sha256'] for b in archive['banks']]
        for b in range(4):assert (root/f'prior/b{b}.bin').read_bytes()==(root/f'prior/b{b}-repeat.bin').read_bytes()
        assert read(root/'upgrade/model-check.json')['passed'] and read(root/'upgrade/install/reset-pending.json')['device_sectors_verified']
        resident=read(root/'resident-check/report.json');utilities=read(root/'utilities/report.json');reg=read(root/'regression/report.json');final=read(root/'final-check/report.json')
        assert all(r['passed'] for r in (resident,utilities,reg,final,read(root/'storage-exercise/report.json')))
        assert utilities['workspace_sha256']==ws['workspace_sha256'] and utilities['store_sha256']==ws['store_sha256']
        assert reg['workspace_latch_preserved'] and final['software_cold_reset_latch_cleared'] and final['raw_write_denied']
        hashes=[]
        for b in range(4):
            image=(root/f'final-check/b{b}.bin').read_bytes();assert len(image)==32768;hashes.append(sha(image))
        assert hashes==final['final_hashes']
        for b in (0,1):assert (root/f'final-check/b{b}.bin').read_bytes()==(root/f'prior/b{b}.bin').read_bytes()
        before=(root/'prior/b3.bin').read_bytes();after=(root/'final-check/b3.bin').read_bytes()
        assert after==(root/'upgrade/expected-b3.bin').read_bytes() and after[3072+4096:8192]==before[3072+4096:8192] and after[0x7000:]==before[0x7000:]
        assert sha(after[:4096])==candidate['artifacts']['str8n-rtc-component-8000-8fff.bin']
        row=dict(board=board,port=final.get('port',{'2512':'COM4','2205':'COM3','2609':'COM8'}[board]),
                 passed_functional=True,final_flash_hashes=hashes,reset_button_workspace_verified=final['physical_reset_workspace_verified'],
                 software_cold_reset_verified=True,power_cycle_workspace_verified=final['power_cycle_workspace_verified'])
        if board!='2512':
            original=(root/'spi-archive/array.bin').read_bytes();assert original==(root/'spi-archive/array-repeat.bin').read_bytes()
            restored=(root/'storage-restore/array-final.bin').read_bytes();assert original==restored and len(restored)==131072
            assert read(root/'storage-power-check/report.json')['passed']
            assert final['control_trim']=='8000' and final['boot_logged_and_acked'] and final['other_outage_slots_preserved']
            row.update(sram_sha256=sha(restored),sram_restored_exactly=True,new_outage=final['new_outage'],control_trim='8000')
        boards.append(row)
    resolved=False
    resolution={}
    if a.reset_capture:
        assert a.reset_capture.resolve().is_relative_to((ROOT/'output/qualification').resolve())
        capture=read(a.reset_capture/'report.json');index=read(a.reset_capture/'closeout-index.json')
        closeout=a.reset_capture/index['stage'];final=read(closeout/'report.json')
        assert capture['board']=='2609' and all(capture[k] for k in ('passed','physical_cold_boot_captured','old_handle_rejected','saved_image_retained','sram_restored','cleanup_latch_cleared'))
        assert capture['latch_after']=='0100' and final['passed'] and final['latch_final']=='0100' and final['control_trim']=='8000'
        first=(a.reset_capture/'sram-first8k-0.bin').read_bytes()
        assert first==(a.reset_capture/'sram-first8k-1.bin').read_bytes()==(a.reset_capture/'sram-first8k-restored.bin').read_bytes()
        original=(a.root/'2609/spi-archive/array.bin').read_bytes()
        assert first==original[:8192] and (closeout/'sram-final.bin').read_bytes()==original
        row=next(b for b in boards if b['board']=='2609')
        assert final['final_flash_hashes']==row['final_flash_hashes']
        row['reset_button_workspace_verified']=True;row['correct_button']='main SXB S2/RESB'
        resolved=True;resolution=dict(capture_root=str(a.reset_capture),capture_sha256=sha((a.reset_capture/'report.json').read_bytes()),
                                     closeout_sha256=sha((closeout/'report.json').read_bytes()),user_report='Earlier presses used the wrong button')
        resolution_index.write_text(json.dumps(dict(capture_root=str(a.reset_capture.resolve())),indent=2)+'\n')
    result=dict(passed_functional=True,version='2.0b14',generation=23,clock='1.5',workspace='1.0',sram_utility='1.1',boards=boards,
        workspace_sha256=ws['workspace_sha256'],store_sha256=ws['store_sha256'],ram_top='64FF',permanent_service_ram='6500-66FF',
        source_backups_tracked=False,full_hardware_acceptance=resolved,open_items=[] if resolved else ['2609 RESET-button cold-path/workspace-latch observation'],reset_resolution=resolution,
        sram_final_state='original arrays restored; no automatic layout initialization')
    (a.root/'acceptance.json').write_text(json.dumps(result,indent=2)+'\n')
    print('PASS installed functional qualification and exact preservation; '+('correct 2609 S2 RESET verified, hardware acceptance complete' if resolved else '2609 RESET-button acceptance remains open'))

if __name__=='__main__':main()
