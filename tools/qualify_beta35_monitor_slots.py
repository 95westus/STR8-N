"""Serial-disabled model qualification of the separately built beta35 A slot.

No frozen candidate files are changed. All monitor and canonical payload
overlays exist only inside emulator memory; persistent state is snapshotted.
"""
import argparse
from datetime import datetime,timezone
import hashlib
import json
import os
from pathlib import Path
import sys
import traceback

ROOT=Path(__file__).resolve().parents[1]
sha=lambda data:hashlib.sha256(data).hexdigest()
read=lambda path:json.loads(path.read_text())


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--build',type=Path,required=True);p.add_argument('--out',type=Path,required=True);args=p.parse_args()
    args.out.mkdir(parents=True,exist_ok=False)
    extension=read(args.build/'build-report.json');assert extension['passed'] and extension['B_matches_frozen_payload']
    freeze=read(ROOT/'output/qualification/beta35-release-qualification-2026-10-17-034745Z/freeze.json')
    workspace=Path(freeze['frozen_source_directory'])
    os.environ.update(STR8_RTC_BUILD='BUILD/v2-beta35-candidate',STR8_TEST_DEPS=str(workspace/'BUILD/test-deps'))
    sys.path.insert(0,str(workspace/'tools'))
    import serial
    def forbidden(*a,**kw):raise RuntimeError('Serial hardware forbidden in offline slot qualification')
    serial.Serial=forbidden
    import beta4_migration as migration
    migration.Link=forbidden
    from test_v2_status import fresh,boot,layout,snapshot,META
    from test_v2_sram_store import console
    assets=ROOT/'tmp/c35e/payload';release=read(ROOT/'release/beta35/release.json')
    assert sha((workspace/'BUILD/v2-beta35-candidate/build.json').read_bytes())==freeze['build_sha256']
    for name,info in release['expected'].items():assert sha((assets/name).read_bytes())==info['sha256']
    slotA=(args.build/'str8n-v2-beta35-slot-a0.bin').read_bytes()
    slotB=(args.build/'str8n-v2-beta35-slot-b0.bin').read_bytes()
    for name,info in extension['artifacts'].items():assert sha((args.build/name).read_bytes())==info['sha256']
    oldA=(ROOT/'BUILD/v2-beta28-b23/str8n-v2-recovery-slot-a0.bin').read_bytes()
    oldB=(ROOT/'BUILD/v2-beta34-candidate/str8n-v2-recovery-slot-b0.bin').read_bytes()
    slots={'A35':slotA,'B35':slotB,'A28':oldA,'B34':oldB}
    selected=[];checks=[]

    def record(label,**details):
        checks.append(dict(name=label,passed=True,**details));print('PASS',label,flush=True)
        (args.out/'progress.json').write_text(json.dumps(checks,indent=2)+'\n')

    def fixture(a,b,preferred,generation,damage=None):
        cpu,m=fresh(primary=layout());m.fast=True
        for bank,address,name,count in [
            (1,0xB000,'clock/storage.bin',12288),(1,0xE000,'assembler/asm-e000.bin',4096),
            (1,0xF000,'assembler/vectors-f000.bin',4096),(2,0x8000,'xip/utilities.bin',22528),
            (2,0xD800,'boot-status/asset.bin',2560),(2,0xE200,'battery/asset.bin',2560),
            (2,0xF000,'local-display/asset.bin',1792),(2,0xF800,'version/asset.bin',2048),
            (3,0x8000,'str8n-rtc-component-8000-8fff.bin',4096),(3,0x9000,'str8n-journal-9000-9fff.bin',3072),
            (3,0xE000,'str8n-v2-recovery-e000-efff.bin',4096),(3,0xF000,'str8n-v2-recovery-f000-ffff.bin',4096)]:
            data=(assets/name).read_bytes()[:count];m.banks[bank][address-0x8000:address-0x8000+count]=data
        m.banks[3][0x2000:0x3000]=slots[a];m.banks[3][0x3000:0x4000]=slots[b]
        config=bytearray(migration.default_config());config[7:13]=b'P'+bytes([preferred])+generation.to_bytes(4,'little');config[14:]=migration.config_sum(config)
        m.banks[3][0x4000:0x6000]=migration.metadata(config,[0]*32,1)+b'\xff'*(8192-128)
        if damage:
            page,kind=damage;off=(page-0x80)*256;image=bytearray(m.banks[3][off:off+4096])
            if kind=='crc':image[128]^=1
            if kind=='uncommitted':image[31]=255
            if kind=='abi':
                image[20]^=1;image[18:20]=migration.crc(image[:18]+image[32:]).to_bytes(2,'little')
            m.banks[3][off:off+4096]=image
        return cpu,m

    def command(cpu,m,line):
        reply=console(cpu,m,line,limit=100000000)
        with (args.out/'commands.txt').open('ab') as log:log.write(reply)
        return reply

    def exercise(label,a,b,preferred,generation,wanted_page,wanted_version,*,damage=None,full=False,recovery=None):
        cpu,m=fixture(a,b,preferred,generation,damage);before=snapshot(m);transcript=bytearray()
        if recovery:
            sent=[False]
            def hook(c):
                if not sent[0] and c.pc==META['boot']['BOOT_RECOVERY_WINDOW']:
                    m.rx.extend(b'S');sent[0]=True
                return False
            boot(cpu,hook=hook);assert sent[0] and b'FIXED F RECOVERY' in m.tx
            transcript.extend(m.tx)
            text=command(cpu,m,(recovery+'\r').encode());assert b'B3> ' in text;transcript.extend(text)
        else:
            boot(cpu);transcript.extend(m.tx)
        assert m.ram[0x7D30]==wanted_page,(label,hex(m.ram[0x7D30]),bytes(m.tx[-400:]))
        reply=command(cpu,m,b'VERSION\r');transcript.extend(reply);assert wanted_version.encode() in reply,(label,reply)
        reply=command(cpu,m,b'TIME\r');transcript.extend(reply);assert b'2026-10-08 19:53:15 (+00:00)' in reply,reply
        if full:
            reply=command(cpu,m,b'BATCH APPS;VERSION\r');transcript.extend(reply)
            assert b'BATCH done' in reply and b'2.0b35' in reply and b'ASM installed B1:E000' in reply,reply
            reply=command(cpu,m,b'BATCH ASM;VERSION\r');transcript.extend(reply)
            assert b'BATCH stopped: unsupported' in reply and b'ASM>' not in reply,reply
            reply=command(cpu,m,b'BATCH MAINT;Q;SRAM;Q;WORK;Q;EDU;Q\r');transcript.extend(reply)
            if wanted_page==0xA0:
                assert reply.endswith(b'BM> ') and b'BATCH done' not in reply,reply
                transcript.extend(command(cpu,m,b'Q\r'))
            else:
                assert b'BATCH done' in reply and reply.endswith(b'B3> '),reply
            reply=command(cpu,m,b'R CLOCK\r');transcript.extend(reply);assert b'CLOCK 1.10' in reply
            for line in [b'STATUS\r',b'STATS\r',b'TRIM\r',b'OFFSET\r',b'Q\r']:transcript.extend(command(cpu,m,line))
            reply=command(cpu,m,b'ASM\r');transcript.extend(reply);assert b'ASM 0.5' in reply
            for line in [b'NEW\r',b'10 ORG $0200\r',b"20 LDA #'X'\r",b'30 JSR $7E6D\r',b'40 JMP $7E67\r',b'ASM\r']:
                reply=command(cpu,m,line);transcript.extend(reply)
            assert b'OK 8 bytes' in reply,reply
            transcript.extend(command(cpu,m,b'QUIT\r'))
            reply=command(cpu,m,b'G 0200\r');transcript.extend(reply);assert b'X' in reply and reply.endswith(b'B3> ')
        assert snapshot(m)==before,(label,'Persistent state changed')
        assert not m.events and not m.bus.writes,(label,m.events,m.bus.writes)
        assert m.ram[0x7D04:0x7D0C]==b'SV\x01\x0f\0\x65\xff\x64'
        assert m.ram[0x66AE]==1
        (args.out/(label+'.txt')).write_bytes(transcript)
        record(label,selected_page=wanted_page,version=wanted_version,persistent_state_unchanged=True,full_foreground_checks=full)

    try:
        exercise('A35-B34-default-A','A35','B34',0xA0,47,0xA0,'2.0b35',full=True)
        exercise('A35-B34-default-B','A35','B34',0xB0,46,0xB0,'2.0b34')
        exercise('A28-B35-default-A','A28','B35',0xA0,40,0xA0,'2.0b28')
        exercise('A28-B35-default-B','A28','B35',0xB0,47,0xB0,'2.0b35',full=True)
        exercise('A35-B35-default-A','A35','B35',0xA0,47,0xA0,'2.0b35')
        exercise('A35-B35-default-B','A35','B35',0xB0,47,0xB0,'2.0b35')
        exercise('bad-A-CRC-fallback-B','A35','B34',0xA0,47,0xB0,'2.0b34',damage=(0xA0,'crc'))
        exercise('bad-B-CRC-fallback-A','A35','B35',0xB0,47,0xA0,'2.0b35',damage=(0xB0,'crc'))
        exercise('uncommitted-A-fallback-B','A35','B34',0xA0,47,0xB0,'2.0b34',damage=(0xA0,'uncommitted'))
        exercise('wrong-A-ABI-fallback-B','A35','B34',0xA0,47,0xB0,'2.0b34',damage=(0xA0,'abi'))
        exercise('fixed-F-return-A35','A35','B34',0xA0,47,0xA0,'2.0b35',recovery='A')
        exercise('fixed-F-return-B34','A35','B34',0xA0,47,0xB0,'2.0b34',recovery='B')
    except Exception:
        (args.out/'failure.json').write_text(json.dumps(dict(passed=False,checks=checks,error=traceback.format_exc()),indent=2)+'\n')
        raise
    model_files={}
    for module in list(sys.modules.values()):
        path=Path(getattr(module,'__file__','') or '.')
        if path.is_file() and path.suffix=='.py' and path.resolve().is_relative_to(workspace):
            rel=path.resolve().relative_to(workspace).as_posix();digest=sha(path.read_bytes());model_files[rel]=digest
            if rel in freeze['source_files']:assert digest==freeze['source_files'][rel]
    report=dict(passed=True,slot_extension_qualified=False,
        finding='QA35-004: frozen native utility BATCH handoff requires BOOT_ACTIVE B0; A35 stops at MAINT prompt instead of consuming queued Q',
        version='2.0b35',generation=47,checks=checks,cases=len(checks),
        finished_utc=datetime.now(timezone.utc).isoformat(),board_access=False,serial_disabled=True,
        native_816_execution_qualified=False,installation_permitted=False,release_qualified=False,
        model_sources=model_files,slot_extension_build_report_sha256=sha((args.build/'build-report.json').read_bytes()),
        artifacts=extension['artifacts'],harness_sha256=sha(Path(__file__).read_bytes()),
        scope='Separate A35 monitor model prerequisite only; installer/converter and hardware gates remain open')
    (args.out/'report.json').write_text(json.dumps(report,indent=2)+'\n')
    print('PASS',len(checks),'slot/model scenarios; no board access or installation authorization')


if __name__=='__main__':main()
