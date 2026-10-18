"""Audit draft links and run only newly documented examples, offline."""
import argparse,json,os,re,sys,traceback
from pathlib import Path
from datetime import datetime,timezone
import beta35_model_transactions as c
p=c.p

def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--out',required=True,type=Path);a=ap.parse_args();a.out.mkdir(parents=True,exist_ok=False)
    freeze=p.read(p.ROOT/'output/qualification/beta35-release-qualification-2026-10-17-034745Z/freeze.json');ws=Path(freeze['frozen_source_directory'])
    os.environ.update(STR8_ASM_CANDIDATE='BUILD/v2-beta35-candidate',STR8_RTC_BUILD='BUILD/v2-beta35-candidate',STR8_TEST_DEPS=str(ws/'BUILD/test-deps'));sys.path.insert(0,str(ws/'tools'))
    import serial
    def forbidden(*args,**kw):raise RuntimeError('No serial access in manual example audit')
    serial.Serial=forbidden
    import beta4_migration
    beta4_migration.Link=forbidden
    import test_asm as asm
    from test_v2_status import boot,layout,snapshot
    checks=[];transcripts=[]
    def check(name):checks.append(dict(name=name,passed=True));print('PASS',name,flush=True)
    try:
        links=[];docs={};sources={}
        for path in sorted((p.ROOT/'docs/beta35').glob('*.md')):
            text=path.read_text(encoding='utf-8');docs[str(path.relative_to(p.ROOT))]=p.sha(path.read_bytes())
            assert 'draft' in text.lower() and ('beta35' in text.lower() or '2.0b35' in text)
            for link in re.findall(r'\]\(([^)]+)\)',text):
                assert not re.match(r'[a-z]+:',link),link
                target=(path.parent/link.split('#')[0]).resolve();assert target.is_file(),(path,link);links.append(dict(document=str(path),link=link))
                if target.is_relative_to(p.ROOT/'release/beta35'):sources[str(target.relative_to(p.ROOT))]=p.sha(target.read_bytes())
        check('five draft documents: local links resolve and beta35/draft labeling present')
        guide=(p.ROOT/'docs/beta35/ASM_GUIDE.md').read_text(encoding='utf-8');sample=re.search(r'```asm\n(.*?)```',guide,re.S).group(1).strip().splitlines()
        assert sample==['10 ORG $0200','20 SEI','30 CLD',"40 LDA #'A'",'50 JSR $7E6D','60 JMP $7E67','70 END']
        # ASM's generic candidate fixture lacks a valid stored CLOCK record.
        # Use the receipt-bound complete 2512 transaction image for named-app
        # lookup, rather than bypassing the documented R CLOCK command.
        cp=p.read(c.EVIDENCE/'transaction-model-checkpoint.json');source=Path(cp['report']);assert p.sha(source.read_bytes())==cp['report_sha256']
        case=next(v for v in p.read(source)['checks'] if v['name']=='2512-complete');source_banks=[(source.parent/case['name']/f'b{i}.bin').read_bytes() for i in range(4)]
        assert p.bank_hashes(source_banks)==case['bank_sha256']
        cpu,m=asm.fixture(primary=layout());m.banks=list(map(bytearray,source_banks));m.spi.banks=m.banks;m.fast=True;m.bus.rtc_regs[:9]=bytes.fromhex('95 53 19 2E 17 10 26 80 00')
        binding=bytes(m.banks[3][0x1c00:0x1c20])
        if binding[:3]==b'EI\1' and binding[31]==0 and p.crc(binding[:28])==int.from_bytes(binding[28:30],'little'):m.bus.ee[0xf2:0xf8]=binding[8:14]
        before=snapshot(m);boot(cpu)
        assert snapshot(m)==before
        def command(line):
            out=asm.command(cpu,line.encode()+b'\r');transcripts.append((line,out.decode('ascii',errors='replace')));return out
        assert b'BATCH' in command('?');assert b'2.0b35' in command('VERSION');assert b'ASM installed B1:E000' in command('APPS')
        assert b'BATCH done' in command('BATCH APPS;VERSION');assert b'BATCH stopped: unsupported' in command('BATCH ASM;VERSION')
        check('documented monitor queries and BATCH APPS;VERSION; ASM batch refusal')
        assert b'CLOCK 1.10' in command('R CLOCK')
        for line in ['HELP','TIME','STATUS','EUI','HISTORY']:
            out=command(line);assert b'CLOCK> ' in out and b'Invalid command' not in out
        assert command('Q').endswith(b'B3> ');assert snapshot(m)==before
        check('CLOCK 1.10 documented query session returns with persistent devices unchanged')
        assert b'STR8-N ASM 0.5' in command('ASM')
        for line in sample:assert b'Error' not in command(line)
        listing=command('LIST');assert all(line.encode() in listing for line in sample)
        result=command('ASM');assert b'OK 10 bytes, origin $0200, buffer $0200' in result,result
        expected=bytes.fromhex('78 D8 A9 41 20 6D 7E 4C 67 7E');assert bytes(m.ram[0x200:0x20a])==expected
        assert b'0200: 78 D8 A9 41 20 6D 7E 4C' in command('DUMP')
        text=command('S19').decode();records=[l for l in text.splitlines() if re.fullmatch('S[19][0-9A-F]{8,}',l)];data={};entry=None
        for line in records:
            b=bytes.fromhex(line[2:]);assert len(b)==b[0]+1 and sum(b)&255==255
            address=int.from_bytes(b[1:3],'big')
            if line[1]=='1':data.update({address+i:v for i,v in enumerate(b[3:-1])})
            else:entry=address
        assert entry==0x200 and bytes(data[i] for i in range(0x200,0x20a))==expected
        (a.out/'asm-example.bin').write_bytes(expected);(a.out/'asm-example.s19').write_text('\n'.join(records)+'\n')
        check('exact manual numbered source assembles, lists, dumps and exports correct checked S-record bytes')
        assert command('QUIT').endswith(b'B3> ');out=command('G 0200');assert b'A' in out and out.endswith(b'B3> ')
        assert snapshot(m)==before and not m.events and not m.bus.writes
        check('documented G 0200 prints A and HOLD returns to monitor; persistent devices unchanged')
        assert b'ASM 0.5' in command('ASM');command('10 WAT');assert b'Unknown instruction or mode' in command('ASM')
        assert b'Assemble successfully first' in command('S19');command('NEW');assert b'Paste source' in command('PASTE')
        out=asm.command(cpu,b'ORG $0200\r\nNOP\r\n.\r\n');transcripts.append(('paste source + dot terminator',out.decode()));assert b'Error' not in out
        assert b'OK 1 bytes' in command('ASM') and m.ram[0x200]==0xea;command('QUIT')
        assert snapshot(m)==before and not m.events and not m.bus.writes
        check('invalid opcode blocks export; NEW and PASTE with dot terminator recover a valid source')
    except Exception:
        (a.out/'transcripts.json').write_text(json.dumps(transcripts,indent=2)+'\n')
        (a.out/'failure.json').write_text(json.dumps(dict(passed=False,checks=checks,error=traceback.format_exc()),indent=2)+'\n');raise
    (a.out/'transcripts.json').write_text(json.dumps(transcripts,indent=2)+'\n')
    result=dict(passed=True,cases=len(checks),checks=checks,document_sha256=docs,source_references_sha256=sources,links=links,
        example_bytes_hex=expected.hex(),example_origin=512,virtual_rtc='2026-10-17T19:53:15',
        test_sha256=p.sha(Path(__file__).read_bytes()),candidate_build_sha256=freeze['build_sha256'],source_report=str(source),source_report_sha256=cp['report_sha256'],source_bank_sha256=case['bank_sha256'],
        finished_utc=datetime.now(timezone.utc).isoformat(),serial_disabled=True,board_access=False,persistent_devices_unchanged=True,
        scope='New documented example and bounded help/query/editor sessions; not exhaustive semantics of every documented write form',
        release_qualified=False,installation_permitted=False)
    (a.out/'report.json').write_text(json.dumps(result,indent=2)+'\n');print('PASS',len(checks),'manual example/link checks')
if __name__=='__main__':main()
