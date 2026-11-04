"""Consolidate physical SRAM/WORK evidence; no hardware or firmware writes."""
import json,hashlib
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];Q=ROOT/'output/qualification'
sha=lambda b:hashlib.sha256(b).hexdigest()

def close():
    p=Q/'2512-SRAM-WORK-positive-RAM-20261101-r5';w=Q/'2512-SRAM-WORK-positive-RAM-20261101-r6'
    program=json.loads((p/'report.json').read_text());work=json.loads((w/'report.json').read_text())
    expected=[('WORK',7,0),('WORK',0,0),('WORK',1,0),('WORK',4,0),('WORK',3,0),
        ('WORK',3,0x4B),('WORK',3,0x44),('WORK',3,0x44),('WORK',2,0),('WORK',3,0x4B),
        ('WORK',5,0),('WORK',0,0),('WORK',1,0),('WORK',5,0x4A),('WORK',2,0),('WORK',5,0),
        ('WORK',0,0),('WORK',8,0),('WORK',0,0),('WORK',6,0),('SRAM',6,0x49)]
    got=[(v['kind'],v['op'],v['status']) for v in work['API_results']]
    assert got==expected and all(v['carry']==int(v['status']==0) for v in work['API_results'])
    assert work['error']=="AssertionError(('SRAM', 6, b'I4'))",'Only the reviewed $49/$4A expectation correction is admitted'
    assert not work.get('metadata_verification_error') and not work.get('SPI_restoration_error')
    for r in (program,work):
        assert r['board']=='2512' and r['all_test_blocks_restored'] and r['owner_RAM_restored'] and r['owner_ZP_restored']
        assert r['B3_unchanged'] and r['port_released']
        assert all(r[k]==0 for k in ('flash_writes','journal_writes','RTC_SET','trim_writes','PF_ACK','resets','power_cuts'))
    assert any(v.startswith('positive-SRAM-save-') for v in program['checks'])
    assert 'entire-131072-byte-SRAM-exactly-restored' in work['checks']
    before=(p/'SRAM-metadata-before.bin').read_bytes()
    assert len(before)==131072 and before==(w/'SRAM-metadata-before.bin').read_bytes()==(w/'SRAM-metadata-after.bin').read_bytes()
    assert (p/'B3-before.bin').read_bytes()==(w/'B3-before.bin').read_bytes()
    for source in ('monitors/native/sram-work-classic.inc','monitors/reference/sram-work-b35.inc'):
        text=(ROOT/'release/str8nf-v0.2.0'/source).read_text()
        guard=text[text.index('SM_A_CHECK_V2:'):text.index('SM_A_GUARD_RETURN:')]
        assert 'LDA #$49' in guard
    queries=[bytes.fromhex(v['reply_hex']) for v in work['API_results']]
    assert queries[1][22]==0 and queries[11][21]==3 and queries[16][23]==1 and queries[18][23]==0
    out=Q/'SRAM-WORK-positive-checkpoint-20261101';out.mkdir(exist_ok=False);(out/'.gitignore').write_text('*\n')
    r=dict(schema=1,passed=True,qualification='2512 physical positive RAM acceptance; installed routes remain open',
        SRAM_cases=['Store two versions','Restore latest and compare bytes','Reclaim','Delete/tombstone','Not-found refusal','SS1 format'],
        WORK_cases=['SS1 upgrade','Claim and committed-header inspection','64-byte write/read and comparison','Wrong owner',
        'Allocation bounds','Request/data overlap','Release/stale handle','48/64 KiB resize','Resize conflict',
        'Fallback selection','Primary repair','WORK format','SRAM format refuses SS2 with $49'],
        actual_API_matrix=got,SRAM_SHA256=sha(before),all_131072_SRAM_bytes_restored=True,
        owner_RAM_ZP_restored=True,B3_unchanged=True,F_writes=0,flash_writes=0,journal_writes=0,
        RTC_setting_writes=0,power_cuts=0,resets=0,port_released=True,native_routes_installed=False,
        expectation_correction=dict(host_expected='4A',baseline_and_actual='49',
            reason='SRAM SS2 format guard requires WORK ownership; $4A is the different WORK resize conflict code',
            rerun_required=False,original_failed_report_retained=True),
        receipts=[dict(path=str(v/'report.json'),sha256=sha((v/'report.json').read_bytes())) for v in (p,w)],
        limits=['Positive RAM operations qualified on 2512; read-only candidate qualified on both CPUs',
            'API write capability granted by the private harness; UNLOCK/YES/LOCK also exercised',
            'No native R SRAM/R WORK deployment; wide Store and named-transfer work remain open'])
    (out/'report.json').write_text(json.dumps(r,indent=2)+'\n');print('PASS physical SRAM/WORK RAM checkpoint; complete SRAM and owner RAM restored')
if __name__=='__main__':close()
