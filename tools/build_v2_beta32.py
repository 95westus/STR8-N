"""Build beta32's visible boot wear status from sealed beta31; offline only."""
import json,shutil
from pathlib import Path
import build_v2_config as c
import build_v2_recovery as fw
import build_v2_beta29 as gate_builder
from build_v2_spi_resident import assemble,sha
from beta4_migration import crc,s19,journal,config_sum,metadata
ROOT=Path(__file__).resolve().parents[1];BASE=ROOT/'BUILD/v2-beta31-candidate';OUT=ROOT/'BUILD/v2-beta32-candidate'
read=lambda p:json.loads(p.read_text())

def main():
 assert not list(OUT.glob('hardware-qualification-*.json'))
 parent=read(BASE/'build.json');proof=read(BASE/'beta31-qualification.json');hardware=read(BASE/'hardware-qualification-2512.json');bh=sha((BASE/'build.json').read_bytes())
 assert proof['passed'] and hardware['passed'] and proof['build_sha256']==hardware['build_sha256']==bh
 for n,h in parent['artifacts'].items():assert sha((BASE/n).read_bytes())==h,n
 assert sha((BASE/'battery/asset.bin').read_bytes())==parent['battery_asset_sha256']
 shutil.copytree(BASE,OUT,dirs_exist_ok=True)
 for pattern in ['*test-results.json','*qualification*.json','usage.json']:
  for p in OUT.glob(pattern):p.unlink()
 source=read(OUT/'source/str8n-v2-text.json')
 for msg in source:msg['text']=msg['text'].replace('2.0b30','2.0b32')
 (OUT/'source/str8n-v2-text.json').write_text(json.dumps(source,indent=2)+'\n')
 pool=bytearray();first=next(i for i,m in enumerate(source) if m['name']=='V2_BAD_PREFIX')
 for i,msg in enumerate(source):
  raw=bytearray(msg['text'].replace('{version}','2.0b32').encode())
  if i<first:raw=raw[4:]
  raw[-1]|=128;pool.extend(raw)
 c.include_bytes(OUT/'asm/text-image.inc',pool);p=OUT/'asm/text-image.inc';p.write_text('V2_TEXT:\n'+p.read_text())
 stage=OUT/'battery/source';p=stage/'battery.asm';t=(BASE/'battery/source/battery.asm').read_text()
 assert 'WEAR_OK_TEXT DB' in t
 t=t.replace('WEAR_OK_TEXT DB "FLASH: wear check OK - tracked <50,000/sector; prior/direct wear unknown.",13,10,0','WEAR_OK_TEXT DB "FLASH: wear check OK. Sector ",0')
 t=t.replace('LDY #>WEAR_OK_TEXT\n        JMP PRINT','LDY #>WEAR_OK_TEXT\n        JMP WEAR_PRINT',1)
 marker='        LDX #<WEAR_NOTE\n        LDY #>WEAR_NOTE\n        JMP PRINT'
 assert t.count(marker)==1
 t=t.replace(marker,'        LDX #<WEAR_MAX_TEXT\n        LDY #>WEAR_MAX_TEXT\n        JSR PRINT\n        JSR WEAR_DECIMAL\n'+marker,1)
 t=t.replace('WEAR_NOTE DB ". W lists counts (hex). Prior/direct wear unknown.",13,10,0','WEAR_MAX_TEXT DB ", max ",0\nWEAR_NOTE DB " tracked erases.",13,10,"Prior/direct wear unknown. W lists counts (hex).",13,10,0')
 t=t.replace('APP_END:',(ROOT/'tools/v2-rtc/wear-decimal32.inc').read_text()+'\nAPP_END:',1)
 p.write_text(t);body,bs,_=assemble(stage,'battery',0x6E00,'APP_END',0x6E07);assert len(body)<=2558
 asset=body+b'\xff'*(2558-len(body));asset+=crc(asset).to_bytes(2,'big');(OUT/'battery/asset.bin').write_bytes(asset)
 # The native provider is unchanged; retain its release tag and all RAM ABI.
 gate_builder.OUT=OUT;x=read(BASE/'xip/build.json');gate,_=gate_builder.build_gate(x['symbols']['B29_ENGINE'],parent['worker']['V2W_SELECT'])
 c.OUT,c.SOURCE=OUT,OUT/'inputs';fw.OUT=OUT;c.include_bytes(OUT/'asm/batch-gate.inc',gate+b'\xea'*(96-len(gate)))
 monitors={}
 for page in [0xA0,0xB0]:
  cells,sy=c.assemble(f'monitor-{page:02x}',(page<<8)+128,shutil.which('wdc02as'),shutil.which('wdcln'),source_file=OUT/'inputs'/f'monitor-{page:02x}.asm')
  monitor=c.dense_image(cells,(page<<8)+128,sy['V2_END']);assert len(monitor)<=3968
  image=bytearray(fw.slot_image(monitor,sy,page,44,parent['boot_compatibility']));image[70:72]=sy['V2_M_EDIT'].to_bytes(2,'little');image[18:20]=crc(image[:18]+image[32:]).to_bytes(2,'little')
  (OUT/f'str8n-v2-recovery-slot-{page:02x}.bin').write_bytes(image);(OUT/f'str8n-v2-recovery-slot-{page:02x}.s19').write_bytes(s19(dict(enumerate(image,page<<8)),0xF004));monitors[f'{page:02x}']=sy
 assert monitors==parent['monitors']
 meta=dict(parent);meta.update(version='2.0b32',generation=44,monitors=monitors,parent_build_sha256=bh,candidate_only=True,hardware_tested=False,boards_flashed=False,board_access=False,battery_symbols=bs,battery_code_bytes=len(body),battery_asset_sha256=sha(asset),flash_wear_boot_status=True,flash_wear_boot_states=['OK','WARNING','HIGH','UNKNOWN'],native_bundle_unchanged=True,flash_wear_peak_display=True,flash_wear_count_format='unsigned decimal',flash_wear_tie_break='lowest bank/sector')
 # Reference banks retain the parent's offline B-slot fixture, not live data.
 banks=[bytearray((BASE/f'candidate/b{i}.bin').read_bytes()) for i in range(4)]
 banks[2][0x6200:0x6C00]=asset;banks[3][0x3000:0x4000]=(OUT/'str8n-v2-recovery-slot-b0.bin').read_bytes()
 j=journal(banks[3]);cfg=bytearray(j[8:24]);cfg[7:13]=b'P\xB0'+(44).to_bytes(4,'little');cfg[14:]=config_sum(cfg)
 counts=[int.from_bytes(j[24+3*i:27+3*i],'little') for i in range(32)]
 banks[3][0x4000:0x5000]=metadata(cfg,counts,int.from_bytes(j[4:8],'little')+1)+b'\xff'*(4096-128)
 for i,b in enumerate(banks):(OUT/f'candidate/b{i}.bin').write_bytes(b)
 for name,off,size in [('str8n-v2-recovery-a000-dfff',0x2000,16384),('str8n-v2-recovery-c000-dfff',0x4000,8192)]:
  data=banks[3][off:off+size];(OUT/(name+'.bin')).write_bytes(data);(OUT/(name+'.s19')).write_bytes(s19(dict(enumerate(data,0x8000+off)),0xF004))
 meta['artifacts']={n:sha((OUT/n).read_bytes()) for n in parent['artifacts']};meta['artifacts']['battery/asset.bin']=sha(asset)
 (OUT/'build.json').write_text(json.dumps(meta,indent=2)+'\n')
 (OUT/'candidate/manifest.json').write_text(json.dumps(dict(candidate_only=True,installation_permitted=False,board_access=False,boards_flashed=False,banks=[sha(b) for b in banks],build_sha256=sha((OUT/'build.json').read_bytes()),note='Offline reference banks only; no installer or live board access.'),indent=2)+'\n')
 for n in ['xip/utilities.bin','boot-status/asset.bin','clock/clock.bin','clock/storage.bin','str8n-v2-recovery-e000-efff.bin','str8n-v2-recovery-f000-ffff.bin','version/asset.bin']:
  assert (OUT/n).read_bytes()==(BASE/n).read_bytes(),n
 print('BUILT beta32 candidate; battery helper',len(body),'bytes,',2558-len(body),'spare; utility/RAM unchanged; NO FLASH',flush=True)
if __name__=='__main__':main()
