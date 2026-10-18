"""Remove only exact SDEMO flash records through verified BANK MAINT edits."""
import argparse,hashlib,json,re,os
from pathlib import Path
import migrate_v2 as u
import upgrade_v2_fleet as fleet
from beta4_migration import Link
from serial_test_coordination import serial_lease
from rtc_prompt_sync import establish_b3

BOARDS=('2205','2512','2604','2609')

def records(image):
    i=0
    while i+24<=len(image):
        h=image[i:i+24];size=int.from_bytes(h[6:8],'little');entry=int.from_bytes(h[4:6],'little')
        if h[:4]==b'SR\1\x3f' and size and 0x200<=entry and entry+size<=0x6700 and i+24+size<=len(image):
            yield i,size,h[8:24].rstrip(b'\0');i+=24+size
        else:i+=1

def inspect(base):
    for board in BOARDS:
        fleet.inventory(base,[board]);root=base/board
        banks=[(root/f'prior-verified/b{i}.bin').read_bytes() for i in range(4)]
        found=[dict(bank=b,address=0x8000+i,size=n+24) for b in range(4) for i,n,name in records(banks[b]) if name==b'SDEMO']
        with serial_lease('remove-sdemo-inspect'),(root/'tables-serial.jsonl').open('x') as log:
            l=Link(fleet.port(board),log)
            try:
                establish_b3(l);text=b''.join(l.command(f'T {b}') for b in range(4));(root/'tables-before.txt').write_bytes(text)
                assert (b'SDEMO' in text)==bool(found),'Record scan and monitor table disagree'
                descriptor=l.dump(0x7D04,0x7D0B)
                if descriptor[:4]==b'SV\1\x0f':
                    l.command('R SRAM',b'SRAM> ');text=l.command('T',b'SRAM> ');l.command('Q');(root/'sram-table-before.txt').write_bytes(text)
                    assert b'SDEMO' not in text,'External SRAM SDEMO needs its own complete retained-array backup before deletion'
                else:text=b'Services unavailable; external SRAM not inspected'
                clock=None
                if descriptor[:4]==b'SV\1\x0f':
                    l.command('R CLOCK',b'CLOCK> ')
                    clock={c:l.command(c,b'CLOCK> ').hex() for c in ('HISTORY','TRIM','EUI')};l.command('Q')
                (root/'retained-clock-before.json').write_text(json.dumps(clock,indent=2)+'\n')
            finally:l.serial.close()
        assert all(row['bank'] in (0,1,2) for row in found),'SDEMO unexpectedly in protected firmware bank'
        sectors={}
        for row in found:
            start=row['address']-0x8000;end=start+row['size']
            for i in range(start//4096,end//4096+1 if end%4096 else end//4096):
                sectors.setdefault((row['bank'],i),bytearray(banks[row['bank']][i*4096:(i+1)*4096]))
                a=max(start,i*4096)-i*4096;z=min(end,(i+1)*4096)-i*4096;sectors[row['bank'],i][a:z]=b'\xff'*(z-a)
        edits=[]
        for (bank,idx),data in sorted(sectors.items()):
            path=root/f'expected-b{bank}-{idx+8:X}.bin';path.write_bytes(data)
            edits.append(dict(bank=bank,sector=idx+8,expected_sha256=hashlib.sha256(data).hexdigest()))
        plan=dict(board=board,records=found,edits=edits,build=u.read(root/'source.json')['source_build'],sram_sdemo_found=False)
        (root/'removal-plan.json').write_text(json.dumps(plan,indent=2)+'\n')
        print('SDEMO',board,found,'sector edits',len(edits),flush=True)

def commands(plan,edit):
    bank,sector=edit['bank'],edit['sector'];start=sector*4096
    fills=[]
    for row in plan['records']:
        if row['bank']!=bank:continue
        a=max(start,row['address']);z=min(start+4096,row['address']+row['size'])
        if a<z:fills.append(f'F {a-start:X}-{z-start-1:X} FF')
    assert fills
    return [f'R {bank} {sector:X}']+fills

def rehearse(root):
    plan=u.read(root/'removal-plan.json');os.environ['STR8_RTC_BUILD']=plan['build']
    from test_v2_status import fresh,boot,snapshot
    from test_v2_storage import cmd
    prior=[(root/f'prior-verified/b{i}.bin').read_bytes() for i in range(4)]
    c,m=fresh();m.banks=[bytearray(b) for b in prior];m.spi.banks=m.banks;boot(c)
    before=snapshot(m);assert b'BM>' in cmd(c,m,b'R MAINT\r');confirmations=[]
    for edit in plan['edits']:
        for command in commands(plan,edit):cmd(c,m,(command+'\r').encode())
        expected=(root/f"expected-b{edit['bank']}-{edit['sector']:X}.bin").read_bytes()
        assert bytes(m.ram[0x5000:0x6000])==expected,'Buffered deletion mismatch'
        text=cmd(c,m,f"W {edit['bank']} {edit['sector']:X}\rY\r".encode());assert b'VERIFIED' in text,text
        token=b'WRITE? TYPE Y> ';assert token in text
        confirmations.append((text.split(token)[0]+token).hex())
        i=(edit['sector']-8)*4096;assert bytes(m.banks[edit['bank']][i:i+4096])==expected
    cmd(c,m,b'Q\r');expected=[bytearray(b) for b in prior]
    for edit in plan['edits']:
        i=(edit['sector']-8)*4096;expected[edit['bank']][i:i+4096]=(root/f"expected-b{edit['bank']}-{edit['sector']:X}.bin").read_bytes()
    actual=[bytearray(b) for b in m.banks]
    actual[3][0x4000:0x6000]=expected[3][0x4000:0x6000]
    assert actual==expected,'Unrelated flash mutation'
    assert snapshot(m)[1:]==before[1:],'Retained device mutation'
    a=u.m.journal(prior[3]);b=u.m.journal(m.banks[3]);counts=[int.from_bytes(a[24+3*i:27+3*i],'little') for i in range(32)]
    for edit in plan['edits']:counts[edit['bank']*8+edit['sector']-8]+=1
    assert b[8:24]==a[8:24] and [int.from_bytes(b[24+3*i:27+3*i],'little') for i in range(32)]==counts
    for bank,image in enumerate(m.banks):(root/f'expected-final-b{bank}.bin').write_bytes(image)
    report=dict(passed=True,board=plan['board'],confirmations_hex=confirmations,counts_after=counts,expected_hashes=[u.sha(image) for image in m.banks],only_sdemo_and_accounted_journal_changed=True,retained_devices_preserved=True)
    (root/'removal-model.json').write_text(json.dumps(report,indent=2)+'\n')
    print('PASS',plan['board'],'exact MAINT record deletion, full-bank preservation and wear accounting',flush=True)

def apply(base):
    reports=[]
    for board in BOARDS:
        root=base/board;plan=u.read(root/'removal-plan.json');assert plan['board']==board
        if not plan['edits']:
            report=dict(passed=True,board=board,action='already-absent',records_removed=0,flash_written=False,external_sram_sdemo_absent=True)
            (root/'report.json').write_text(json.dumps(report,indent=2)+'\n');reports.append(report);print('PASS',board,'SDEMO already absent; no writes',flush=True);continue
        model=u.read(root/'removal-model.json');assert model['passed'] and len(model['confirmations_hex'])==len(plan['edits'])
        with serial_lease('remove-sdemo-write'),(root/'removal-serial.jsonl').open('x') as log:
            l=Link(fleet.port(board),log)
            try:
                establish_b3(l);active=l.dump(0x7D30,0x7D30)
                assert active==bytes((u.read(root/'initial-state.json')['active_page'],))
                for bank in range(4):
                    prompt=f'\r\nB{bank}> '.encode();l.command(f'B{bank}',prompt)
                    image=b''.join(l.dump(a,a+4095,prompt) for a in range(0x8000,0x10000,4096))
                    assert image==(root/f'prior-verified/b{bank}.bin').read_bytes(),'Stale backup; no deletion'
                l.command('B3');l.command('R MAINT',b'BM> ')
                for idx,edit in enumerate(plan['edits']):
                    for command in commands(plan,edit):
                        text=l.command(command,b'BM> ');assert b'INVALID' not in text and b'FAILED' not in text,text
                    text=l.command('D 0-FFF',b'BM> ');cells={}
                    for line in text.decode('ascii').splitlines():
                        match=re.fullmatch(r'([0-9A-F]{4}):((?: [0-9A-F]{2}){1,16})',line.strip())
                        if match:cells.update((int(match[1],16)+i,v) for i,v in enumerate(bytes.fromhex(match[2])))
                    assert set(cells)==set(range(4096)),'Incomplete editor readback'
                    image=bytes(cells[i] for i in range(4096));expected=(root/f"expected-b{edit['bank']}-{edit['sector']:X}.bin").read_bytes()
                    assert image==expected and u.sha(image)==edit['expected_sha256'],'Buffered deletion mismatch; do not confirm'
                    text=l.command(f"W {edit['bank']} {edit['sector']:X}",b'WRITE? TYPE Y> ')
                    assert text==bytes.fromhex(model['confirmations_hex'][idx]),'Unexpected write plan; do not confirm'
                    text=l.command('Y',b'BM> ');assert b'VERIFIED' in text and b'FAILED' not in text,text
                    print('REMOVED',board,f"B{edit['bank']}:{edit['sector']:X}",'verified',flush=True)
                l.command('Q');hashes=[]
                for bank in range(4):
                    prompt=f'\r\nB{bank}> '.encode();l.command(f'B{bank}',prompt)
                    image=b''.join(l.dump(a,a+4095,prompt) for a in range(0x8000,0x10000,4096))
                    assert image==(root/f'expected-final-b{bank}.bin').read_bytes(),f'Unexpected B{bank} change'
                    (root/f'final-b{bank}.bin').write_bytes(image);hashes.append(u.sha(image))
                l.command('B3');assert l.dump(0x7D30,0x7D30)==active
                text=b''.join(l.command(f'T {b}') for b in range(4));assert b'SDEMO' not in text;(root/'tables-after.txt').write_bytes(text)
                l.command('R SRAM',b'SRAM> ');text=l.command('T',b'SRAM> ');l.command('Q');assert text==(root/'sram-table-before.txt').read_bytes()
                l.command('R CLOCK',b'CLOCK> ');clock={c:l.command(c,b'CLOCK> ').hex() for c in ('HISTORY','TRIM','EUI')};l.command('Q')
                assert clock==u.read(root/'retained-clock-before.json'),'Clock history/trim/EUI changed'
                (root/'retained-clock-after.json').write_text(json.dumps(clock,indent=2)+'\n')
                text=l.command('W');(root/'wear-after.txt').write_bytes(text)
                rows=re.findall(rb'B([0-3]):([8-9A-F]) ([0-9A-F]{6})',text);assert len(rows)==32
                counts=[None]*32
                for b,s,n in rows:counts[int(b)*8+int(s,16)-8]=int(n,16)
                assert counts==model['counts_after']
                report=dict(passed=True,board=board,action='removed',records_removed=len(plan['records']),sector_erases=len(plan['edits']),
                    full_flash_verified=True,flash_hashes=hashes,other_programs_preserved=True,firmware_and_fallback_preserved=True,
                    erase_accounting_verified=True,clock_history_trim_identity_preserved=True,external_sram_table_unchanged=True,physical_reset_required=False)
            finally:l.serial.close()
        (root/'report.json').write_text(json.dumps(report,indent=2)+'\n');reports.append(report)
        print('PASS',board,'SDEMO absent; complete flash matches exact model; other programs, firmware, clocks and wear counts verified',flush=True)
    (base/'report.json').write_text(json.dumps(dict(passed=True,boards=reports),indent=2)+'\n')

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('stage',choices=('inspect','rehearse','apply'));p.add_argument('--root',required=True,type=Path);a=p.parse_args()
    if a.stage=='inspect':inspect(a.root.resolve())
    elif a.stage=='rehearse':rehearse(a.root.resolve())
    else:apply(a.root.resolve())
