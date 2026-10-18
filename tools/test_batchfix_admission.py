"""Execute linked CLOCK-name and registered-app predicates without boot/ports."""
import argparse,json,os,sys,hashlib
from pathlib import Path
from datetime import datetime,timezone
ROOT=Path(__file__).resolve().parents[1];sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--build',required=True,type=Path);ap.add_argument('--report',required=True,type=Path);a=ap.parse_args()
    freeze=json.loads((ROOT/'output/qualification/beta35-release-qualification-2026-10-17-034745Z/freeze.json').read_text());ws=Path(freeze['frozen_source_directory'])
    os.environ.update(STR8_RTC_BUILD='BUILD/v2-beta35-candidate',STR8_TEST_DEPS=str(ws/'BUILD/test-deps'));sys.path.insert(0,str(ws/'tools'))
    import serial
    def forbidden(*args,**kwargs):raise RuntimeError('Serial forbidden in admission tests')
    serial.Serial=forbidden
    import beta4_migration
    beta4_migration.Link=forbidden
    from test_v2_status import fresh,layout,snapshot
    from test_v2_spi_resident import k
    build=json.loads((a.build/'build-report.json').read_text());sy=json.loads((a.build/'symbols.json').read_text())['xip/utilities'];image=(a.build/'payload/xip/utilities.bin').read_bytes()
    assert sha(a.build/'payload/xip/utilities.bin')==build['artifacts']['xip/utilities.bin']['sha256']
    cpu,m=fresh(primary=layout());m.banks[2][:len(image)]=image;m.bank=2;before=snapshot(m);checks=[]
    for line,wanted in [('R CLOCK',True),('R 1 CLOCK',True),('R   CLOCK  ',True),('R 1   CLOCK ',True),('R 2 CLOCK',False),('R 3 CLOCK',False),('R CLOCKX',False),('R CLOCK ARGS',False),('R ASM',False),('R 1CLOCK',False),('R 1 CLOCKX',False),('R ',False)]:
        m.ram[0x7c00:0x7c40]=bytes(64);m.ram[0x7c00:0x7c00+len(line)]=line.encode();sp=cpu.sp
        assert k.model.call(cpu,sy['BFX_CLOCK_RUN'])==wanted and cpu.sp==sp,line
        checks.append(dict(name=line,accepted=wanted,passed=True))
    for page in [0xa0,0xb0]:
        for badbyte in [None,0,1,2,3,4,5]:
            m.ram[0x7d30]=page;m.ram[0x7ef4]=0xba;m.ram[0x7c94]=0xa9;m.ram[0x7c9f]=0x8d;m.ram[0x7ee4]=1;m.ram[0x7ee7]=0
            m.ram[0xfe:0x100]=bytes.fromhex('0020');m.ram[0x2000:0x2006]=bytes.fromhex('800442540101')
            if badbyte is not None:m.ram[0x2000+badbyte]^=1
            assert k.model.call(cpu,sy['B29_APP_CHECK'])==(badbyte is None),(page,badbyte)
            if badbyte is not None:assert m.ram[0x7ee7]==1
            checks.append(dict(name=f'{page:02X} app header byte {badbyte}',accepted=badbyte is None,passed=True))
    assert snapshot(m)==before and not m.events and not m.bus.writes
    a.report.parent.mkdir(parents=True,exist_ok=True);a.report.write_text(json.dumps(dict(passed=True,candidate_id='batchfix-r1',cases=len(checks),checks=checks,source_build_report_sha256=sha(a.build/'build-report.json'),test_sha256=sha(Path(__file__)),finished_utc=datetime.now(timezone.utc).isoformat(),model_only=True,serial_disabled=True,board_access=False,persistent_devices_unchanged=True),indent=2)+'\n');print('PASS',len(checks),'linked admission/refusal checks')
if __name__=='__main__':main()
