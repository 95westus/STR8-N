"""Beta35 fleet update from existing verified images; no live backups/readback dumps."""
import argparse
from contextlib import nullcontext
import hashlib
import json
import os
from pathlib import Path
import time

os.environ['STR8_RTC_BUILD']='BUILD/v2-beta35-candidate'
import beta4_migration as m
from rtc_boards import SERIALS
import serial_test_coordination as coordination
from rtc_prompt_sync import establish_b3

ROOT=Path(__file__).resolve().parents[1];DATA=Path(r'C:\SRC\STR8-N')
BUILD=ROOT/'BUILD/v2-beta35-candidate';BASE=ROOT/'BUILD/v2-beta34-candidate'
OLD=DATA/'output/qualification/beta34-fleet-2026-10-16'
OUT=DATA/'output/qualification/beta35-fleet-2026-10-16'
coordination.ROOT=DATA/'output/qualification/serial-coordination'
read=lambda p:json.loads(p.read_text())
sha=lambda b:hashlib.sha256(b).hexdigest()
save=lambda p,v:p.write_text(json.dumps(v,indent=2)+'\n')
images=lambda d,p:[(d/f'{p}{i}.bin').read_bytes() for i in range(4)]


def before(board):
    receipt=read(OLD/'report.json');assert receipt['passed']
    folder=OLD/'fresh/2512' if board=='2512' else OLD/board/'hardware'
    prefix='flash-1-b' if board=='2512' else 'final-b'
    banks=images(folder,prefix)
    assert [sha(b) for b in banks]==receipt['boards'][board]['final_flash_sha256']
    return banks


def prepare():
    meta=read(BUILD/'build.json');assert meta['version']=='2.0b35'
    for n,h in meta['artifacts'].items():assert sha((BUILD/n).read_bytes())==h
    assert (BUILD/'str8n-journal-9000-9fff.bin').read_bytes()==(BASE/'str8n-journal-9000-9fff.bin').read_bytes()
    OUT.mkdir(parents=True,exist_ok=False)
    for board in SERIALS:
        banks=before(board);final=[bytearray(b) for b in banks]
        region=banks[1][0x3000:0x6000]
        assert region in (b'\xff'*12288,(BASE/'clock/storage.bin').read_bytes())
        final[1][0x3000:0x6000]=(BUILD/'clock/storage.bin').read_bytes()
        final[2][0x7800:]=(BUILD/'version/asset.bin').read_bytes()
        final[3][:4096]=(BUILD/'str8n-rtc-component-8000-8fff.bin').read_bytes()
        final[3][0x3000:0x4000]=(BUILD/'str8n-v2-recovery-slot-b0.bin').read_bytes()
        order=[(3,12),(1,13),(1,12),(1,11),(2,15),(3,8),(3,11)]
        j=m.journal(banks[3]);cfg=bytearray(j[8:24]);assert cfg[14:]==m.config_sum(cfg)
        cfg[7:13]=b'P\xB0'+(47).to_bytes(4,'little');cfg[14:]=m.config_sum(cfg)
        counts=[int.from_bytes(j[24+3*i:27+3*i],'little') for i in range(32)];oldcounts=counts[:]
        for b,s in order:counts[b*8+s-8]+=1;assert counts[b*8+s-8]<0xFFFFFF
        final[3][0x4000:0x5000]=m.metadata(cfg,counts,int.from_bytes(j[4:8],'little')+1)+b'\xff'*(4096-128)
        assert final[0]==banks[0] and final[1][:0x3000]==banks[1][:0x3000] and final[1][0x6000:]==banks[1][0x6000:]
        assert final[3][0x1000:0x3000]==banks[3][0x1000:0x3000] and final[3][0x5000:]==banks[3][0x5000:]
        mf=read(BUILD/'migrator/manifest.json');cells,entry=m.read_s19(BUILD/'migrator/rtc-migrator-2000.s19')
        cells[mf['count']]=len(order);cells[mf['commit_after']]=0;sy=mf['symbols']
        call=sy['MIG_HALT']-3;tail=max(cells)+1
        stub=b'\x20'+sy['MIG_PRINT'].to_bytes(2,'little')+b'\xA9\x03\x20'+sy['V2W_SELECT'].to_bytes(2,'little')+b'\x4C\x04\xF0'
        cells.update(dict(enumerate(stub,tail)));cells.update(dict(enumerate(b'\x20'+tail.to_bytes(2,'little'),call)))
        pending=[bytearray(b) for b in banks];payloads=[]
        for i,(b,s) in enumerate(order):
            off=(s-8)*4096;payload=bytearray(final[b][off:off+4096]);a=0xB003 if (b,s)==(1,11) else 0xB01F if (b,s)==(3,11) else 0
            if a:payload[a-(s<<12)]=255
            cells.update(dict(enumerate(bytes((s<<4,))+m.fnv(pending[b]).to_bytes(4,'little')+m.fnv(payload).to_bytes(4,'little'),mf['table']+9*i)))
            cells[mf['banks']+i]=b;cells[mf['commits']+i]=b+1 if a else 0
            cells.update(dict(enumerate(a.to_bytes(2,'little')+b'\0\0',mf['commit_addresses']+4*i)))
            pending[b][off:off+4096]=payload
            if a:pending[b][a-0x8000]=0 if b==3 else 0x3F
            payloads.append(payload)
        assert pending==final
        # Completion message is already printed before the explicit B3/RESET return.
        token='BETA35 VERIFIED; RESTARTING'
        msg=token.encode()+b'\r\n\0';assert len(msg)<=sy['MIG_BAD']-sy['MIG_DONE']
        cells.update(dict(enumerate(msg,sy['MIG_DONE'])))
        folder=OUT/board;folder.mkdir();installer=m.s19(cells,entry);(folder/'installer.s19').write_bytes(installer)
        for i,p in enumerate(payloads):(folder/f'transfer-{i:02d}.bin').write_bytes(p)
        for b,p in enumerate(final):(folder/f'expected-b{b}.bin').write_bytes(p)
        save(folder/'plan.json',dict(board=board,steps=order,prior_hashes=[sha(b) for b in banks],expected_hashes=[sha(b) for b in final],
            installer_sha256=sha(installer),build_sha256=sha((BUILD/'build.json').read_bytes()),
            completion_token=token,return_stub=tail,return_checkpoint=tail+8,counts_before=oldcounts,counts_after=counts,
            new_backups=False,host_readbacks=False,normal_on_device_program_verification=True))
    print('PREPARED four seven-sector plans from existing verified images; no board reads',flush=True)


