"""Offline B3-only provisioning image boot/core/fallback checks; never opens serial."""
import hashlib,json,os,sys,traceback
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];Q=ROOT/'output/qualification';OUT=Q/'rc1-boot-core-model';sha=lambda b:hashlib.sha256(b).hexdigest()
def main():
    assert not OUT.exists();OUT.mkdir();image=(ROOT/'output/releases/rc1-2026-10-18-r1/firmware/str8n-2.0rc1-apps-str8n-only.bin').read_bytes();assert sha(image)=='8704eff78e177696383c496225408c47fb51a70a3b26b3f2a715e575cc61e066';core=image[0x10000:];assert len(core)==32768
    freeze=json.loads((Q/'beta35-release-qualification-2026-10-17-034745Z/freeze.json').read_text());workspace=Path(freeze['frozen_source_directory'])
    os.environ.update(STR8_ASM_CANDIDATE='BUILD/v2-beta35-candidate',STR8_TEST_DEPS=str(workspace/'BUILD/test-deps'));sys.path.insert(0,str(workspace/'tools'))
    import serial
    def forbidden(*a,**k):raise RuntimeError('Board ports forbidden in B3-core model')
    serial.Serial=forbidden
    import beta4_migration;beta4_migration.Link=forbidden
    import test_asm as asm
    from test_v2_status import boot,layout,snapshot
    checks=[];logs=[]
    try:
        for slot in ('A','B'):
            cpu,m=asm.fixture(primary=layout());m.banks=[bytearray(b'\xff'*32768) for _ in range(3)]+[bytearray(core)]
            if slot=='B':m.banks[3][0x201f]=255
            m.spi.banks=m.banks;m.fast=True;m.bus.rtc_regs[:9]=bytes.fromhex('95 53 19 2F 18 10 26 00 0C');before=snapshot(m);boot(cpu)
            assert m.ram[0x7d30]==(0xa0 if slot=='A' else 0xb0) and b'STR8-N 2.0rc1 B3' in m.tx
            commands={}
            for command in (b'?\r',b'D 0200 020F\r',b'W\r',b'T 1\r',b'APPS\r',b'J1\r',b'J2\r',b'J3\r'):
                text=asm.command(cpu,command);commands[command.decode().strip()]=text.decode('ascii','replace');assert text.endswith(b'B3> '),repr(text[-300:])
                if command in (b'J1\r',b'J2\r'):assert b'Bad vector' in text
            assert snapshot(m)==before and not m.events and not m.bus.writes
            checks.append(dict(name=slot+' B3-only boot/core commands, absent-provider admission, invalid bank-vector refusals and J3 restart',passed=True,persistent_model_devices_unchanged=True));logs.append(dict(slot=slot,commands=commands));print('PASS B3-only MON',slot,'boot/core/fallback and J vectors',flush=True)
        filename='str8n-2.0rc1-boot-core-b3.bin';(OUT/filename).write_bytes(core)
        result=dict(passed=True,filename=filename,bytes=len(core),sha256=sha(core),parent_app_image_sha256=sha(image),parent_offset=0x10000,full_device_offset=0x18000,CPU_range='B3:8000-FFFF',checks=checks,model_only=True,W65C02_execution=True,hardware_core_only_installation_tested=False,board_access=False,preserving_upgrade=False,generic_defaults=True,apps_and_B1_B2_not_included=True)
        (OUT/'report.json').write_text(json.dumps(result,indent=2)+'\n');(OUT/'transcripts.json').write_text(json.dumps(logs,indent=2)+'\n')
    except BaseException:(OUT/'failure.json').write_text(json.dumps(dict(passed=False,checks=checks,transcripts=logs,error=traceback.format_exc()),indent=2)+'\n');raise
if __name__=='__main__':main()
