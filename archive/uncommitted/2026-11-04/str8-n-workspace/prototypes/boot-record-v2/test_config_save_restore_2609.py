"""Rehearse CONFIG A/save/boot/S/restore and torn appends without device access."""
import argparse,json,re
from pathlib import Path
import prepare_config_save_restore_2609 as p
import test_ram_config_2609 as t
from test_b14_raw import start,feed

CFG=t.PROMPT
REC=b'REC> '
MON=b'B3> '
CHOICES=b'S=Recovery  A/B=Monitor  0-3=Bank\r\n'


def banks_at(plan,stage):return [(plan/f'{stage}-b{n}.bin').read_bytes() for n in range(4)]


def policy(banks,counts):
    row=t.legacy.latest(banks);assert row is not None
    assert row[13]==0 and row[14:18]==b'\x08'*4 and row[160:164]==b'\xff'*4
    assert [int.from_bytes(row[64+3*n:67+3*n],'little') for n in range(32)]==counts
    assert int.from_bytes(row[18:22],'little')==p.cfg.GENERATION
    return row


def protect(banks,source):
    assert list(map(bytes,banks[:3]))==list(map(bytes,source[:3]))
    assert bytes(banks[3][:0x4000])==source[3][:0x4000] and bytes(banks[3][0x6000:])==source[3][0x6000:]


def cold(build,cpu,banks,prompt):
    h=t.legacy.core.Machine(build,cpu,opaque=True)
    h.m.banks[:]=list(map(bytearray,banks));h.m.bank=3;h.m.tx.clear();h.m.acia_tx.clear()
    h.c.pc=0xf004;h.c.p=0x34;h.c.sp=255
    if cpu=='65c816-e':h.c.mode=1;h.c.dpr=h.c.dbr=h.c.pbr=0
    h.run(lambda:bytes(h.m.tx).endswith(prompt))
    assert not h.m.events
    return h


def load_again(h,build,port):
    start(h,port);feed(h,port,(build/'payload'/p.cfg.BIN).read_bytes())
    h.run(lambda:bytes(h.m.tx if port==1 else h.m.acia_tx).endswith(CFG))


def dump_bytes(reply,first,last):
    cells={}
    for line in reply.decode('ascii').splitlines():
        match=re.fullmatch(r'([0-9A-F]{4}):((?: [0-9A-F]{2}){1,16})',line.strip())
        if match:cells.update((int(match[1],16)+n,v) for n,v in enumerate(bytes.fromhex(match[2])))
    assert set(cells)==set(range(first,last+1))
    return bytes(cells[n] for n in range(first,last+1))


def checked_RAM_reentry(command,build):
    image=bytearray((build/'payload'/p.cfg.BIN).read_bytes())
    sy=p.cfg.read(build/'symbols.json')['core/ram-config'];image[sy['CONFIG_ROW']-0x200]=4
    assert dump_bytes(command(b'D 0200 0CA7\r',MON),0x200,0xca7)==image
    reply=command(b'G 0200\r',CFG)
    assert b'2609 RAM CONFIG / b15 F' in reply


