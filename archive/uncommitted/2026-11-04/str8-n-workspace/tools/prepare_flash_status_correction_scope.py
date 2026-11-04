"""Prepare the minimum additional2512 correction scope; never open a port."""
import json,sys
from pathlib import Path
import install_2512_native_utilities as d
t=d.t
sys.path.insert(0,str(t.REPO/'tools'))
from journal_rotation_plan import reserve
from status_extents import assert_preserved


def run():
    q=t.ROOT/'output/qualification';trial=q/'2512-flash-status-correction-RAM-20261101-r1'
    r=json.loads((trial/'report.json').read_text());assert r['passed'] and r['owner_RAM_restored'] and r['owner_ZP_restored'] and r['port_released']
    mfpath=t.ROOT/'BUILD/flash-status-correction-r4/manifest.json';mf=json.loads(mfpath.read_text())
    def artifact(n):
        b=(mfpath.parent/n).read_bytes();assert t.sha(b)==mf['artifacts'][n]['sha256'];return b
    before={b:(trial/f'B{b}-before.bin').read_bytes() for b in range(4)}
    after={b:bytearray(v) for b,v in before.items()}
    maint=artifact('BANK-MAINT-corrected.bin');flash=artifact('FLASH-corrected.bin')
    after[1][:0x3000]=maint;after[2][0x6000:]=flash
    original2=(q/'FLASH-transfer-scope-20261101-r1/B2-original.bin').read_bytes()
    assert_preserved(original2,bytes(after[2]))
    assert after[1][:0x2000]==before[1][:0x2000] and after[1][0x3000:]==before[1][0x3000:]
    assert after[2][:0x6000]==before[2][:0x6000]
    folder=q/'FLASH-status-correction-scope-20261101-r1';folder.mkdir(exist_ok=False);(folder/'.gitignore').write_text('*\n')
    state=before[3];targets=[];operations=[]
    for bank,page in ((1,0xA0),(2,0xE0),(2,0xF0)):
        off=(page-0x80)*256;data=bytes(after[bank][off:off+4096]);old=before[bank][off:off+4096];assert old!=data
        name=f'B{bank}-{page:02X}-target.bin';(folder/name).write_bytes(data)
        (folder/f'B{bank}-{page:02X}-original.bin').write_bytes(old)
        state,op=reserve(state,bank*8+(page-0x80)//16);assert not op['journal_sector_erases'];operations.append(op)
        targets.append(dict(bank=bank,page=page,address=f'B{bank}:{page:02X}00',file=name,sha256=t.sha(data),before_sha256=t.sha(old)))
    after[3]=bytearray(state);prior=t.classify_journal(before[3]);end=t.classify_journal(state)
    assert prior['sequence']==1130 and end['sequence']==1133 and prior['valid_records']==21 and end['valid_records']==24
    for off in range(0x4000,0x6000,256):
        if before[3][off:off+256]!=b'\xff'*256:assert state[off:off+256]==before[3][off:off+256]
    assert state[:0x4000]==before[3][:0x4000] and state[0x6000:]==before[3][0x6000:]
    for bank in range(4):
        (folder/f'B{bank}-original.bin').write_bytes(before[bank]);(folder/f'B{bank}-target.bin').write_bytes(after[bank])
    plan=dict(status='REVIEW_READY_NOT_APPROVED',board='2512',total_erases=3,journal_appends=3,journal_sector_erases=0,F_writes=0,
        targets=targets,operations=operations,counts_before=prior['counts'],counts_after=end['counts'],
        sequence_before=1130,sequence_after=1133,old_records_retained=21,records_after=24,
        before_bank_sha256={f'B{b}':t.sha(v) for b,v in before.items()},after_bank_sha256={f'B{b}':t.sha(v) for b,v in after.items()},
        candidate_manifest=str(mfpath),candidate_manifest_sha256=t.sha(mfpath.read_bytes()),
        RAM_receipt=str(trial/'report.json'),RAM_receipt_sha256=t.sha((trial/'report.json').read_bytes()),
        correction=['Restore exact1450-byte STATUS allocation FA50-FFF9','Keep FLASH code below FA50',
            'Dense library fragments in existing BANK MAINT padding','AUTO reloads SP only; WB AREA remains intact'],
        preserved=['F/MON A/B','all current journal records/settings','entire B0 and all other images','RTC time/trim/history',
                   'SPI SRAM/WORKSPACE','fresh owner RAM/ZP'],
        tests=['Rich VERSION and TIME/trim','R FLASH loaded fragment CRC and I cancellation','explicit wide Store NO',
               'AREA AUTO confirmation/NO from actual board-loaded gate','S19 Ctrl-C','TABLE/R MAINT/R CLOCK and PROGRAM NO'],
        excluded=['2609','2205','2604','power cuts','F writes','C/D erases','extra positive flash/SPI writes','published downloads'])
    t.save(folder/'plan.json',plan)
    print('REVIEW READY: three erases; C500-C700/seq1131-1133; all21 old rows retained; F/MON/B0 unchanged')
    print('Counts C/D/E/F',end['counts'][28:32])


if __name__=='__main__':run()
