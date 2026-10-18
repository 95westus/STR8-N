"""Build beta30 monitor aliases from sealed beta29; offline only, no installer."""
import json,shutil
from pathlib import Path
import build_v2_beta29 as previous
import build_v2_config as c
import build_v2_recovery as fw
from build_v2_spi_resident import assemble,sha
from beta4_migration import crc,s19,journal,config_sum,metadata
ROOT=Path(__file__).resolve().parents[1];BASE=ROOT/'BUILD/v2-beta29-candidate';OUT=ROOT/'BUILD/v2-beta30-candidate'
read=lambda p:json.loads(p.read_text())
def monitors(meta,gate):
 c.OUT,c.SOURCE=OUT,OUT/'inputs';fw.OUT=OUT
 c.include_bytes(OUT/'asm/batch-gate.inc',gate)
 result={}
 for page in [0xA0,0xB0]:
  cells,sy=c.assemble(f'monitor-{page:02x}',(page<<8)+128,shutil.which('wdc02as'),shutil.which('wdcln'),source_file=OUT/'inputs'/f'monitor-{page:02x}.asm')
  body=c.dense_image(cells,(page<<8)+128,sy['V2_END']);assert len(body)<=3968
  image=bytearray(fw.slot_image(body,sy,page,42,meta['boot_compatibility']));image[70:72]=sy['V2_M_EDIT'].to_bytes(2,'little');image[18:20]=crc(image[:18]+image[32:]).to_bytes(2,'little')
  (OUT/f'str8n-v2-recovery-slot-{page:02x}.bin').write_bytes(image);(OUT/f'str8n-v2-recovery-slot-{page:02x}.s19').write_bytes(s19(dict(enumerate(image,page<<8)),0xF004));result[f'{page:02x}']=sy
 return result

