"""Verify unchanged shared firmware and temporary CPU probe before 2609 install."""
import hashlib,json,os,re,shutil,subprocess,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];Q=ROOT/'output/qualification'
read=lambda p:json.loads(p.read_text())
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
def main():
    out=Q/'bf1-2609-hardware-2026-10-17';out.mkdir(exist_ok=True);receipt=out/'shared-firmware-preflight.json';assert not receipt.exists()
    pin=read(Q/'batchfix-r1-2026-10-17/candidate-artifact-pin.json');build=ROOT/'tmp/bfx5'
    for name,v in pin['artifacts'].items():assert sha(build/'payload'/name)==v['sha256']
    for name,digest in pin['source_files'].items():assert sha(ROOT/'release/candidates/batchfix-r1'/name)==digest
    model=Q/'bf1-2609-route-2026-10-17-r1';m=read(model/'report.json');assert m['passed'] and m['cases']==28
    prior=Q/'bf1-2604-hardware-2026-10-17/A-checks';old=read(prior/'report.json');assert old['passed'] and old['full_flash_verified']
    oldbanks=[(prior/f'after-checks-b{i}.bin').read_bytes() for i in range(4)];newbanks=[(model/'install-A-after-B-complete'/f'b{i}.bin').read_bytes() for i in range(4)]
    layout=read(ROOT/'release/beta35/layout.json');ranges=[]
    for segment in layout['segments']:
        bank=segment['bank'];offset=segment['address']-0x8000;n=segment['bytes'];target=(build/'payload'/segment['file']).read_bytes()[segment['offset']:segment['offset']+n]
        assert oldbanks[bank][offset:offset+n]==newbanks[bank][offset:offset+n]==target
        ranges.append(dict(bank=bank,address=segment['address'],bytes=n,sha256=hashlib.sha256(target).hexdigest()))
    assert oldbanks[3][0x2000:0x3000]==newbanks[3][0x2000:0x3000]==(build/'payload/str8n-v2-recovery-slot-a0.bin').read_bytes()
    probe=ROOT/'tmp/bf1cpu2';pr=read(probe/'report.json');assert pr['passed'] and sha(probe/'mode.bin')==pr['binary_sha256'] and sha(probe/'mode.s19')==pr['s19_sha256']
    # Obtain opcode encoding independently from WDC's 816 assembler without
    # running a native-mode CPU program or changing the firmware.
    op=ROOT/'tmp/bf1cpuop1';assert not op.exists();op.mkdir();(op/'op.asm').write_text(' MODULE OPCHECK\n CODE\n SEC\n XCE\n NOP\n PHB\n PHK\n PHD\n END\n')
    logs=[]
    for cmd in [[shutil.which('wdc816as'),'-G','-L','-S','-W','op.asm'],[shutil.which('wdcln'),'-g','-s','-t','-c2000','-hm19','-j','-o','op.s19','op.obj']]:
        r=subprocess.run(cmd,cwd=op,capture_output=True,text=True);logs.append(dict(command=cmd,returncode=r.returncode,stdout=r.stdout,stderr=r.stderr));(op/'build.log.json').write_text(json.dumps(logs,indent=2));assert r.returncode==0,(r.stdout,r.stderr)
    codes=[]
    for line in (op/'op.s19').read_text().splitlines():
        raw=bytes.fromhex(line[2:]);assert len(raw)==raw[0]+1 and sum(raw)&255==255
        if line[1]=='1':codes.extend(raw[3:-1])
    assert bytes(codes)==bytes.fromhex('38fbea8b4b0b')
    freeze=read(Q/'beta35-release-qualification-2026-10-17-034745Z/freeze.json');ws=Path(freeze['frozen_source_directory']);os.environ.update(STR8_RTC_BUILD='BUILD/v2-beta35-candidate',STR8_TEST_DEPS=str(ws/'BUILD/test-deps'));sys.path.insert(0,str(ws/'tools'))
    import serial
    def forbidden(*a,**k):raise RuntimeError('Serial forbidden during CPU-probe preflight')
    serial.Serial=forbidden
    from test_v2_status import fresh,boot,snapshot
    from test_v2_sram_store import console
    cpu,mem=fresh();mem.fast=True
    for i,data in enumerate(newbanks):mem.banks[i][:]=data
    backup=Q/'2609-return-backup-2026-10-17-1931Z';ee=(backup/'eeprom.bin').read_bytes();mem.bus.ee[:128]=ee[:128];mem.bus.ee[0xff]=ee[128];mem.bus.ee[0xf0:0xf8]=ee[129:137];mem.spi.devices[0].data[:]=(backup/'sram.bin').read_bytes();mem.bus.rtc_regs[:9]=bytes.fromhex('95 53 19 2F 18 10 26 80 0E')
    boot(cpu);before=snapshot(mem);data=(probe/'mode.bin').read_bytes();mem.ram[0x2000:0x2000+len(data)]=data
    text=console(cpu,mem,b'',entry=0x2000,limit=100000000);raw=bytes(mem.ram[0x2440:0x244e])
    assert raw[:6]==bytes.fromhex('02ff00000000') and raw[7:12]==bytes.fromhex('0117040102') and raw[13]==0xa5 and raw[6]&0x0c==4 and snapshot(mem)==before and not mem.events and not mem.bus.writes
    (out/'CPU-probe-65C02-model.txt').write_bytes(text)
    result=dict(passed=True,one_firmware_set=True,candidate_id='batchfix-r1',generation=48,artifacts=pin['artifacts'],shared_owned_ranges=ranges,additional_A_slot_identical=True,
        prior_2604_hardware_report_sha256=sha(prior/'report.json'),new_2609_model_report_sha256=sha(model/'report.json'),temporary_probe_report_sha256=sha(probe/'report.json'),temporary_probe_sha256=pr['binary_sha256'],temporary_probe_65C02_model_passed=True,temporary_probe_65C02_result_hex=raw.hex(),WDC816_opcode_encoding_checked=True,
        runtime_contract='65C02 or 65C816 E=1, D=0, DBR=0, PBR=0; no native-mode monitor-service calls',startup_exception='Owner explicitly accepts unchanged F30D CPU detection briefly entering native mode then restoring E=1',deferred=['native 816 applications/tests','ACIA','crypto'],firmware_modified=False,board_access=False,installation_permitted=False,release_qualified=False)
    receipt.write_text(json.dumps(result,indent=2)+'\n');print('PASS one firmware set, shared code ranges, WDC816 opcode check and fresh 65C02 mode-probe model')
if __name__=='__main__':main()