def qualify(board):
    import test_v2_rtc_upgrade as test
    from test_v2_status import fresh,boot
    from test_v2_sram_store import console
    folder=OUT/board;p=read(folder/'plan.json');cells,entry=m.read_s19(folder/'installer.s19');banks=before(board)
    final=images(folder,'expected-b');allowed=set(map(tuple,p['steps']))
    record=final[1][0x3000:0x3000+24+read(BUILD/'clock/build.json')['bytes']]
    class Memory(test.Memory):
        def mutated(self,kind,address,value):
            if self.bank==3 and address==0xB01F and value==0:
                assert bytes(self.banks[1])==final[1] and bytes(self.banks[2])==final[2]
            super().mutated(kind,address,value)
    def execute(initial,corrupt=False):
        mem=Memory(initial,allowed,{},commit_records={(1,0xB000):record})
        for a,v in cells.items():mem.ram[a]=v
        cpu=test.CPU(memory=mem,pc=entry);mem.cpu=cpu;mem.rx.extend(b'Y\r')
        for i,(b,s) in enumerate(p['steps']):
            token=f'SEND 4096 BYTES FOR B{b}:{s:X}\r\n'.encode()
            if corrupt:
                test.run(cpu,lambda:token in bytes(mem.tx) or cpu.pc==test.S['MIG_HALT'])
                if cpu.pc==test.S['MIG_HALT']:return mem,cpu
            else:test.run(cpu,lambda:token in bytes(mem.tx))
            mem.tx.clear();payload=bytearray((folder/f'transfer-{i:02d}.bin').read_bytes())
            if corrupt and i==0:payload[127]^=1
            mem.rx.extend(payload)
            if corrupt:
                test.run(cpu,lambda:cpu.pc==test.S['MIG_HALT']);return mem,cpu
        test.run(cpu,lambda:cpu.pc==0xF004)
        return mem,cpu
    mem,cpu=execute(banks);assert mem.bank==3 and [bytes(b) for b in mem.banks]==final
    assert [(e[1],e[2]>>12) for e in mem.events if e[0]=='erase']==list(map(tuple,p['steps']))
    stale=[bytearray(b) for b in banks];stale[3][0x123]^=1
    bad,_=execute(stale,True);assert not bad.events
    bad,_=execute(banks,True);assert not bad.events
    print('PASS installer',board,'guards, record commit, exact sectors and actual B3 return',flush=True)
    cpu,mem=fresh();mem.fast=True;mem.banks=[bytearray(b) for b in final];mem.spi.banks=mem.banks
    prior=OLD/'fresh'/board;array=(prior/'spi-sram-1.bin').read_bytes();mem.spi.devices[0].data[:]=array
    mem.bus.rtc_regs[:32]=(prior/'rtc-registers-1.bin').read_bytes();mem.bus.ee[:128]=(prior/'eeprom-1.bin').read_bytes()
    mem.bus.ee[240:248]=(prior/'eeprom-protected-1.bin').read_bytes();mem.bus.ee[255]=(prior/'eeprom-status-1.bin').read_bytes()[0]
    boot(cpu);assert b'2.0b35' in mem.tx
    transcript=bytearray(mem.tx)
    def cmd(line):
        print('MODEL',board,line,flush=True);o=console(cpu,mem,line.encode()+b'\r',limit=100000000);transcript.extend(o);return o
    assert b'Done' in cmd('R 1 CLOCK L')
    if board!='2604':
        out=cmd(f'SRAM\rS CLK 2000 {0x2000+read(BUILD/"clock/build.json")["bytes"]-1:04X} 2000\rQ')
        assert b'SRAM: 00' in out,out[-500:]
        split=int.from_bytes(array[5:7],'little')*256;assert bytes(mem.spi.devices[0].data[split:])==array[split:]
        out=cmd('BATCH SRAM;G CLK;STATS;Q');assert b'CLOCK 1.10' in out and b'BATCH done' in out
    assert b'CLOCK 1.10' in cmd('R CLOCK');cmd('STATS');cmd('Q')
    assert (BUILD/'xip/utilities.bin').read_bytes()==(BASE/'xip/utilities.bin').read_bytes()
    assert [bytes(b) for b in mem.banks]==final
    assert bytes(mem.bus.ee[:128])==(prior/'eeprom-1.bin').read_bytes()
    (folder/'model-console.txt').write_bytes(transcript)
    save(folder/'model.json',dict(passed=True,installer_sha256=p['installer_sha256'],expected_hashes=p['expected_hashes'],
        source_guard=True,payload_guard=True,actual_return_bank=3,clock='1.10',workspace_preserved=True,
        expected_sram_sha256=sha(bytes(mem.spi.devices[0].data)),build_sha256=p['build_sha256']))


