"""Compose a clean 128 KiB bf1 programmer image from the pinned build payloads.

No board capture, serial access, retained-device image, or existing wear journal
is an input. This is fresh provisioning, not a preserving upgrade transaction.
"""
import argparse,binascii,hashlib,json
from pathlib import Path

SEGMENTS=[
    (1,0xB000,'clock/storage.bin',0,12288),
    (1,0xE000,'assembler/asm-e000.bin',0,4096),
    (1,0xF000,'assembler/vectors-f000.bin',0,4096),
    (2,0x8000,'xip/utilities.bin',0,22528),
    (2,0xD800,'boot-status/asset.bin',0,2560),
    (2,0xE200,'battery/asset.bin',0,2560),
    (2,0xF000,'local-display/asset.bin',0,1792),
    (2,0xF800,'version/asset.bin',0,2048),
    (3,0x8000,'str8n-rtc-component-8000-8fff.bin',0,4096),
    (3,0x9000,'str8n-journal-9000-9fff.bin',0,4096),
    (3,0xA000,'str8n-v2-recovery-slot-a0.bin',0,4096),
    (3,0xB000,'str8n-v2-recovery-slot-b0.bin',0,4096),
    (3,0xE000,'str8n-v2-recovery-e000-efff.bin',0,4096),
    (3,0xF000,'str8n-v2-recovery-f000-ffff.bin',0,4096)]
sha=lambda b:hashlib.sha256(b).hexdigest()
crc=lambda b:binascii.crc_hqx(b,0xffff)

def fresh_record():
    # Same documented source defaults as the bootstrap template, with explicit
    # MON A / generation 48 selection. Counts are a fresh-provisioning baseline,
    # not a claim of zero historical erases on an existing physical device.
    config=bytearray([1,0,3,7,0xF0,10,0]+[0]*9)
    config[7:13]=b'P\xA0'+(48).to_bytes(4,'little')
    a=b=0
    for value in config[:14]:a=(a+value)&255;b=(b+a)&255
    config[14:]=bytes([a,b])
    record=bytearray(b'\xff'*128);record[:8]=b'WC\x01\0'+(1).to_bytes(4,'little')
    record[8:24]=config;record[24:120]=bytes(96);record[120:122]=crc(record[:120]).to_bytes(2,'little');record[127]=0
    return bytes(record)

def compose(payload,reference):
    files={}
    assert reference['version']=='2.0bf1' and reference['generation']==48 and len(reference['artifacts'])==19
    for name,info in reference['artifacts'].items():
        data=(payload/name).read_bytes();assert len(data)==info['bytes'] and sha(data)==info['sha256'],'Payload pin mismatch: '+name;files[name]=data
    image=bytearray(b'\xff'*131072);coverage=bytearray(131072);ranges=[]
    for bank,address,name,offset,size in SEGMENTS:
        first=bank*32768+address-0x8000;data=files[name][offset:offset+size]
        assert len(data)==size and not any(coverage[first:first+size])
        image[first:first+size]=data;coverage[first:first+size]=b'\x01'*size
        ranges.append(dict(bank=bank,address=address,offset=first,bytes=size,source=name,source_offset=offset,sha256=sha(data)))
    first=3*32768+0x4000;record=fresh_record();image[first:first+128]=record;coverage[first:first+128]=b'\x01'*128
    ranges.append(dict(bank=3,address=0xC000,offset=first,bytes=128,source='fresh deterministic configuration/wear record',sha256=sha(record)))
    assert all(v==255 for i,v in enumerate(image) if not coverage[i])
    assert image[:32768]==b'\xff'*32768
    assert image[3*32768+0x1C00:3*32768+0x2000]==b'\xff'*1024
    for page in (0xA0,0xB0):
        slot=image[3*32768+(page-0x80)*256:3*32768+(page-0x80)*256+4096]
        assert slot[:4]==b'MI\x01'+bytes([page]) and slot[31]==0 and int.from_bytes(slot[8:12],'little')==48
        assert crc(slot[:18]+slot[32:])==int.from_bytes(slot[18:20],'little')
    assert image[-4:-2]==b'\x04\xF0'
    return bytes(image),ranges

def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--payload',type=Path,required=True);ap.add_argument('--reference',type=Path,required=True);ap.add_argument('--out',type=Path,required=True);a=ap.parse_args()
    ref=json.loads(a.reference.read_text(encoding='utf-8'));image,ranges=compose(a.payload,ref)
    a.out.mkdir(parents=True,exist_ok=False);name='str8n-2.0bf1-firmware.bin';(a.out/name).write_bytes(image)
    manifest=dict(version='2.0bf1',generation=48,filename=name,bytes=len(image),sha256=sha(image),bank_order=[0,1,2,3],bytes_per_bank=32768,CPU_window='8000-FFFF',offset_formula='bank*32768 + CPU_address - 0x8000',processor_scope='65C02 and 65C816 emulation runtime',startup_detector_exception='Unchanged F30D CPU detection briefly enters native mode then restores E=1',default_monitor='MON A',alternate_monitor='MON B',MON_A=dict(bank=3,address=0xA000,file_offset=0x1A000),MON_B=dict(bank=3,address=0xB000,file_offset=0x1B000),configuration='fresh deterministic defaults, MON A generation 48',wear_history='fresh provisioning baseline, not existing-device lifetime counts',erased_fill=255,no_board_capture_inputs=True,no_device_identity_in_image=True,no_EEPROM_SRAM_or_RTC_image=True,ranges=ranges,reference_sha256=sha(a.reference.read_bytes()),composer_sha256=sha(Path(__file__).read_bytes()),fresh_provisioning_only=True,preserving_upgrade=False,full_release_qualified=False,hardware_flash_performed=False,board_access=False,deferred=['native 816 applications/tests','ACIA','crypto'])
    (a.out/'firmware-layout.json').write_text(json.dumps(manifest,indent=2)+'\n');(a.out/'str8n-2.0bf1-firmware.sha256').write_text(sha(image)+'  '+name+'\n');print(json.dumps({k:manifest[k] for k in ('filename','bytes','sha256','bank_order','default_monitor')},indent=2))
if __name__=='__main__':main()
