"""Compose STR8-N bf1 B1/B2/B3 only. B0/WDCMONV2 is excluded, never an input."""
import argparse,json,hashlib
from pathlib import Path
from build_full_image import compose
sha=lambda data:hashlib.sha256(data).hexdigest()
def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--payload',type=Path,required=True);p.add_argument('--reference',type=Path,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args()
    reference=json.loads(a.reference.read_text());full,ranges=compose(a.payload,reference);image=full[32768:];assert len(image)==98304 and full[:32768]==b'\xff'*32768
    a.out.mkdir(parents=True,exist_ok=False);name='str8n-2.0bf1-str8n-only.bin';(a.out/name).write_bytes(image)
    relocated=[dict(item,offset=item['offset']-32768) for item in ranges];assert all(item['bank'] in (1,2,3) and item['offset']>=0 for item in relocated)
    manifest=dict(version='2.0bf1',generation=48,filename=name,bytes=len(image),sha256=sha(image),bank_order=[1,2,3],excluded_banks=[0],bytes_per_bank=32768,CPU_window='8000-FFFF',offset_formula='(bank-1)*32768 + CPU_address - 0x8000',full_device_programmer_offset=32768,contains_WDCMONV2_firmware=False,WDC_vendor_image_inputs=False,no_board_capture_inputs=True,no_EEPROM_SRAM_RTC_image=True,processor_scope='Identical firmware bytes for 65C02 and 65C816 emulation runtime',startup_detector_exception='Existing F30D startup detection retained',MON_A=dict(bank=3,address=0xa000,file_offset=0x12000),MON_B=dict(bank=3,address=0xb000,file_offset=0x13000),ranges=relocated,fresh_provisioning_only=True,preserving_upgrade=False,B0_programming_permitted=False,full_release_qualified=False,board_access=False,reference_sha256=sha(a.reference.read_bytes()),composer_sha256=sha(Path(__file__).read_bytes()),base_composer_sha256=sha(Path(__file__).with_name('build_full_image.py').read_bytes()),deferred=['native 816 applications/tests','ACIA','crypto'])
    (a.out/'str8n-only-layout.json').write_text(json.dumps(manifest,indent=2)+'\n');(a.out/'str8n-only.sha256').write_text(sha(image)+'  '+name+'\n');print(json.dumps({k:manifest[k] for k in ('filename','bytes','sha256','bank_order','excluded_banks','contains_WDCMONV2_firmware')},indent=2))
if __name__=='__main__':main()
