"""Restore only erased STATUS text holes; native guarded1->0, zero erases."""
import argparse,binascii,json,re
from pathlib import Path
import install_2512_native_utilities as d
from serial_test_coordination import drift_pending

t=d.t
MONS=tuple(f'B{n}> '.encode() for n in range(4))


def run(board,out):
    folder=Path(out).resolve();assert folder.is_relative_to(t.ROOT/'output/qualification')
    folder.mkdir(exist_ok=False);(folder/'.gitignore').write_text('*\n')
    (folder/'driver-as-executed.py').write_bytes(Path(__file__).read_bytes())
    archive=t.ROOT/f'output/qualification/STORAGE-native-scope-20261101-r3/{board}'
    installed=t.ROOT/f'output/qualification/{board}-native-storage-installed-20261101-r1'
    old=(archive/'B2-original.bin').read_bytes();current=(installed/'B2-after.bin').read_bytes()
    target=bytearray(current)
    for a in (0x40,0x240):
        assert current[a:a+192]==b'\xff'*192
        assert binascii.crc_hqx(old[a:a+192],65535)==0
        target[a:a+192]=old[a:a+192]
    target=bytes(target);(folder/'B2-target.bin').write_bytes(target)
    mp=t.ROOT/f'output/qualification/device-operations/{board}.json'
    r=dict(board=board,passed=False,flash_byte_programs=0,sector_erases=0,journal_writes=0,F_writes=0,
        RTC_SET=0,trim_writes=0,PF_ACK=0,SRAM_writes=0,owner_RAM_borrowed=False,owner_ZP_borrowed=False,
        target_sha256=t.sha(target),checks=[])
    s=None;marker=None;origin=None;edu=None;before_journal=None
    def save():t.save(folder/'report.json',r)
    def mark(**kw):m=json.loads(mp.read_text());m.update(kw);t.save(mp,m)
    def dump(first,last):
        face=s.command(f'D {first:04X} {last:04X}')
        found={}
        for match in re.finditer(rb'(?:^|\n)([0-9A-F]{4}):((?: [0-9A-F]{2}){1,16})',face):
            at=int(match[1],16);found.update((at+i,v) for i,v in enumerate(bytes.fromhex(match[2].decode())))
        assert all(a in found for a in range(first,last+1))
        return bytes(found[a] for a in range(first,last+1))
    def check(name):r['checks'].append(name);save();print('PASS '+board+' '+name,flush=True)
    def mon():
        if s.context==t.REC:s.command('B',(t.MON,))
        if s.context in MONS and s.context!=t.MON:s.command('B3',(t.MON,))
        assert s.context==t.MON
    save()
    with t.serial_lease(board+'-STATUS-erased-literal-repair',timeout=600):
      if drift_pending():raise InterruptedError('RTC priority; no board opened')
      marker=json.loads(mp.read_text())
      assert marker['application_ram_restored'] and not marker['application_RAM_restore_pending']
      assert not any(v for k,v in marker.items() if k.endswith('_worker_active'))
      assert marker['current_physical_bank_sha256']['B2']==t.sha(current)
      with (folder/'serial.jsonl').open('x') as log:
        try:
            s=d.Session(folder,log,board);s.link.send(b'\r');s.until((t.MON,t.REC),seconds=12);origin=s.context;mon()
            edu=dump(0x6A20,0x6A20)[0]
            original=s.command('VERSION');(folder/'VERSION-before.txt').write_bytes(original)
            assert b'g0000000D / MON B' in original and b'STATUS tools unavailable' in original
            # Last committed row, independently selected from the preserved B3.
            b3=(installed/'B3-after.bin').read_bytes()
            journal=t.classify_journal(b3);page=int(journal['page'],16) if 'page' in journal else None
            if page is None:
                from native_journal_room import valid_snapshot
                page=max((o for o in range(0x4000,0x6000,256) if valid_snapshot(b3[o:o+256])),key=lambda o:int.from_bytes(b3[o+8:o+12],'little'))+0x8000
            before_journal=dump(page,page+255);assert before_journal==b3[page-0x8000:page-0x8000+256]
            s.command('B2',(b'B2> ',))
            for a in (0x8040,0x8240):assert dump(a,a+191)==b'\xff'*192
            check('both-STATUS-holes-erased-latest-journal-retained')
            mark(status_literal_repair_worker_active=True)
            for base in (0x8040,0x8240):
                for a in range(base,base+192,8):
                    data=target[a-0x8000:a-0x8000+8]
                    face=s.command(f'!M {a:04X} '+data.hex(' ').upper())
                    assert b'REFUSED' not in face and b'Partial' not in face,face
                    r['flash_byte_programs']+=sum(v!=255 for v in data);save()
                assert dump(base,base+191)==target[base-0x8000:base-0x8000+192]
            check('384-byte-literal-extents-restored-without-erase')
            mon();assert dump(page,page+255)==before_journal
            face=s.command('VERSION');(folder/'VERSION-after.txt').write_bytes(face)
            assert b'STATUS tools unavailable' not in face
            assert (b'CPU: 65C02' if board=='2512' else b'CPU: 65C816 emulation') in face
            assert ('Board: '+board).encode() in face and b'EDU ON' in face
            check('rich-VERSION-board-CPU-EDU-status-restored')
            face=s.command('TIME');(folder/'TIME-after.txt').write_bytes(face)
            assert b' trim $'+(b'0C' if board=='2512' else b'0E') in face and b'ctrl $80' in face
            check('native-TIME-control-trim-and-journal-unchanged')
            m=json.loads(mp.read_text());m['current_physical_bank_sha256']['B2']=t.sha(target)
            m.update(status_literal_repair_worker_active=False,last_STATUS_literal_repair=str(folder/'report.json'),
                current_image_evidence='Native-storage targets plus program-only restoration of archived STATUS text8040/8240; all other image bytes retained')
            t.save(mp,m);r['passed']=True
        except Exception as e:r['error']=repr(e);raise
        finally:
            if s:
                try:
                    mon()
                    if edu is not None and edu!=1:s.command(f'!M 6A20 {edu:02X}')
                    if origin==t.REC:s.command('Q',(t.REC,))
                finally:s.link.close();r['port_released']=True
            if marker:mark(status_literal_repair_worker_active=False,status_literal_repair_pending=not r['passed'])
            save()
    print(('PASS ' if r['passed'] else 'FAIL ')+board+' STATUS repair; port released',flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--board',choices=('2512','2609'),required=True)
    p.add_argument('--out',required=True);a=p.parse_args();run(a.board,a.out)