def audit(board):
    p=read(OUT/board/'plan.json');q=read(OUT/board/'model.json')
    result=read(BUILD/'beta35-test-results.json')
    assert result['passed'] and q['passed'] and result['build_sha256']==p['build_sha256']
    assert q['installer_sha256']==p['installer_sha256']==sha((OUT/board/'installer.s19').read_bytes())
    assert p['build_sha256']==q['build_sha256']==sha((BUILD/'build.json').read_bytes())
    assert p['expected_hashes']==q['expected_hashes']
    for i,(b,s) in enumerate(p['steps']):
        data=bytearray((OUT/board/f'expected-b{b}.bin').read_bytes()[(s-8)*4096:(s-7)*4096])
        if (b,s)==(1,11):data[3]=255
        if (b,s)==(3,11):data[31]=255
        assert (OUT/board/f'transfer-{i:02d}.bin').read_bytes()==data
    return p


def install(board):
    from serial.tools.list_ports import comports
    p=audit(board);folder=OUT/board;report=dict(board=board,passed=False,new_backups=False,host_readbacks=False,ram_restored=False,
        application_ram_used_by_installer=True,internal_program_verification=True,soak_started=False)
    with coordination.serial_lease('beta35-no-backup-'+board,priority=True),(folder/'serial.jsonl').open('x') as log:
        port=next(x.device for x in comports() if x.serial_number==SERIALS[board]);link=m.Link(port,log)
        try:
            establish_b3(link)
            link.command('L',b'S19')
            for row in (folder/'installer.s19').read_bytes().splitlines():link.send(row+b'\r\n');time.sleep(.04)
            reply=link.until(b'\r\nB3> ');assert not any(e in reply for e in (b'Bad',b'Protected',b'checksum'))
            link.command('G 2000',b'Y then Enter> ');link.send(b'Y\r')
            for i,(b,s) in enumerate(p['steps']):
                link.until(f'SEND 4096 BYTES FOR B{b}:{s:X}\r\n'.encode(),90)
                data=(folder/f'transfer-{i:02d}.bin').read_bytes()
                for j in range(0,4096,64):link.send(data[j:j+64]);time.sleep(.01)
                print('FLASH',board,f'B{b}:{s:X}',flush=True)
            text=link.until(p['completion_token'].encode(),90)+link.until(b'\r\nB3> ',90)
            assert b'2.0b35' in text;(folder/'installed-boot.txt').write_bytes(text)
            text=link.command('J3');assert b'2.0b35' in text and b'MONITOR B gen 0000002F VALID default' in text
            (folder/'j3.txt').write_bytes(text)
            text=link.command('VERSION');assert b'2.0b35' in text;(folder/'version.txt').write_bytes(text)
            text=link.command('R 1 CLOCK L');assert b'Done' in text
            if board!='2604':
                link.command('SRAM',b'SRAM> ')
                text=link.command(f'S CLK 2000 {0x2000+read(BUILD/"clock/build.json")["bytes"]-1:04X} 2000',b'SRAM> ')
                assert b'SRAM: 00' in text,text[-500:];(folder/'saved-clk.txt').write_bytes(text);link.command('Q')
            text=link.command('R CLOCK',b'CLOCK> ');assert b'CLOCK 1.10' in text
            text+=link.command('STATS',b'CLOCK> ')+link.command('Q');(folder/'stats.txt').write_bytes(text)
            report.update(passed=True,version='2.0b35',clock='1.10',j3=True,internal_all_sectors_verified=True,
                saved_clk_updated=board!='2604',stats_smoke_passed=True,asm_flash_unchanged=True,
                build_sha256=p['build_sha256'],installer_sha256=p['installer_sha256'])
        except Exception as e:report['error']=repr(e);raise
        finally:link.serial.close();save(folder/'hardware.json',report)
    print('PASS',board,'beta35; no backups or host readbacks',flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('stage',choices=('prepare','qualify','install'));p.add_argument('--board',choices=tuple(SERIALS));a=p.parse_args()
    if a.stage=='prepare':prepare()
    else:assert a.board;globals()[a.stage](a.board)