def main():
 assert not list(OUT.glob('hardware-qualification-*.json'))
 parent=read(BASE/'build.json');proof=read(BASE/'beta29-qualification.json');hardware=read(BASE/'hardware-qualification-2512.json')
 assert proof['passed'] and hardware['passed'] and proof['build_sha256']==hardware['build_sha256']==sha((BASE/'build.json').read_bytes())
 for n,h in parent['artifacts'].items():assert sha((BASE/n).read_bytes())==h,n
 shutil.copytree(BASE,OUT,dirs_exist_ok=True)
 for pattern in ['*test-results.json','*qualification*.json','usage.json']:
  for p in OUT.glob(pattern):p.unlink()
 source=read(OUT/'source/str8n-v2-text.json')
 for msg in source:msg['text']=msg['text'].replace('2.0b29','2.0b30')
 (OUT/'source/str8n-v2-text.json').write_text(json.dumps(source,indent=2)+'\n')
 pool=bytearray();first=next(i for i,m in enumerate(source) if m['name']=='V2_BAD_PREFIX')
 for i,msg in enumerate(source):
  raw=bytearray(msg['text'].replace('{version}','2.0b30').encode())
  if i<first:raw=raw[4:]
  raw[-1]|=128;pool.extend(raw)
 c.include_bytes(OUT/'asm/text-image.inc',pool);p=OUT/'asm/text-image.inc';p.write_text('V2_TEXT:\n'+p.read_text())
 for page in [0xA0,0xB0]:
  p=OUT/'inputs'/f'monitor-{page:02x}.asm';t=(BASE/'inputs'/p.name).read_text();assert 'B29_PROVIDER_MAGIC DB "UX",2,41' in t
  p.write_text(t.replace('B29_PROVIDER_MAGIC DB "UX",2,41','B29_PROVIDER_MAGIC DB "UX",2,42'))
 p=OUT/'xip/source/utilities.asm';t=(BASE/'xip/source/utilities.asm').read_text();assert 'DB "UX",2,41' in t
 t=t.replace('DB "UX",2,41','DB "UX",2,42',1)
 begin=t.index('B29_TYPED:');end=t.index('B29_TRY_BATCH:',begin)
 part=t[begin:end];assert 'B29_LONG_99:\n        LDA $7C00' in part
 part=part.replace('B29_LONG_99:\n','B29_LONG_99:\n        JSR B30_ALIAS\n',1);t=t[:begin]+part+t[end:]
 t=t.replace('B29_MON_NOT_HELP:\n','B29_MON_NOT_HELP:\n        JSR B30_ALIAS\n',1)
 start=t.index('B29_FULL_HELP_TEXT:');end=t.index('B29_MON_DELTA',start)
 full=next(m['text'] for m in read(ROOT/'BUILD/v2-beta28-b23/source/str8n-v2-text.json') if m['name']=='V2_HELP')+'\r\nMAINT SRAM WORK EDU (R optional)\r\nBATCH cmd;cmd (34 text bytes); ESC cancels\r\n'
 raw=full.encode()+b'\0';helptext='B29_FULL_HELP_TEXT:\n'+''.join('        DB '+','.join(f'${v:02X}' for v in raw[i:i+16])+'\n' for i in range(0,len(raw),16))+'\n'
 t=t[:start]+helptext+t[end:]
 alias=(ROOT/'tools/v2-spi/utility-alias30.asm').read_text();t=t.replace('X28_END:',alias+'\nX28_END:');assert t.count('JSR B30_ALIAS')==2
 p.write_text(t)
 body,sy,_=assemble(p.parent,'utilities',0x8000,'X28_END',0x8000);assert len(body)<=0x57FE
 # Native entry addresses precede all alias changes. WORK stub and status
 # targets remain byte exact; only the provider's release tag changes.
 old=read(BASE/'xip/build.json')['symbols']
 for name in ['MM_START','SM_ENTRY','WK_ENTRY','WK_API','ED_START','X28_APPS','B29_ENGINE']:assert sy[name]==old[name],name
 asset=body+b'\xff'*(0x57FE-len(body));asset+=crc(asset).to_bytes(2,'big');(OUT/'xip/utilities.bin').write_bytes(asset)
 previous.OUT=OUT;gate,gs=previous.build_gate(sy['B29_ENGINE'],parent['worker']['V2W_SELECT']);assert len(gate)<=96
 linked=monitors(parent,gate+b'\xea'*(96-len(gate)));assert linked==parent['monitors'],'Monitor layout moved'
 stage=OUT/'storage-status/source';p=stage/'storage-services.inc';t=(BASE/'storage-status/source/storage-services.inc').read_text();assert 'DB "UX",2,41' in t;p.write_text(t.replace('DB "UX",2,41','DB "UX",2,42'))
 status,ss,_=assemble(stage,'storage-status',0x6E00,'APP_END',0x6E07);assert len(status)<=2558
 sa=status+b'\xff'*(2558-len(status));sa+=crc(sa).to_bytes(2,'big');(OUT/'boot-status/asset.bin').write_bytes(sa)
 meta=dict(parent);meta.update(version='2.0b30',generation=42,monitors=linked,candidate_only=True,boards_flashed=False,hardware_tested=False,board_access=False,parent_build_sha256=sha((BASE/'build.json').read_bytes()),utility_aliases=['MAINT','SRAM','WORK','EDU'],utility_alias_scope='monitor and monitor-provider batch segments',status_symbols=ss,status_code_bytes=len(status),status_asset_sha256=sha(sa))
 meta['artifacts']={n:sha((OUT/n).read_bytes()) for n in parent['artifacts']}
 (OUT/'build.json').write_text(json.dumps(meta,indent=2)+'\n')
 x=read(BASE/'xip/build.json');x.update(version='2.0b30',generation=42,symbols=sy,flash_linked_bytes=len(body),flash_spare_bytes=0x57FE-len(body),sha256=sha(asset));(OUT/'xip/build.json').write_text(json.dumps(x,indent=2)+'\n')
 # Reference only: preserve the beta29 candidate's A28 fallback arrangement.
 # Fresh live backups and an installation plan are deliberately absent.
 banks=[bytearray((BASE/f'candidate/b{i}.bin').read_bytes()) for i in range(4)]
 banks[2][:0x5800]=asset;banks[2][0x5800:0x6200]=sa;banks[3][0x3000:0x4000]=(OUT/'str8n-v2-recovery-slot-b0.bin').read_bytes()
 j=journal(banks[3]);cfg=bytearray(j[8:24]);cfg[7:13]=b'P\xB0'+(42).to_bytes(4,'little');cfg[14:]=config_sum(cfg)
 counts=[int.from_bytes(j[24+3*i:27+3*i],'little') for i in range(32)]
 banks[3][0x4000:0x5000]=metadata(cfg,counts,int.from_bytes(j[4:8],'little')+1)+b'\xff'*(4096-128)
 for i,b in enumerate(banks):(OUT/f'candidate/b{i}.bin').write_bytes(b)
 for name,off,size in [('str8n-v2-recovery-a000-dfff',0x2000,16384),('str8n-v2-recovery-c000-dfff',0x4000,8192)]:
  data=banks[3][off:off+size];(OUT/(name+'.bin')).write_bytes(data);(OUT/(name+'.s19')).write_bytes(s19(dict(enumerate(data,0x8000+off)),0xF004))
 meta['artifacts']={n:sha((OUT/n).read_bytes()) for n in meta['artifacts']};(OUT/'build.json').write_text(json.dumps(meta,indent=2)+'\n')
 (OUT/'candidate/manifest.json').write_text(json.dumps(dict(candidate_only=True,installation_permitted=False,board_access=False,boards_flashed=False,banks=[sha(b) for b in banks],build_sha256=sha((OUT/'build.json').read_bytes()),note='Offline reference only; same B-slot batch ABI and A28 reference fallback as parent. No live state captured or installer generated.'),indent=2)+'\n')
 for name in ['clock/clock.bin','clock/storage.bin','clock/build.json','str8n-v2-recovery-e000-efff.bin','str8n-v2-recovery-f000-ffff.bin','version/asset.bin']:
  assert (OUT/name).read_bytes()==(BASE/name).read_bytes(),name
 print('BUILT beta30 candidate:',len(body)+2,'utility bytes,',0x57FE-len(body),'spare; no additional RAM; NO FLASH',flush=True)
if __name__=='__main__':main()
