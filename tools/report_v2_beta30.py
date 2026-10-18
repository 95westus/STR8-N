"""Seal beta30 offline receipts and write a concise candidate usage report."""
import json
from pathlib import Path
from beta4_migration import crc,slot_valid
from build_v2_spi_resident import sha
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'BUILD/v2-beta30-candidate'
read=lambda p:json.loads(p.read_text())

def main():
    meta=read(OUT/'build.json');x=read(OUT/'xip/build.json');bh=sha((OUT/'build.json').read_bytes())
    receipts={}
    for name in ['beta30-test-results.json','beta30-alias-test-results.json','beta30-program-test-results.json','beta30-reproducibility-test-results.json']:
        r=read(OUT/name);assert r['passed'] and r['build_sha256']==bh,name
        if 'artifacts' in r:assert r['artifacts']==meta['artifacts'],name
        receipts[name]=dict(sha256=sha((OUT/name).read_bytes()),checks=r.get('checks',[]))
    for n,h in meta['artifacts'].items():assert sha((OUT/n).read_bytes())==h,n
    assert crc((OUT/'xip/utilities.bin').read_bytes())==0
    assert crc((OUT/'boot-status/asset.bin').read_bytes())==0
    assert crc((OUT/'version/asset.bin').read_bytes())==0
    assert all(slot_valid((OUT/f'str8n-v2-recovery-slot-{p:02x}.bin').read_bytes(),p) for p in [0xA0,0xB0])
    prior=ROOT/'output/qualification/beta28-2026-10-15/2512/upgrade'
    banks=[(OUT/f'candidate/b{i}.bin').read_bytes() for i in range(4)]
    assert banks[0]==(prior/'post-reset-b0.bin').read_bytes()
    old=(prior/'post-reset-b3.bin').read_bytes();assert banks[3][:0x3000]==old[:0x3000] and banks[3][0x7000:]==old[0x7000:]
    assert not (OUT/'candidate/manifest.json').is_file() or not read(OUT/'candidate/manifest.json')['installation_permitted']
    used=x['flash_linked_bytes']+2;spare=22528-used
    clock=meta['clock_bytes'];usage=dict(version='2.0b30',candidate_only=True,model_qualified=True,hardware_tested=False,board_access=False,boards_flashed=False,utility_flash=dict(reserved_bytes=22528,used_bytes=used,spare_bytes=spare,beta29_used_bytes=21874,added_bytes=used-21874),batch_ram=dict(reserved_bytes=156,regions=meta['batch_ram_regions'],maximum_command_list_bytes=34,maximum_monitor_line_bytes=40,application_ram_range_unchanged=True),clock=dict(version='1.9',ram_start=8192,ram_end_inclusive=8192+clock-1,ram_bytes=clock,flash_record_bytes=clock+24,reserved_flash_bytes=12288,spare_flash_bytes=12288-clock-24),monitor_bytes=meta['monitor_bytes'])
    (OUT/'usage.json').write_text(json.dumps(usage,indent=2)+'\n')
    seal=dict(passed=True,version='2.0b30',candidate_only=True,build_sha256=bh,artifacts=meta['artifacts'],receipts=receipts,usage_sha256=sha((OUT/'usage.json').read_bytes()),board_access=False,boards_flashed=False,hardware_tested=False,installer_generated=False)
    (OUT/'beta30-qualification.json').write_text(json.dumps(seal,indent=2)+'\n')
    print(json.dumps(usage,indent=2))

if __name__=='__main__':main()
