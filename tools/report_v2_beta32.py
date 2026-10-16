"""Seal the beta32 boot wear-status candidate's offline evidence."""
import json
from pathlib import Path
from beta4_migration import crc,slot_valid
from build_v2_spi_resident import sha
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'BUILD/v2-beta32-candidate';BASE=ROOT/'BUILD/v2-beta31-candidate'
def main():
 meta=json.loads((OUT/'build.json').read_text());bh=sha((OUT/'build.json').read_bytes());receipts={}
 for name in ['beta32-wear-test-results.json','beta32-reproducibility-test-results.json']:
  r=json.loads((OUT/name).read_text());assert r['passed'] and r['build_sha256']==bh
  if 'artifacts' in r:assert r['artifacts']==meta['artifacts']
  receipts[name]=dict(sha256=sha((OUT/name).read_bytes()),checks=r.get('checks',[]))
 for name,digest in meta['artifacts'].items():assert sha((OUT/name).read_bytes())==digest,name
 assert crc((OUT/'battery/asset.bin').read_bytes())==0
 for page in [0xA0,0xB0]:assert slot_valid((OUT/f'str8n-v2-recovery-slot-{page:02x}.bin').read_bytes(),page)
 for name in ['xip/utilities.bin','boot-status/asset.bin','clock/clock.bin','clock/storage.bin','str8n-v2-recovery-e000-efff.bin','str8n-v2-recovery-f000-ffff.bin','version/asset.bin']:
  assert (OUT/name).read_bytes()==(BASE/name).read_bytes(),name
 old=[(BASE/f'candidate/b{i}.bin').read_bytes() for i in range(4)];new=[(OUT/f'candidate/b{i}.bin').read_bytes() for i in range(4)]
 assert new[:2]==old[:2] and new[2][:0x6200]==old[2][:0x6200] and new[2][0x6C00:]==old[2][0x6C00:]
 assert new[3][:0x3000]==old[3][:0x3000] and new[3][0x5000:]==old[3][0x5000:]
 used=meta['battery_code_bytes']+2
 usage=dict(version='2.0b32',candidate_only=True,model_qualified=True,hardware_tested=False,board_access=False,boards_flashed=False,battery_wear_helper=dict(reserved_flash_bytes=2560,used_flash_bytes=used,spare_flash_bytes=2560-used,added_code_bytes=meta['battery_code_bytes']-json.loads((BASE/'build.json').read_text())['battery_code_bytes']),utility_flash=dict(used_bytes=22012,spare_bytes=516,unchanged=True),additional_ram_reservation_bytes=0,monitor_bytes=meta['monitor_bytes'],flash_wear_thresholds=meta['flash_wear_thresholds'])
 (OUT/'usage.json').write_text(json.dumps(usage,indent=2)+'\n')
 seal=dict(passed=True,version='2.0b32',candidate_only=True,build_sha256=bh,artifacts=meta['artifacts'],receipts=receipts,usage_sha256=sha((OUT/'usage.json').read_bytes()),board_access=False,boards_flashed=False,hardware_tested=False,installer_generated=False)
 (OUT/'beta32-qualification.json').write_text(json.dumps(seal,indent=2)+'\n');print(json.dumps(usage,indent=2))
if __name__=='__main__':main()
