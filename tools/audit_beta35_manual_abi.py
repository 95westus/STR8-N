"""Owner-local frozen-model manual audit; never imports a live serial link."""
import argparse,json,os,re,sys,traceback
from pathlib import Path
from datetime import datetime,timezone
import beta35_model_transactions as c
p=c.p
def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--out',required=True,type=Path);a=ap.parse_args();a.out.mkdir(parents=True,exist_ok=False)
    freeze=p.read(p.ROOT/'output/qualification/beta35-release-qualification-2026-10-17-034745Z/freeze.json');ws=Path(freeze['frozen_source_directory'])
    os.environ.update(STR8_ASM_CANDIDATE='BUILD/v2-beta35-candidate',STR8_TEST_DEPS=str(ws/'BUILD/test-deps'));sys.path.insert(0,str(ws/'tools'))
    import serial
    def forbidden(*args,**kw):raise RuntimeError('Live serial forbidden in manual audit')
    serial.Serial=forbidden
    import beta4_migration
    beta4_migration.Link=forbidden
    import test_asm as asm
    from test_v2_status import boot,layout,snapshot
    checks=[];transcripts=[];sources={}
    def read_source(name):
        path=p.ROOT/'release/beta35/source'/name;sources[str(path.relative_to(p.ROOT))]=p.sha(path.read_bytes());return path.read_text()
    def passed(name,**kw):checks.append(dict(name=name,passed=True,**kw));print('PASS',name,flush=True)
    def command(cpu,line):
        keys=line.encode()+b'\r' if isinstance(line,str) else line;out=asm.command(cpu,keys);transcripts.append(dict(keys=repr(keys),output=out.decode('ascii',errors='replace')));return out
    try:
        docs={path.name:path.read_text(encoding='utf-8') for path in (p.ROOT/'docs/beta35').glob('*.md')};links=[]
        for name,text in docs.items():
            for link in re.findall(r'\]\(([^)]+)\)',text):
                assert not re.match(r'[a-z]+:',link);assert (p.ROOT/'docs/beta35'/link.split('#')[0]).is_file();links.append((name,link))
        passed('all local manual links resolve',links=len(links))
        public=read_source('assembler/str8n-v2-public.inc');eq=dict((k,int(v,16)) for k,v in re.findall(r'^(\w+)\s+EQU\s+\$([0-9A-F]+)',public,re.M))
        for label,address in [('PUTC',0x7e6d),('GETC',0x7e70),('HEX_OUT',0x7e7c),('NEWLINE',0x7e7f),('CAPS_QUERY',0x7e85),('BOARD_QUERY',0x7e88),('HOLD',0x7e67),('RESET',0x7e64)]:
            assert eq['STR8V2_RAM_'+label]==address and f'{label} ${address:04X}' in docs['ASM_GUIDE.md'];passed('documented RAM ABI address '+label,address=address)
        assert eq['STR8V2_RAM_CALLS']==13 and eq['STR8V2_RAM_SIGNATURE']==0x7e60 and eq['STR8V2_CAPS_FLAGS']==0x17
        assert 'E=1, D=0, DBR=0, PBR=0' in public and 'native-mode calls' in public;passed('ABI signature/count/capability and emulation-only contract')
        layout_source=read_source('assembler/layout.inc');sizes=dict((k,int(v,16)) for k,v in re.findall(r'^(\w+)\s+EQU\s+\$([0-9A-F]+)',layout_source,re.M))
        assert [sizes[k] for k in ['OUTPUT_START','OUTPUT_END','SOURCE_START','SOURCE_END','SYMBOL_START','SYMBOL_END','STATE_END']]==[0x200,0x3300,0x3300,0x4f00,0x4f00,0x6300,0x6500]
        for text in ['$0200–$32FF','$3300–$4EFF','$4F00–$62FF','$6300–$64FF']:assert text in docs['ASM_GUIDE.md']
        passed('ASM buffers, logical origin and physical output bounds')
        service=read_source('core/service-eq.inc');assert 'SVC_DESC EQU $7D04' in service and 'SVC_ACTIVE EQU $7D0C' in service
        assert '$7D04' in docs['TECHNICAL_MANUAL.md'] and '$7D0C' in docs['TECHNICAL_MANUAL.md'];passed('optional service descriptor and reset-latched RAM reservation')
        flash=read_source('core/str8n-v2-flash.inc');assert 'F preflights one sector, snapshots it, prints old/new bytes, then confirms' in flash
        assert 'not RAM fill' in docs['COMMAND_REFERENCE.md'] and 'not a RAM fill' in docs['USER_GUIDE.md'];passed('F corrected to confirmed single-sector flash patch')
        core=read_source('core/monitor-b0.asm');assert 'V2_COMMAND_J:' in core and 'JSR     V2_WORKER' in core and 'V2_COMMAND_P:' in core
        utilities=read_source('xip/utilities.asm');assert 'B29_NATIVE_NAMES DB "MAINT",0,"SRAM",0,"WORK",0,"EDU",0' in utilities
        clock=read_source('clock/clock.asm');assert 'TITLE DB "CLOCK 1.10"' in clock and 'TRIM -127..+127' in clock
        outage=read_source('clock/outage-duration.inc');assert 'Yearless PF pair' in outage and 'no seconds or lifetime claim' in outage
        passed('command contexts, clock version, outage year/minute limits and write effects source audit')
        priorcp=p.read(c.EVIDENCE/'manual-drafts-checkpoint.json');prior=Path(priorcp['report']);assert p.sha(prior.read_bytes())==priorcp['report_sha256'];old=p.read(prior);assert old['passed']
        # Source example is unchanged; reuse its linked assembly/export/execution
        # instead of rerunning those passed cases after prose-only corrections.
        block=re.search(r'```asm\n(.*?)```',docs['ASM_GUIDE.md'],re.S).group(1)
        assert block.strip().splitlines()==['10 ORG $0200','20 SEI','30 CLD',"40 LDA #'A'",'50 JSR $7E6D','60 JMP $7E67','70 END']
        assert old['example_bytes_hex']=='78d8a941206d7e4c677e';passed('unchanged ten-byte example reuses pinned assembly/S19/execution receipt',receipt_sha256=priorcp['report_sha256'])
        bank_source=Path(old['source_report']);assert p.sha(bank_source.read_bytes())==old['source_report_sha256'];folder=bank_source.parent/'2512-complete';banks=[(folder/f'b{i}.bin').read_bytes() for i in range(4)];assert p.bank_hashes(banks)==old['source_bank_sha256']
        cpu,m=asm.fixture(primary=layout());m.banks=list(map(bytearray,banks));m.spi.banks=m.banks;m.fast=True;m.bus.rtc_regs[:9]=bytes.fromhex('95 53 19 2E 17 10 26 80 00')
        before=snapshot(m);boot(cpu);assert snapshot(m)==before
        assert bytes(m.ram[0x7e60:0x7e64])==b'RA\1\r' and bytes(m.ram[0x7d04:0x7d07])==b'SV\1' and m.ram[0x7d0a:0x7d0c]==bytes.fromhex('ff64')
        passed('boot initialized RA descriptor and active EDU application limit')
        for bank in range(4):
            m.bank=bank;cpu.p=(cpu.p|4)&~8;sp=cpu.sp
            assert asm.model.call(cpu,0x7e85) and (cpu.a,cpu.x,cpu.y)==(1,0x17,4) and cpu.sp==sp
            assert asm.model.call(cpu,0x7e88) and cpu.a==1 and cpu.x==2 and cpu.y&1 and cpu.sp==sp
            m.rx.extend(b'Z');asm.model.call(cpu,0x7e70);assert cpu.a==ord('Z') and cpu.sp==sp
            cpu.a=ord('!');start=len(m.tx);asm.model.call(cpu,0x7e6d);assert bytes(m.tx[start:])==b'!' and cpu.sp==sp
            passed('RAM query/GETC/PUTC calls execute with flash bank '+str(bank)+' selected',persistent_state_unchanged=snapshot(m)==before)
        m.bank=3;cpu.pc=0x7e67;boot(cpu)
        assert b'ASM 0.5' in command(cpu,'ASM');command(cpu,'NEW');assert b'Paste source' in command(cpu,'PASTE')
        assert b'Cancelled' in command(cpu,b'NOP\r\x03');assert b'OK 1 bytes' in command(cpu,'ASM') and m.ram[0x200]==0xea
        command(cpu,'QUIT');passed('Ctrl-C cancels paste and preserves already accepted line')
        assert b'Type YES' in command(cpu,'BATCH MAINT;NAME TEST;Q');assert b'BATCH canceled' in command(cpu,b'\x1b');assert command(cpu,'Q').endswith(b'B3> ')
        passed('Escape cancels BATCH confirmation and drops queued Q; manual Q returns')
        assert b'BATCH stopped: command failed' in command(cpu,'BATCH SRAM;BOGUS;Q');assert command(cpu,'Q').endswith(b'B3> ')
        assert snapshot(m)==before and not m.events and not m.bus.writes;passed('native command error stops batch with every persistent fake device unchanged')
    except Exception:
        (a.out/'transcripts.json').write_text(json.dumps(transcripts,indent=2)+'\n');(a.out/'failure.json').write_text(json.dumps(dict(passed=False,checks=checks,error=traceback.format_exc()),indent=2)+'\n');raise
    model_sources={}
    for mod in list(sys.modules.values()):
        path=Path(getattr(mod,'__file__','') or '.')
        if path.is_file() and path.suffix=='.py' and path.resolve().is_relative_to(ws.resolve()):
            name=path.resolve().relative_to(ws).as_posix();digest=p.sha(path.read_bytes());model_sources[name]=digest
            if name in freeze['source_files']:assert digest==freeze['source_files'][name]
    result=dict(passed=True,cases=len(checks),checks=checks,documents={n:p.sha((p.ROOT/'docs/beta35'/n).read_bytes()) for n in docs},source_references=sources,
        reused_example_report=str(prior),reused_example_report_sha256=priorcp['report_sha256'],model_sources=model_sources,
        test_sha256=p.sha(Path(__file__).read_bytes()),finished_utc=datetime.now(timezone.utc).isoformat(),
        model_only=True,serial_disabled=True,board_access=False,persistent_model_devices_unchanged=True,installation_permitted=False,release_qualified=False,
        scope='All current manual claims reviewed against source; bounded live instruction-model ABI/cancel/error extension plus exact unchanged example proof. No native 816 or electrical qualification.')
    (a.out/'transcripts.json').write_text(json.dumps(transcripts,indent=2)+'\n');(a.out/'report.json').write_text(json.dumps(result,indent=2)+'\n');print('PASS',len(checks),'manual/ABI audit checks')
if __name__=='__main__':main()
