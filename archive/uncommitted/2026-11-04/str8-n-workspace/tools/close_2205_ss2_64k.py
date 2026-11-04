"""Host-only closeout of the completed2205 SS2 resize; historical receipts stay exact."""
import json
from pathlib import Path
from resize_2205_ss2_64k import ROOT,Q,OUT,SCOPE,t

def run():
    r=json.loads((OUT/'report.json').read_text(encoding='utf-8'))
    assert r['passed'] and not r['SPI_change_pending'] and r['metadata_operation_started']
    for k in ('whole_SPI_matches_exact_plan','PROGRAM_records_exact','all_payload_bytes_exact','all_four_banks_exact','owner_RAM_restored','owner_ZP_restored','provider_cache_restored','F_images_settings_history_exact','port_released'):assert r[k],k
    p=json.loads((SCOPE/'plan.json').read_text(encoding='utf-8'))
    before=(OUT/'SPI-before.bin').read_bytes();after=(OUT/'SPI-after.bin').read_bytes()
    assert after==(SCOPE/'SPI-metadata-expected.bin').read_bytes()+before[2048:]
    changed=[i for i,(a,b) in enumerate(zip(before,after)) if a!=b];assert len(changed)==p['expected_changed_bytes']==74
    archive=ROOT/'local-archives/2205-SS2-64K-20261102'
    for file in (OUT/'report.json',OUT/'SPI-after.bin',OUT/'layout-after.json'):
        target=archive/file.name;assert not target.exists();target.write_bytes(file.read_bytes())
    t.save(archive/'completion-manifest.json',dict(local_only=True,permanent=True,passed=True,files={file.name:dict(bytes=file.stat().st_size,sha256=t.sha(file.read_bytes())) for file in archive.iterdir() if file.is_file()}))
    previous=Q/'SS2-64K-standardization-complete-20261102.json';old=json.loads(previous.read_text(encoding='utf-8'));assert old['passed']
    result=dict(passed=True,format='SS2',PROGRAM_boundary='10000',PROGRAM_payload_bytes=63488,WORKSPACE_payload_bytes=65504,
        previous_three_board_receipt=str(previous),previous_receipt_sha256=t.sha(previous.read_bytes()),
        boards={b:dict(report=old['boards'][b]['report'],passed=True) for b in ('2512','2604','2609')})
    result['boards']['2205']=dict(report=str(OUT/'report.json'),report_sha256=t.sha((OUT/'report.json').read_bytes()),passed=True,
        archive=str(archive),SPI_before_sha256=t.sha(before),SPI_after_sha256=t.sha(after),metadata_bytes_changed=74,
        both_CLK_records_and_all_payload_preserved=True,flash_settings_history_exact=True,owner_RAM_ZP_cache_hooks_restored=True,
        native_operation_repeated=False,physical_resets=0,power_cuts=0,flash_writes=0,
        flash_bank_sha256={f'B{b}':t.sha((OUT/f'B{b}-before.bin').read_bytes()) for b in range(4)})
    for board in result['boards']:
        marker=json.loads((Q/f'device-operations/{board}.json').read_text(encoding='utf-8'))
        assert marker['SPI_format']=='SS2' and marker['PROGRAM_boundary']=='10000'
    t.save(Q/'SS2-64K-four-board-complete-20261102.json',result)
    docs=ROOT/'release/str8nf-v0.2.0/docs'
    path=docs/'2205_CURRENT_INVENTORY.md';text=path.read_text(encoding='utf-8')
    old='- SPI SS2:32 KiB PROGRAM/96 KiB WORKSPACE; payload30,720 bytes and\n  WORKSPACE98,272 bytes. Full128KiB exact against the permanent backup.'
    new='- SPI SS2: 64 KiB PROGRAM / 64 KiB WORKSPACE; PROGRAM payload 63,488 bytes\n  and WORKSPACE 65,504 bytes. Native P64 resize passed: exactly 74 management\n  bytes changed, with the PROGRAM directory and every payload byte retained.'
    assert text.count(old)==1;text=text.replace(old,new)
    text+='\nThe later 64/64 resize receipt is\n`output/qualification/2205-SS2-64K-standardized-20261102-r1/report.json`.\nAll four boards now have recorded SS2/64K layouts; combined receipt:\n`output/qualification/SS2-64K-four-board-complete-20261102.json`.\nThis metadata-only change used zero flash/journal/RTC-setting writes or resets.\nOriginal SPECIAL and initial 32/96 rollout receipts remain unchanged.\n'
    path.write_text(text,encoding='utf-8')
    path=docs/'UNIFIED_CANDIDATE_STATUS.md';text=path.read_text(encoding='utf-8')
    old='2205 retains its existing SS2 32KiB PROGRAM/96KiB WORKSPACE layout and both\nold CLK records; it was not included in the separate64/64 resize allowance.\nIts old CLK payloads are retained data, not newly qualified legacy-ABI apps.'
    new='A later owner-requested 2205 native P64 resize passed, so all four reference\nboards now use SS2 with 64 KiB PROGRAM / 64 KiB WORKSPACE. Both old 2205 CLK\nrecords and all payload bytes remain exact. Its old CLK payloads are retained\ndata, not newly qualified legacy-ABI apps. The original three-board receipt\nand SPECIAL archive stay unchanged; the four-board combined receipt is\n`output/qualification/SS2-64K-four-board-complete-20261102.json`.'
    assert text.count(old)==1;text=text.replace(old,new);path.write_text(text,encoding='utf-8')
    path=docs/'2205_FOUNDATION_ROLLOUT_ACCEPTANCE.md';text=path.read_text(encoding='utf-8')
    text+='\n## Subsequent 64/64 standardization\n\nThe later instruction “change 64/64 on 2205.” authorized a separate native\nWORK P64 resize. It passed with exactly 74 changed management bytes across\n192 permitted addresses: layout generation 3 and WS revision/epoch 2.\nBoth CLK records, all payload bytes, all four flash banks, settings/history\nand fresh owner RAM/ZP/cache/hooks were preserved. No flash or RTC-setting\nwrites, reset or power cut occurred; RTC retained priority. This supersedes\nthe initial 32/96 layout for current inventory, without altering the historical\nSPECIAL backup or the initial rollout receipts. Final REC>, COM3 released.\n\nReceipt: `output/qualification/2205-SS2-64K-standardized-20261102-r1/report.json`.\nPrivate resize preimages and completion evidence:\n`C:\\SRC\\STR8-N\\local-archives\\2205-SS2-64K-20261102`.\n'
    path.write_text(text,encoding='utf-8')
    print('PASS allfour recorded SS2/64K layouts;2205 records/payload/flash/settings/history and owner exact; original SPECIAL and three-board receipts unchanged',flush=True)

if __name__=='__main__':run()
