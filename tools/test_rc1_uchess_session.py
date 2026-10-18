"""Execute published bf1 ASM0.5 -> S/T/R -> restored game in CPU model only."""
import hashlib,json,os,sys,traceback,zipfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];Q=ROOT/'output/qualification';OUT=Q/'rc1-uchess-model-r2';sha=lambda b:hashlib.sha256(b).hexdigest()
def main():
    assert not OUT.exists();OUT.mkdir();published=ROOT/'output/releases/rc1-2026-10-18-r1/str8n-v2.0rc1-release.zip'
    with zipfile.ZipFile(published) as z:
        image=z.read('str8n-2.0rc1/firmware/str8n-2.0rc1-apps-str8n-only.bin');source=z.read('str8n-2.0rc1/uchess-source/microchess.asm')
    assert sha(image)=='8704eff78e177696383c496225408c47fb51a70a3b26b3f2a715e575cc61e066';(OUT/'uchess.a').write_bytes(source);expected=image[24:1463];assert len(expected)==1439
    freeze=json.loads((Q/'beta35-release-qualification-2026-10-17-034745Z/freeze.json').read_text());workspace=Path(freeze['frozen_source_directory'])
    os.environ.update(STR8_ASM_CANDIDATE='BUILD/v2-beta35-candidate',STR8_TEST_DEPS=str(workspace/'BUILD/test-deps'));sys.path.insert(0,str(workspace/'tools'))
    import serial
    def forbidden(*a,**k):raise RuntimeError('Board access forbidden in uChess example qualification')
    serial.Serial=forbidden
    import beta4_migration;beta4_migration.Link=forbidden
    import test_asm as asm
    from test_v2_status import boot,layout
    logs=[];checks=[]
    try:
        for slot in ('A','B'):
            cpu,m=asm.fixture(primary=layout());m.banks=[bytearray(b'\xff'*32768)]+[bytearray(image[n:n+32768]) for n in range(0,len(image),32768)]
            if slot=='B':m.banks[3][0x201f]=255
            m.spi.banks=m.banks;m.fast=True;m.bus.rtc_regs[:9]=bytes.fromhex('95 53 19 2F 18 10 26 00 0C')
            original=list(map(bytes,m.banks));retained=(bytes(m.spi.devices[0].data),bytes(m.bus.ee),bytes(m.bus.rtc_regs));boot(cpu);log=[]
            assert m.ram[0x7d30]==(0xa0 if slot=='A' else 0xb0)
            def cmd(text,raw=False):
                result=asm.command(cpu,text.encode()+(b'' if raw else b'\r'));log.append(dict(command=text,output=result.decode('ascii','replace')));return result
            assert b'ASM 0.5' in cmd('ASM');cmd('NEW');assert b'Paste source' in cmd('PASTE')
            result=asm.command(cpu,source.replace(b'\r\n',b'\n').replace(b'\n',b'\r')+b'.\r');assert b'Error' not in result
            assert b'OK 1439 bytes, origin $0200, buffer $0200' in cmd('ASM');assert bytes(m.ram[0x200:0x79f])==expected
            cmd('QUIT');assert b'UCHESS' in cmd('T 1');assert b'Done' in cmd('S 1 AUTO 0200 079E UCHDEMO')
            table=cmd('T 1');assert b'UCHDEMO' in table and b'UCHESS' in table and b'0200-079E' in table
            cmd('M 0200 EA');assert m.ram[0x200]==0xea
            assert b'Done' in cmd('R 1 UCHDEMO L');assert bytes(m.ram[0x200:0x79f])==expected
            cmd('D 0200 020F');assert b'Microchess Copyright 1976 Peter Jennings' in cmd('G 0200');assert b'B3>' in cmd('Q',True)
            assert b'Microchess Copyright' in cmd('R 1 UCHDEMO');assert b'B3>' in cmd('Q',True)
            after=list(map(bytes,m.banks));position=after[1].find(b'UCHDEMO\0')-8;assert position>=1463 and original[1][position:position+1463]==b'\xff'*1463
            assert after[1][:position]==original[1][:position] and after[1][position+1463:]==original[1][position+1463:]
            assert all(after[b]==original[b] for b in (0,2,3)) and not any(e[0]=='erase' for e in m.events)
            assert retained==(bytes(m.spi.devices[0].data),bytes(m.bus.ee),bytes(m.bus.rtc_regs)) and not m.bus.writes
            checks.append(dict(slot=slot,passed=True,actual_ASM_05_PASTE_and_assembly=True,executable_bytes=1439,source_name='uchess.a',source_sha256=sha(source),executable_sha256=sha(expected),store_command='S 1 AUTO 0200 079E UCHDEMO',table_command='T 1',load_only_command='R 1 UCHDEMO L',load_run_command='R 1 UCHDEMO',existing_UCHESS_preserved=True,all_other_flash_preserved=True,RTC_EEPROM_SRAM_preserved=True,flash_erases=0,record_CPU_address=0x8000+position));logs.append(dict(slot=slot,session=log));print('PASS MON',slot,'uchess.a ASM0.5, Store/Table/Restore, load-only/run and preserved devices',flush=True)
        (OUT/'report.json').write_text(json.dumps(dict(passed=True,checks=checks,published_zip_sha256=sha(published.read_bytes()),alias_source_byte_identical=True,model_only=True,board_access=False,soaks_and_RTC_sampling_stopped=True),indent=2)+'\n')
    except BaseException:(OUT/'failure.json').write_text(json.dumps(dict(passed=False,checks=checks,error=traceback.format_exc()),indent=2)+'\n');raise
    finally:(OUT/'transcripts.json').write_text(json.dumps(logs,indent=2)+'\n')
if __name__=='__main__':main()
