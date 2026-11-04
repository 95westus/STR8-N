"""RAM-only BANK MAINT qualification and relevant-bank capture; no NVM writes."""
import argparse
import binascii
import json
from pathlib import Path
import install_2512_native_utilities as d

t=d.t
BM=b'BM> '
CONFIRM=b'WRITE? TYPE Y> '


def run(board,folder,reuse_layout=None):
    folder=Path(folder).resolve();assert folder.is_relative_to(t.ROOT/'output/qualification')
    folder.mkdir(exist_ok=False);(folder/'.gitignore').write_text('*\n')
    build=t.ROOT/'BUILD/native-apps-g1-maint-r1'
    manifest=json.loads((build/'manifest.json').read_text())
    app=(build/'BANK-MAINT-g00000001-RAM.bin').read_bytes()
    assert t.sha(app)==manifest['artifacts']['BANK-MAINT-g00000001-RAM.bin']['sha256']
    assert len(app)==8957
    # Force only the previously admitted B slot for this private RAM entry.
    # Ordinary native launches obtain MU_ACTIVE from their caller instead.
    prefix=bytes.fromhex('78 D8 A2 00 BD 00 6A 9D 00 65 BD 00 00 9D 00 64 E8 D0 F1 A9 B0 8D 30 7D 9C F9 7D 4C 00 20')
    packet=prefix.ljust(0x1E00,b'\xff')+app
    (folder/'RAM-trial.bin').write_bytes(packet)
    reader=(t.REPO/'firmware/payload/STR8N-F-READBACK-RAM.bin').read_bytes()
    markpath=t.ROOT/f'output/qualification/device-operations/{board}.json'
    r=dict(board=board,passed=False,checks=[],F_writes=0,flash_writes=0,journal_writes=0,
        RTC_writes=0,SRAM_data_writes=0,power_cuts=0,owner_RAM_restored=False,owner_ZP_restored=False)
    s=None;borrowed=False;ram=zp=native_prefix=None
    def save():t.save(folder/'report.json',r)
    def mark(**kw):
        m=json.loads(markpath.read_text());m.update(kw);t.save(markpath,m)
    def check(label):r['checks'].append(label);save();print('PASS '+board+' '+label,flush=True)
    def rec():
        if s.context==CONFIRM:s.command('NO',(BM,))
        if s.context==b'Type YES: ':s.command('NO',(BM,))
        if s.context==BM:s.command('Q',(t.MON,))
        if s.context==t.MON:s.command('Q',(t.REC,))
        elif s.context==d.SERVICE:
            s.client.send(b'Q');s.client.until(t.REC);s.context=t.REC
        assert s.context==t.REC,'Unknown execution context; no blind recovery'
    def cmd(text,tokens=None):
        out=s.command(text,tokens)
        label=__import__('re').sub(r'[^A-Za-z0-9_-]','_',text.split()[0])
        (folder/(str(s.counter)+'-'+label+'.txt')).write_bytes(out)
        return out
    def ramwrite(text):
        out=cmd(text,(CONFIRM,BM));assert s.context==CONFIRM,(text,out)
        out=cmd('Y',(BM,));assert b'VERIFIED' in out,(text,out)
    def crc():
        out=cmd('K');match=__import__('re').search(rb'CRC16-CCITT-FALSE ([0-9A-F]{4})',out)
        assert match,out
        return int(match[1],16)
    save()
    with t.serial_lease(board+'-BANK-MAINT-RAM-only',timeout=30):
        marker=json.loads(markpath.read_text());assert not marker['application_RAM_restore_pending']
        assert not any(v for k,v in marker.items() if k.endswith('_worker_active'))
        with (folder/'serial.jsonl').open('x') as log:
            try:
                s=d.Session(folder,log,board);s.link.send(b'\r');s.until((t.MON,t.REC),seconds=12)
                if s.context==t.REC:s.command('B',(t.MON,))
                assert b'g0000000C / MON B' in s.command('VERSION')
                native_prefix=s.dump(0x200,0x1FF+len(reader));zp=s.dump(0,0xDF)
                (folder/'owner-prefix.bin').write_bytes(native_prefix);(folder/'owner-zp.bin').write_bytes(zp)
                mark(bank_maint_RAM_worker_active=True,application_RAM_restore_pending=True,block_snapshot=True)
                borrowed=True;rec();t.transport.recovery_usb(s.link);s.service(reader)
                memory=s.client.read(b'M',0x6500)
                assert memory[:len(reader)]==reader and s.client.read(b'Z',0xE0)==zp
                ram=native_prefix+memory[len(reader):]
                (folder/'owner-ram.bin').write_bytes(ram)
                for bank in (1,2,3):
                    if reuse_layout and bank in (1,2):
                        body=(Path(reuse_layout)/f'B{bank}-before.bin').read_bytes()
                    else:body=s.client.flash(bank)
                    assert t.sha(body)==marker['current_physical_bank_sha256'][f'B{bank}']
                    (folder/f'B{bank}-before.bin').write_bytes(body)
                original3=(folder/'B3-before.bin').read_bytes()
                original2=(folder/'B2-before.bin').read_bytes()
                known=(t.REPO/'firmware/payload/STR8N-F-BOOT-4096.bin').read_bytes()
                assert original3[-4096:]==known
                r.update(owner_RAM_sha256=t.sha(ram),owner_ZP_sha256=t.sha(zp),journal=t.classify_journal(original3))
                check('fresh-owner-escrow-and-relevant-layout-capture')
                rec();s.load(packet,t.sha(packet),BM)
                helptext=cmd('?')
                assert b'Copy RAM or flash' in helptext and b'Buffer CRC16' in helptext
                assert b'BM>' in helptext and b'CONFIG 0.3' not in helptext
                check('real-BM-menu-and-return-contract-admitted')
                assert ('Board: '+board).encode() in cmd('NAME')
                cmd('NAME BMTEST',(b'Type YES: ',));cmd('NO',(BM,))
                assert ('Board: '+board).encode() in cmd('NAME')
                assert b'DEFAULT=B' in cmd('BOOT')
                check('board-name-query-cancel-and-BOOT-settings-inspection')
                table=cmd('TABLE')
                assert b'B2:B000 2000-4FD4 2FD5 C CLOCK' in table,table
                assert b'B2:E000 2000-3A28 1A29 C FLASH' in table,table
                assert b'no payload CRC' in table
                cmd('T 1');check('TABLE-and-T-bank-compact-rows-with-native-CRC')
                cmd('N 1000 FF');assert crc()==binascii.crc_hqx(b'\xff'*4096,65535)
                cmd('P 0 12 34 56');cmd('F 10-1F A5')
                expected=bytearray(b'\xff'*4096);expected[:3]=bytes((0x12,0x34,0x56));expected[0x10:0x20]=b'\xA5'*16
                expected_crc=binascii.crc_hqx(expected,65535)
                assert crc()==expected_crc
                display=cmd('D 0-1F');assert b'12 34 56' in display
                for query in ('M1','M2','M3','VERSION','TABLE 1'):
                    cmd(query);assert crc()==expected_crc,query
                check('full-4K-editor-patch-fill-dump-CRC-and-independent-buffer')
                # Flash-read -> independent buffer -> RAM; no flash mutation.
                cmd('R 3 8000-80FF');ramwrite('W R 1300')
                ramwrite('C R 1300-13BF R 1340')
                ramwrite('C R 1300-133F R 1500')
                assert b'MATCH' in cmd('V R 1300-133F R 1500')
                cmd('N 1 EF');ramwrite('W R 1500')
                assert b'DIFFERENT AT DEST 1500' in cmd('V R 1300-133F R 1500')
                # Cancel a RAM copy before its first destination write.
                cmd('C R 1300-133F R 1580',(CONFIRM,));cmd('NO',(BM,))
                for text in ('E 3 F','E 3 C-D','E 2 8','E 1 8-A','C R 1300-133F 3 F000'):
                    out=cmd(text);assert s.context==BM and b'WRITE? TYPE Y' not in out,text
                check('RAM-copy-compare-overlap-cancel-and-protected-flash-refusal')
                cmd('Q',(t.MON,));assert s.dump(0,0xDF)==zp
                data=s.dump(0x1300,0x13FF)
                target=bytearray(original3[:256]);target[0x40:]=original3[:0xC0]
                assert data==target,'Overlapping COPY must have memmove behavior'
                assert s.dump(0x1500,0x153F)==bytes((0xEF,))+original3[1:0x40]
                check('quiet-Q-preserves-ZP-and-exact-overlap-result')
                rec();s.service(reader)
                assert s.client.flash(3)==original3
                assert s.client.flash(2)==original2
                check('F-all-boot-wear-metadata-and-B2-images-unchanged')
            finally:
                try:
                    if borrowed:
                        if s.context!=d.SERVICE:rec();s.service(reader)
                        if ram is None:
                            memory=s.client.read(b'M',0x6500);assert memory[:len(reader)]==reader
                            ram=native_prefix+memory[len(reader):]
                        r.update(s.client.restore_owner(ram,zp));s.context=t.REC
                        s.command('B',(t.MON,));r['owner_RAM_restored']=True
                finally:
                    if s is not None:s.link.close();r['port_released']=True
                    if borrowed:
                        restored=r['owner_RAM_restored'] and r['owner_ZP_restored']
                        mark(bank_maint_RAM_worker_active=False,application_RAM_restore_pending=not restored,
                            application_ram_restored=restored,block_snapshot=marker['block_snapshot'] if restored else True,
                            last_BANK_MAINT_RAM_trial=str(folder/'report.json'))
                    save()
    r['passed']=len(r['checks'])==8 and r['owner_RAM_restored'] and r['owner_ZP_restored']
    save();print('PASS '+board+' RAM-only BM trial; owner RAM/ZP restored',flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--board',choices=['2512','2609'],required=True)
    p.add_argument('--out',required=True);p.add_argument('--reuse-layout',type=Path)
    a=p.parse_args();run(a.board,a.out,a.reuse_layout)
