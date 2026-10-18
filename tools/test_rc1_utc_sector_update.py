"""Execute the complete narrow updater and its refusal/return paths offline."""
import copy,hashlib,json,os,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];Q=ROOT/'output/qualification';RUN=Q/'rc1-utc-2609-2604-hardware-2026-10-18-r4';read=lambda p:json.loads(p.read_text())
def main():
    assert not (RUN/'CPU-report.json').exists();prep=read(RUN/'preparation.json');kit=Path(prep['package'])/'migration'
    sys.path.insert(0,str(kit));import runtime as r;import legacy_transport as wire
    freeze=read(Q/'beta35-release-qualification-2026-10-17-034745Z/freeze.json');ws=Path(freeze['frozen_source_directory']);os.environ.update(STR8_ASM_CANDIDATE='BUILD/v2-beta35-candidate',STR8_TEST_DEPS=str(ws/'BUILD/test-deps'));sys.path.insert(0,str(ws/'tools'))
    import serial
    def forbidden(*a,**k):raise RuntimeError('Board access forbidden in narrow updater test')
    serial.Serial=forbidden
    import beta4_migration;beta4_migration.Link=forbidden
    import test_asm as asm
    from test_v2_status import boot,layout,snapshot
    checks=[]
    for board in ('2609','2604'):
        info=read(RUN/board/'build.json');source=[(Path(info['source_reference']).parent/f'source-b{n}.bin').read_bytes() for n in range(4)]
        boot_cpu,m=asm.fixture(primary=layout());m.banks=list(map(bytearray,source));m.spi.banks=m.banks;m.fast=True;m.bus.rtc_regs[:9]=bytes.fromhex('95 53 19 2F 18 10 26 00 0C')
        # This test does not qualify the boot-menu timeout. Accelerate its
        # pure A/X delay loop only, reproducing its exact return registers.
        delay=read(ROOT/'tmp/ru3/symbols.json')['core/str8n-v2-worker']['V2W_BOOT_DELAY']
        def skip_delay(c):
            if c.pc!=delay:return False
            c.a=c.x=0;c.p=(c.p&~0x80)|2
            c.sp=(c.sp+1)&255;lo=c.memory[0x100+c.sp];c.sp=(c.sp+1)&255;hi=c.memory[0x100+c.sp];c.pc=(((hi<<8)|lo)+1)&65535
            return True
        boot(boot_cpu,hook=skip_delay)
        cases=('good-dynamic-journal','bad-static-firmware','bad-RAM-payload','bad-worker','no-valid-journal') if board=='2609' else ('good-dynamic-journal',)
        for case in cases:
            cpu=copy.deepcopy(boot_cpu);mem=cpu.memory
            if case=='good-dynamic-journal':
                seq,off,row,_=r.clean_journal(mem.banks);counts=[int.from_bytes(row[24+i*3:27+i*3],'little') for i in range(32)];counts[0]+=2
                mem.banks[3][off+128:off+256]=r.record(row[8:24],counts,seq+7)
                mem.banks[3][0x1FF0]=0xAA  # Mutable identity/settings tail must be preserved
            elif case=='bad-static-firmware':mem.banks[3][0x1040]^=1
            elif case=='bad-worker':mem.ram[0x7800]^=1
            elif case=='no-valid-journal':mem.banks[3][0x4000:0x6000]=b'\xff'*8192
            cells,entry=wire.read_s19(RUN/board/'updater.s19',max_end=0x6500)
            for a,v in cells.items():mem.ram[a]=v
            if case=='bad-RAM-payload':mem.ram[0x4010]^=1
            before=snapshot(mem);mem.events.clear();text=asm.command(cpu,b'G 2000\r')
            assert text.endswith(b'B3> '),'Updater must return to a usable monitor: '+repr(text[-200:])
            if case=='good-dynamic-journal':
                assert b'UTC UPDATE VERIFIED  [power-fail UTC]' in text,text
                assert bytes(mem.banks[3][:4096])==(kit/'payload/str8n-rtc-component-8000-8fff.bin').read_bytes()
                assert [bytes(b) for b in mem.banks[:3]]==before[0][:3]
                assert bytes(mem.banks[3][0x1000:0x4000])==before[0][3][0x1000:0x4000] and bytes(mem.banks[3][0x6000:])==before[0][3][0x6000:]
                assert [e for e in mem.events if e[0]=='erase']==[('erase',3,0x8000,255)]
                old=r.latest(before[0])[2];new=r.latest(mem.banks)[2];assert old[8:24]==new[8:24]
                for i in range(32):assert int.from_bytes(new[24+i*3:27+i*3],'little')==int.from_bytes(old[24+i*3:27+i*3],'little')+(i==24)
                assert snapshot(mem)[1:]==before[1:]
            else:
                assert (b'UTC UPDATE FAILED' if case=='no-valid-journal' else b'UTC UPDATE REFUSED; NO FLASH WRITE') in text,text
                assert snapshot(mem)==before and not mem.events
            assert b'2.0rc1' in asm.command(cpu,b'VERSION\r')
            (RUN/board/(case+'-model.txt')).write_bytes(text);checks.append(dict(board=board,case=case,passed=True,returns_to_monitor=True))
            (RUN/'CPU-progress.json').write_text(json.dumps(checks,indent=2)+'\n');print('PASS',board,case,flush=True)
    (RUN/'CPU-report.json').write_text(json.dumps(dict(passed=True,checks=checks,board_access=False,boot_delay_loop_only_accelerated=True,full_return_paths_tested=True,one_exact_wear_accounted_erase=True,mutable_identity_settings_preserved=True,source_build_hashes={b:read(RUN/b/'build.json')['s19_sha256'] for b in ('2609','2604')}),indent=2)+'\n')
if __name__=='__main__':main()
