"""Prepare two review-only MON A scopes from verified captures; no port/build."""
import json
import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];REPO=ROOT/'release/str8nf-v0.2.0'
sys.path[:0]=[str(REPO/'migration-host'),str(REPO/'tools')]
import nf_migrate as m
from journal_rotation_plan import reserve
from native_journal_room import require_zero_erase_room


def prepare():
    cap=ROOT/'output/qualification/2609-AP02-trial-20261030-r1'
    banks=[(cap/f'final-pass1-B{n}.bin').read_bytes() for n in range(4)]
    marker=json.loads((ROOT/'output/qualification/device-operations/2609.json').read_text())
    assert list(map(m.sha,banks))==[marker['current_physical_bank_sha256'][f'B{n}'] for n in range(4)]
    for n,b in enumerate(banks):assert b==(cap/f'final-pass2-B{n}.bin').read_bytes()
    source=REPO/'monitors/candidates/g00000008-r2'
    manifest=json.loads((source/'manifest.json').read_text())
    candidate=(source/'STR8N-MON-0.1.0-dev-g00000008-A.bin').read_bytes()
    paired=(source/'STR8N-MON-0.1.0-dev-g00000008-B.bin').read_bytes()
    assert m.sha(paired)==m.sha(banks[3][0x3000:0x4000])==manifest['artifacts']['STR8N-MON-0.1.0-dev-g00000008-B.bin']['sha256']
    assert len(candidate)==4096 and m.sha(candidate)==manifest['artifacts']['STR8N-MON-0.1.0-dev-g00000008-A.bin']['sha256']
    assert candidate[:4]==b'MI\x01\xa0' and candidate[8:12]==(8).to_bytes(4,'little') and candidate[20:24]==b'PR05'
    old=m.classify_journal(banks[3]);assert old['sequence']==1033 and old['valid_records']==19 and old['default']=='S'
    out=ROOT/'output/qualification/2609-MON-A-g8-scope-20261030-r1'
    assert not out.exists();out.mkdir();(out/'.gitignore').write_text('*\n')
    original=banks[3][0x2000:0x3000]
    assert original[20:24]==b'PR04' and original[8:12]==(0x8000000f).to_bytes(4,'little')
    (out/'original-MON-A-PR04-4096.bin').write_bytes(original)
    (out/'candidate-MON-A-PR05-g8-4096.bin').write_bytes(candidate)
    summary={}
    for mode,total in [('install-and-keep',1),('test-and-restore',2)]:
        dest=out/mode;dest.mkdir();require_zero_erase_room(banks[3],total)
        state=list(banks);operations=[]
        for index,target in enumerate([candidate] if total==1 else [candidate,original]):
            before=list(map(m.sha,state));bank3,journal=reserve(state[3],26)
            assert journal['journal_sector_erases']==[]
            changed=bytearray(bank3);changed[0x2000:0x3000]=target;state[3]=bytes(changed)
            label='installed' if index==0 else 'restored'
            for n,body in enumerate(state):(dest/f'{label}-expected-B{n}.bin').write_bytes(body)
            operations.append(dict(label=label,bank=3,address='A000',image_sha256=m.sha(target),journal=journal,
                                   before_bank_sha256=before,after_bank_sha256=list(map(m.sha,state))))
        final=m.classify_journal(state[3])
        assert final['counts']==[v+total if n==26 else v for n,v in enumerate(old['counts'])]
        for off in range(0x4000,0x6000,256):
            if m.valid_snapshot(banks[3][off:off+256]):assert state[3][off:off+256]==banks[3][off:off+256]
        assert state[:3]==banks[:3] and state[3][:0x2000]==banks[3][:0x2000]
        assert state[3][0x3000:0x4000]==banks[3][0x3000:0x4000] and state[3][0x6000:]==banks[3][0x6000:]
        for k in ('default','enabled_mask','entries','unknown_mask'):assert final[k]==old[k]
        plan=dict(schema=1,status='REVIEW_ONLY_NOT_AUTHORIZED',mode=mode,board='2609',port='COM8',usb_serial='A10MPQXCA',CPU='65C816 emulation',
            source_capture=str(cap),source_bank_sha256=list(map(m.sha,banks)),
            old_MON_A=dict(generation='8000000F',contract='PR04',sha256=m.sha(original)),
            candidate_MON_A=dict(generation='00000008',contract='PR05',sha256=m.sha(candidate),source=str(source)),
            source_MON_B_matches_same_build=True,source_MON_B_sha256=m.sha(paired),target='B3:A000',total_sector_erases=total,
            F_writes=0,C_D_erases=0,B_E_or_tool_writes=0,all_19_original_records_retained=True,operations=operations,
            final_bank_sha256=list(map(m.sha,state)),A_count_before=old['counts'][26],A_count_after=final['counts'][26],
            final_journal=final,default_S_preserved=True,mask_00_preserved=True,all_other_boot_and_count_fields_preserved=True,
            SRAM_data_writes=0,WORKSPACE_writes=0,RTC_SET=0,trim_writes=0,PF_ACK=0,power_cuts=0,firmware_builds=0,CPU_simulations=0,
            original_A_archived_on_host=True,original_A_retained_on_chip_at_finish=(total==2),
            latest_RAM_reference=marker['RTC_RAM_reference'],fresh_native_owner_double_escrow_required=True,
            owner_RAM_restore_must_use_fresh_trial_escrow=True,physical_RESET_request_requires_armed_receiver=True,
            RTC_admission_update_required=True,RTC_instrument_and_profile_unchanged=True,final_context='REC>',
            other_boards_excluded=True,push=False,published_downloads_changed=False)
        (dest/'plan.json').write_text(json.dumps(plan,indent=2)+'\n')
        summary[mode]=dict(plan_sha256=m.sha((dest/'plan.json').read_bytes()),erases=total,
            A_count_before=old['counts'][26],A_count_after=final['counts'][26],
            appends=[j for op in operations for j in op['journal']['journal_appends']],default='S',old_records_retained=19)
    (out/'review-summary.json').write_text(json.dumps(summary,indent=2)+'\n')
    print(json.dumps(dict(out=str(out),plans=summary),indent=2))


if __name__=='__main__':prepare()