def walkthrough(plan,out,cpu,port,passed):
    info=p.verify(plan);build=Path(info['build']);source=banks_at(plan,'source');counts=info['counts_before']
    expectedA=banks_at(plan,'MON-A');expectedS=banks_at(plan,'restored-S')
    h=t.current_machine(build,cpu,port,banks=source);transcript=bytearray(bytes(h.m.tx if port==1 else h.m.acia_tx))
    def command(body,prompt=CFG):
        reply=h.port_command(port,body,prompt);transcript.extend(reply);return reply
    for key in (b'B\r',b'C\r',b'W\r'):command(key)
    assert not h.m.events
    command(b'Q\r',REC);command(b'A\r',MON);checked_RAM_reentry(command,build)
    assert not h.m.events
    assert b'OK\r\n' in command(b'C A\r')
    assert list(map(bytes,h.m.banks))==expectedA
    row=policy(h.m.banks,counts);assert row[7]==ord('A') and int.from_bytes(row[8:12],'little')==1021
    assert b'DEFAULT=A\r\n' in command(b'B\r');command(b'W\r')
    save_events=list(h.m.events);save_snapshots=list(h.m.snapshots)
    assert save_events and all(event[0]!='erase' and event[1]==3 and 0xc600<=event[2]<0xc700 for event in save_events)
    passed(cpu,port,'save-A-exact-C600-seq1021-generation-pin-no-erase',mutations=len(save_events),RAM_independently_checked=True)
    reply=command(b'Q\r',MON)
    assert b'Boot : 6 5 4 3 2 1 0' in reply and b'STR8-N 2.0proto b15 B3' in reply
    assert b'7D30: A0' in command(b'D 7D30 7D30\r',MON)
    assert dump_bytes(command(b'D C600 C6FF\r',MON),0xc600,0xc6ff)==(plan/'MON-A-journal-row.bin').read_bytes()
    command(b'J3\r',CHOICES);command(b'S',REC)
    assert h.m.events==save_events and policy(h.m.banks,counts)[7]==ord('A')
    # A complete F reset with the committed images independently boots MON A.
    boot=cold(build,cpu,expectedA,MON)
    assert b'Boot : 6 5 4 3 2 1 0' in boot.m.tx
    passed(cpu,port,'saved-A-boots-without-A-key-manual-S-does-not-save',boot_default='A')
    load_again(h,build,port)
    assert b'DEFAULT=A\r\n' in command(b'C\r')
    command(b'Q\r',MON);checked_RAM_reentry(command,build)
    assert b'OK\r\n' in command(b'C S\r')
    assert list(map(bytes,h.m.banks))==expectedS
    row=policy(h.m.banks,counts);assert row[7]==ord('S') and int.from_bytes(row[8:12],'little')==1022
    # Restoring policy never rolls sequence or history back to the source row.
    original=t.legacy.latest(source)
    assert row[:8]+row[12:30]+row[32:252]+row[254:]==original[:8]+original[12:30]+original[32:252]+original[254:]
    for key in (b'B\r',b'C\r',b'W\r'):command(key)
    events=list(h.m.events);assert all(event[0]!='erase' for event in events)
    assert all(event[1]==3 and 0xc600<=event[2]<0xc800 for event in events)
    reply=command(b'Q\r',REC);assert b'Boot : 6 5 4 3 2 1 0' in reply
    assert h.m.events==events and list(map(bytes,h.m.banks))==expectedS
    reset=cold(build,cpu,expectedS,REC);assert policy(reset.m.banks,counts)[7]==ord('S')
    protect(h.m.banks,source)
    (out/f'simulated-walkthrough-{cpu}-port{port}.txt').write_bytes(transcript)
    passed(cpu,port,'restore-S-exact-C700-seq1022-autoboot-REC-all-counts-and-B0-preserved',mutations=len(events)-len(save_events),RAM_independently_checked=True)
    return save_snapshots,list(h.m.snapshots[len(save_snapshots):])


def prefixes(plan,cpu,stage,snapshots,passed):
    info=p.verify(plan);source=banks_at(plan,'source');base=banks_at(plan,'source' if stage=='A' else 'MON-A')
    build=Path(info['build']);old=t.legacy.latest(base);last='A' if stage=='A' else 'S'
    for snapshot in snapshots:
        banks=list(map(bytearray,base));banks[3][0x4000:0x6000]=snapshot
        protect(banks,source);row=policy(banks,info['counts_before'])
        assert chr(row[7]) in (chr(old[7]),last)
        assert row[32:64]+row[160:252]==old[32:64]+old[160:252]
        t.legacy.reboot_reader(build,cpu,banks)
    passed(cpu,1,'all-mutation-prefixes-'+('save-A' if stage=='A' else 'restore-S'),prefixes=len(snapshots))


