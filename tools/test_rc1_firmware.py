"""Run actual rc1 full-image MON A/B identity, app and BATCH instructions offline."""
import hashlib,json,os,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];Q=ROOT/'output/qualification';OUT=Q/'rc1-firmware-model';sha=lambda b:hashlib.sha256(b).hexdigest()
def main():
    OUT.mkdir(exist_ok=False);image=(ROOT/'output/releases/rc1-2026-10-18-r1/firmware/str8n-2.0rc1-apps-str8n-only.bin').read_bytes()
    freeze=json.loads((Q/'beta35-release-qualification-2026-10-17-034745Z/freeze.json').read_text());ws=Path(freeze['frozen_source_directory'])
    os.environ.update(STR8_ASM_CANDIDATE='BUILD/v2-beta35-candidate',STR8_TEST_DEPS=str(ws/'BUILD/test-deps'));sys.path.insert(0,str(ws/'tools'))
    import serial
    def forbidden(*a,**k):raise RuntimeError('No board access in rc1 qualification')
    serial.Serial=forbidden
    import beta4_migration;beta4_migration.Link=forbidden
    import test_asm as asm
    from test_v2_status import boot,layout,snapshot
    checks=[];logs=[]
    for slot in ('A','B'):
        cpu,m=asm.fixture(primary=layout());m.banks=[bytearray(b'\xff'*32768)]+[bytearray(image[n:n+32768]) for n in range(0,len(image),32768)]
        if slot=='B':m.banks[3][0x201f]=255
        m.spi.banks=m.banks;m.fast=True;m.bus.rtc_regs[:9]=bytes.fromhex('95 53 19 2F 18 10 26 00 0C');before=snapshot(m);boot(cpu)
        assert m.ram[0x7d30]==(0xa0 if slot=='A' else 0xb0) and b'STR8-N 2.0rc1 B3' in m.tx
        def cmd(text):
            out=asm.command(cpu,text if isinstance(text,bytes) else text.encode()+b'\r');logs.append(dict(slot=slot,command=str(text),output=out.decode('ascii','replace')));return out
        version=cmd('VERSION');assert b'2.0rc1' in version and b'00000031' in version,version
        assert b'UCHESS' in cmd('T 1');assert b'ASM' in cmd('APPS')
        for text in ('BATCH MAINT;Q;SRAM;Q;WORK;Q;EDU;Q','BATCH R CLOCK;STATUS;Q'):
            out=cmd(text);assert b'BATCH done' in out and out.endswith(b'B3> ')
        assert b'Microchess Copyright 1976 Peter Jennings' in cmd('R 1 UCHESS');assert b'B3>' in cmd(b'Q')
        assert snapshot(m)==before and not m.events and not m.bus.writes
        checks.append(dict(slot=slot,passed=True,version='2.0rc1',generation=49,apps_and_native_utility_CLOCK_BATCH_passed=True,UCHESS_copyright_displayed=True,persistent_devices_unchanged=True))
        print('PASS rc1 MON',slot,'generation 49, all utility/CLOCK BATCH, UCHESS and preserved devices',flush=True)
    (OUT/'transcripts.json').write_text(json.dumps(logs,indent=2)+'\n');(OUT/'report.json').write_text(json.dumps(dict(passed=True,checks=checks,image_sha256=sha(image),board_access=False,rc1_hardware_tested=False),indent=2)+'\n')
if __name__=='__main__':main()
