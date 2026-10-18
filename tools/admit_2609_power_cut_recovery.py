"""Admit actual return bytes and expected automatic PF journal changes."""
import json,hashlib,binascii
from pathlib import Path
import plan_bf1_2609_route as route
from atomic_json import publish
ROOT=Path(__file__).resolve().parents[1];Q=ROOT/'output/qualification';G=Q/'bf1-2609-physical-gate-2026-10-17-r1'
read=lambda p:json.loads(p.read_text());sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()

def main():
    cut=G/'power-cut-1';capture=cut/'return-capture';output=cut/'recovery-admission.json';assert not output.exists()
    receipt=read(capture/'report.json');assert receipt['passed'] and receipt['application_ram_restored'] and receipt['ports_released']
    assert receipt['flash_repeat_verified'] and receipt['eeprom_repeat_verified'] and receipt['sram_repeat_verified']
    assert not read(capture/'restore-needed.json')['needed'] and receipt['active_page']==0xa0
    for name,info in receipt['files'].items():assert sha(capture/name)==info['sha256']
    mode=receipt['cpu_mode_after_capture'];assert mode['emulation_mode_before_probe'] and mode['dbr']==mode['pbr']==mode['direct_page']==0
    assert b'Running: MONITOR A, gen 00000028' in (capture/'version.txt').read_bytes()
    proof_path=G/'stable-boundary-proof-r2/report.json';proof=read(proof_path);assert proof['passed']
    banks=[(capture/f'b{i}.bin').read_bytes() for i in range(4)];assert route.p.bank_hashes(banks)==proof['expected_cut_hashes']
    original=G/'post-restoration-backup';source=[(original/f'b{i}.bin').read_bytes() for i in range(4)]
    info_path=G/'reinstall-route-r1/install-B-complete/plan.json';info=read(info_path)
    prefix_path=G/'stable-boundary-proof-r2/stable-first-transfer-cut/events.json';prefix=read(prefix_path)
    attempts=route.attest_recovery(banks,source,events=prefix,info=info,certificate=route.p.bank_hashes(banks))
    assert (capture/'sram.bin').read_bytes()==(original/'sram.bin').read_bytes()
    before=(original/'eeprom.bin').read_bytes();after=(capture/'eeprom.bin').read_bytes();assert after[128:]==before[128:]
    changes=[i for i,(x,y) in enumerate(zip(before,after)) if x!=y];event=None
    if changes:
        slots={i//32 for i in changes};assert max(changes)<128 and len(slots)==1,'Unexpected EEPROM modifications'
        slot=next(iter(slots));row=after[slot*32:(slot+1)*32]
        assert row[:3]==b'PF\x01' and row[3]==slot+1 and row[4:8]==b'JR\x20\xa5'
        assert int.from_bytes(row[28:30],'little')==binascii.crc_hqx(row[:28],0xffff) and row[30:32]==b'\0\xa5'
        old_sequences=[]
        for i in range(4):
            old=before[i*32:(i+1)*32]
            if old[:3]==b'PF\x01' and int.from_bytes(old[28:30],'little')==binascii.crc_hqx(old[:28],0xffff):old_sequences.append(int.from_bytes(old[8:12],'little'))
        sequence=int.from_bytes(row[8:12],'little');assert old_sequences and sequence==max(old_sequences)+1
        event=dict(slot=slot,sequence=sequence,record_hex=row.hex(),raw_outage_hex=row[12:20].hex(),CRC_valid=True,committed=True,automatic_ack_verified=True)
    model_plan=G/'stable-boundary-proof-r2/stable-boundary-recovery/plan.json';recovery=read(model_plan)
    assert recovery['source_sha256']==route.p.bank_hashes(banks)
    assert sha(G/'stable-boundary-proof-r2/stable-boundary-recovery/installer-model-only.s19')==recovery['installer_sha256']
    result=dict(passed=True,board='2609',actual_hardware_A40_fallback=True,actual_emulation_mode_verified=True,
                actual_interrupted_flash_matches_exact_model=True,source_hashes=route.p.bank_hashes(banks),
                modeled_prefix_events=len(prefix),replayed_erase_attempts=attempts,
                capture_report_sha256=sha(capture/'report.json'),boundary_report_sha256=sha(proof_path),
                EEPROM_expected_PF_event=event,EEPROM_factory_status_unchanged=True,full_SRAM_unchanged=True,
                expected_boot_PF_logging_only=bool(event),no_recovery_write_performed=True,
                recovery_plan=str(model_plan.resolve()),recovery_plan_sha256=sha(model_plan),
                expected_recovery_hashes=recovery['expected_sha256'],physical_power_interruption_recovery_completed=False,
                release_qualified=False,installation_permitted=False)
    publish(output,result);print(json.dumps(result,indent=2))
if __name__=='__main__':main()