def inspected_restore_retries(plan,cpu,snapshots,passed):
    info=p.verify(plan);base=banks_at(plan,'MON-A');source=banks_at(plan,'source');build=Path(info['build'])
    choices={0,len(snapshots)//2,len(snapshots)-1}
    for index in sorted(choices):
        banks=list(map(bytearray,base));banks[3][0x4000:0x6000]=snapshots[index]
        row=policy(banks,info['counts_before'])
        if row[7]==ord('S'):
            assert int.from_bytes(row[8:12],'little')==1022
            continue  # Never append another C S when the restore is committed.
        h=t.current_machine(build,cpu,banks=list(map(bytes,banks)))
        assert b'OK' in t.legacy.command(h,1,b'C S')
        restored=policy(h.m.banks,info['counts_before'])
        assert restored[7]==ord('S') and int.from_bytes(restored[8:12],'little')==1022
        assert all(event[0]!='erase' for event in h.m.events)
        protect(h.m.banks,source);cold(build,cpu,h.m.banks,REC)
    passed(cpu,1,'inspected-torn-restore-skips-dirty-page-and-already-S-is-noop',selected_prefixes=len(choices))


def bad_monitor(plan,cpu,passed):
    info=p.verify(plan);source=banks_at(plan,'source');build=Path(info['build'])
    for case in ('missing','CRC','commit'):
        banks=list(map(bytearray,source))
        if case=='missing':banks[3][0x2000:0x3000]=b'\xff'*4096
        elif case=='CRC':banks[3][0x2100]^=1
        else:banks[3][0x201f]=255
        h=t.current_machine(build,cpu,banks=list(map(bytes,banks)));before=list(map(bytes,h.m.banks))
        assert b'REFUSED: journal/target' in t.legacy.command(h,1,b'C A')
        assert not h.m.events and list(map(bytes,h.m.banks))==before
    passed(cpu,1,'missing-corrupt-uncommitted-MON-A-refused-without-mutation',cases=3)
    banks=list(map(bytearray,banks_at(plan,'MON-A')));banks[3][0x2000:0x3000]=b'\xff'*4096
    boot=cold(build,cpu,banks,REC)
    assert policy(boot.m.banks,info['counts_before'])[7]==ord('A')
    h=t.current_machine(build,cpu,banks=list(map(bytes,banks)))
    assert b'OK' in t.legacy.command(h,1,b'C S')
    assert policy(h.m.banks,info['counts_before'])[7]==ord('S') and all(event[0]!='erase' for event in h.m.events)
    cold(build,cpu,h.m.banks,REC)
    passed(cpu,1,'saved-A-unavailable-falls-to-REC-and-RAM-CONFIG-restores-S')


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--plan',type=Path,required=True);parser.add_argument('--out',type=Path,required=True)
    args=parser.parse_args();plan,out=args.plan.resolve(),args.out.resolve();assert not out.exists();out.mkdir(parents=True)
    info=p.verify(plan);cases=[]
    def passed(cpu,port,case,**details):
        cases.append(dict(passed=True,cpu=cpu,port=port,case=case,**details))
        p.cfg.save(out/'progress.json',dict(completed=len(cases),cases=cases));print('PASS',len(cases),cpu,port,case,details,flush=True)
    for cpu in ('65c816-e','65c02'):
        for port in (1,2):
            A,S=walkthrough(plan,out,cpu,port,passed)
            if port==1:prefixA,prefixS=A,S
        prefixes(plan,cpu,'A',prefixA,passed);prefixes(plan,cpu,'S',prefixS,passed)
        inspected_restore_retries(plan,cpu,prefixS,passed);bad_monitor(plan,cpu,passed)
    source=banks_at(plan,'source');p.admit_source(source,info)
    changed=[('MON-A',banks_at(plan,'MON-A')),('restored-S',banks_at(plan,'restored-S'))]
    bad=list(map(bytearray,source));bad[0][5]^=1;changed.append(('changed-B0',bad))
    for name,banks in changed:
        try:p.admit_source(banks,info)
        except AssertionError:pass
        else:raise AssertionError('Changed source accepted: '+name)
    passed('host',0,'exact-source-refuses-replay-and-changed-B0',cases=len(changed))
    assert not p.cfg.ATTEMPTS
    result=dict(passed=True,checks=len(cases),failures=0,hardware=False,board_access=False,serial_access=False,
        actual_saved_setting_writes=False,plan_sha256=p.cfg.digest(plan/'plan.json'),BIN_sha256=info['BIN_sha256'],
        checker_sha256=p.cfg.digest(__file__),CPUs=['65c816-e','65c02'],ports=['USB model','ACIA model'],
        mutation_prefixes=sum(case.get('prefixes',0) for case in cases),cases=cases)
    p.cfg.save(out/'qualification.json',result)
    print('PASS',len(cases),'exercise groups;',result['mutation_prefixes'],'interrupted-write prefixes; no device access',flush=True)


if __name__=='__main__':main()
