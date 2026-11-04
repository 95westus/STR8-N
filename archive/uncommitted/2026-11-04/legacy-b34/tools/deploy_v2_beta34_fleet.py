"""Backup-bound beta34 fleet updates. No migration matrix or soak execution."""
import argparse
import json
import re
import sys
import time
from pathlib import Path

import deploy_v2_beta34_2512 as base
from rtc_boards import SERIALS
from run_v2_beta32_soak import batch

ROOT, DATA, BUILD = base.ROOT, base.DATA, base.BUILD
OUT = DATA / 'output/qualification/beta34-fleet-2026-10-16'
read, save, sha, images, m, io = base.read, base.save, base.sha, base.images, base.m, base.io
SOURCE = b'ORG $0200\nLDA #$21\nJSR $7E6D\nJMP $7E67\n'
BODY = bytes.fromhex('A921206D7E4C677E')


def plan_stage(board, label, before, target, order, prior, target_version, default_generation):
    final = [bytearray(b) for b in target]
    j = m.journal(before[3]); assert j
    cfg = bytearray(j[8:24]); assert cfg[14:] == m.config_sum(cfg)
    if default_generation is not None:
        cfg[7:13] = b'P\xB0' + default_generation.to_bytes(4, 'little')
    cfg[14:] = m.config_sum(cfg)
    counts = [int.from_bytes(j[24+3*i:27+3*i], 'little') for i in range(32)]
    old = counts[:]
    assert order[0] == (3,12) and len(order) == len(set(order))
    for b,s in order:
        counts[b*8+s-8] += 1; assert counts[b*8+s-8] < 0xFFFFFF
    final[3][0x4000:0x5000] = m.metadata(cfg,counts,int.from_bytes(j[4:8],'little')+1)+b'\xff'*(4096-128)
    changed = {(b,s) for b in range(4) for s in range(8,16)
               if before[b][(s-8)*4096:(s-7)*4096] != final[b][(s-8)*4096:(s-7)*4096]}
    assert changed == set(order), (changed,order)
    assert final[0] == before[0]
    assert final[3][0x1C00:0x2000] == before[3][0x1C00:0x2000]
    assert final[3][0x5000:0x6000] == before[3][0x5000:0x6000]
    mf = read(BUILD/'migrator/manifest.json'); assert len(order) <= mf['max_sectors']
    cells,entry = m.read_s19(BUILD/'migrator/rtc-migrator-2000.s19')
    cells[mf['count']] = len(order); cells[mf['commit_after']] = 0
    sy = mf['symbols']; call = sy['MIG_HALT']-3; tail = max(cells)+1
    assert bytes(cells[call+i] for i in range(3)) == b'\x20'+sy['MIG_PRINT'].to_bytes(2,'little')
    assert tail+11 < 0x6200
    # The final transfer may belong to B1. Select resident B3 from RAM
    # before fetching the ROM RESET vector, regardless of the last sector.
    cells.update(dict(enumerate(b'\x20'+sy['MIG_PRINT'].to_bytes(2,'little')+
        b'\xA9\x03\x20'+sy['V2W_SELECT'].to_bytes(2,'little')+b'\x4C\x04\xF0',tail)))
    cells.update(dict(enumerate(b'\x20'+tail.to_bytes(2,'little'),call)))
    token = 'MIGRATION VERIFIED; READY FOR J3'; message = token.encode()+b'\r\n\0'
    assert len(message) <= sy['MIG_BAD']-sy['MIG_DONE']
    cells.update(dict(enumerate(message,sy['MIG_DONE'])))
    pending = [bytearray(b) for b in before]; payloads = []; records = []
    for i,(b,s) in enumerate(order):
        off = (s-8)*4096; payload = bytearray(final[b][off:off+4096])
        address = (s<<12)+31 if b==3 and s in (10,11) else 0xE712 if (b,s)==(3,14) else 0xB003 if (b,s)==(1,11) and label=='clock' else 0
        if address:
            payload[address-(s<<12)] = 255
            if address == 0xB003: records.append(dict(bank=1,address=0xB000))
        row = bytes((s<<4,))+m.fnv(pending[b]).to_bytes(4,'little')+m.fnv(payload).to_bytes(4,'little')
        cells.update(dict(enumerate(row,mf['table']+9*i))); cells[mf['banks']+i] = b
        cells[mf['commits']+i] = b+1 if address else 0
        cells.update(dict(enumerate(address.to_bytes(2,'little')+b'\0\0',mf['commit_addresses']+4*i)))
        pending[b][off:off+4096] = payload
        if address: pending[b][address-0x8000] = 0 if address&255==31 else 0x3F
        payloads.append(payload)
    assert pending == final
    stage = OUT/board/label; (stage/'upgrade').mkdir(parents=True,exist_ok=False)
    (stage/'prior-verified').mkdir()
    for b in range(4):
        (stage/f'prior-verified/b{b}.bin').write_bytes(before[b])
        (stage/f'upgrade/expected-b{b}.bin').write_bytes(final[b])
    for i,p in enumerate(payloads): (stage/f'upgrade/transfer-{i:02d}.bin').write_bytes(p)
    installer = m.s19(cells,entry); (stage/'upgrade/installer.s19').write_bytes(installer)
    peak = max(counts); i = counts.index(peak)
    plan = dict(board=board,label=label,version=target_version,prior_directory='prior-verified',
        backup_directory=str(prior),steps=[dict(bank=b,sector=s) for b,s in order],
        prior_hashes=[sha(b) for b in before],expected_hashes=[sha(b) for b in final],
        installer_sha256=sha(installer),build_sha256=sha((BUILD/'build.json').read_bytes()),
        source_tool_sha256=sha(Path(__file__).read_bytes()),storage_update=True,commit_records=records,
        success_checkpoint=tail+8,return_stub_start=tail,explicit_return_bank=3,
        completion_token=token,counts_before=old,counts_after=counts,
        expected_wear_peak=f'Sector B{i//8}:{8+i%8:X}, max {peak} tracked erases.',
        physical_reset_required=False,returns_to_monitor=True)
    save(stage/'upgrade/plan.json',plan)
    print('PREPARED',board,label,len(order),'sectors',order,flush=True)
    return [bytes(b) for b in final]


def prepare():
    base.build_audit(); assert read(OUT/'fresh/manifest.json')['passed']
    candidate = images(BUILD/'candidate','b')
    fallback = (OUT/'fresh/2512/flash-1-b3.bin').read_bytes()[0x2000:0x3000]
    assert m.slot_valid(fallback,0xA0) and b'2.0b28' in fallback
    for board in ('2205','2609','2604'):
        prior = OUT/'fresh'/board; assert read(prior/'report.json')['passed']
        original = images(prior,'flash-1-b'); assert original == images(prior,'flash-2-b')
        assert original[1][0x6000:] == b'\xff'*8192, 'Do not overwrite an unknown B1:E/F image'
        before = original; stages = []
        if board == '2604':
            # Bound the known legacy CLOCK record before replacing that utility.
            old = (DATA/'output/qualification/fleet-as-is-backup-2026-10-16/2604/flash-1-b1.bin').read_bytes()
            assert before[1] == old
            assert before[2] == (DATA/'output/qualification/fleet-as-is-backup-2026-10-16/2604/flash-1-b2.bin').read_bytes()
            target = [bytearray(b) for b in before]
            target[1][0x3000:0x6000] = (BUILD/'clock/storage.bin').read_bytes()
            before = plan_stage(board,'clock',before,target,[(3,12),(1,13),(1,12),(1,11)],prior,'2.0b25',None)
            stages.append('clock')
        else:
            assert before[2] == (ROOT/'BUILD/v2-beta32-candidate/candidate/b2.bin').read_bytes(), 'Unexpected data in the shared utility bank'
            assert before[3][0x7000:] == candidate[3][0x7000:], 'Unexpected recovery ABI'
        target = [bytearray(b) for b in before]
        target[1][0x6000:] = candidate[1][0x6000:]
        target[2][:] = candidate[2]
        target[3][:0x1C00] = candidate[3][:0x1C00]
        target[3][0x2000:0x3000] = fallback
        target[3][0x3000:0x4000] = candidate[3][0x3000:0x4000]
        target[3][0x6000:] = candidate[3][0x6000:]
        assert target[1][:0x6000] == before[1][:0x6000]
        changed = lambda b,s:before[b][(s-8)*4096:(s-7)*4096]!=target[b][(s-8)*4096:(s-7)*4096]
        order = [(3,12)]+[(2,s) for s in range(15,7,-1) if changed(2,s)]
        order += [(1,s) for s in (15,14) if changed(1,s)]
        # Keep source A through new B publication and the fixed-F transition.
        order += [(3,s) for s in (8,9,14,11,15,10) if changed(3,s)]
        final = plan_stage(board,'firmware',before,target,order,prior,'2.0b34',46)
        stages.append('firmware')
        save(OUT/board/'plan.json',dict(board=board,stages=stages,final_hashes=[sha(b) for b in final],
                                     original_hashes=[sha(b) for b in original]))
    peer = images(OUT/'fresh/2512','flash-1-b')
    known = read(DATA/'output/qualification/beta34-2512-2026-10-16/hardware/report.json')
    assert [sha(b) for b in peer] == known['final_flash_hashes']
    save(OUT/'2512-already-current.json',dict(passed=True,board='2512',version='2.0b34',
         flash_written=False,full_flash_sha256=[sha(b) for b in peer],fresh_backup_passed=True))


def rehearse(board,label):
    import test_v2_rtc_upgrade as test
    stage = OUT/board/label; expected = images(stage/'upgrade','expected-b')
    prior = images(stage/'prior-verified','b'); parent = test.Memory; instances=[]
    class Memory(parent):
        def __init__(self,*a,**kw):
            super().__init__(*a,**kw); self.require_maintenance_commit=False; instances.append(self)
        def mutated(self,kind,address,value):
            if label=='firmware':
                if self.bank==3 and address==0xE712 and value==0x3F:
                    assert bytes(self.banks[1])==expected[1] and bytes(self.banks[2])==expected[2]
                if self.bank==3 and address==0xB01F and value==0:
                    assert bytes(self.banks[3][0x6000:0x7000])==expected[3][0x6000:0x7000]
                if self.bank==3 and address>>12==15:
                    assert bytes(self.banks[3][0x3000:0x4000])==expected[3][0x3000:0x4000]
                    assert bytes(self.banks[3][0x2000:0x3000])==prior[3][0x2000:0x3000]
                if self.bank==3 and address>>12==10:
                    assert bytes(self.banks[3][0x7000:])==expected[3][0x7000:]
            super().mutated(kind,address,value)
    test.Memory=Memory; argv=sys.argv
    try: sys.argv=['rehearse','--root',str(stage)]; test.main()
    finally: test.Memory=parent; sys.argv=argv
    if read(stage/'upgrade/plan.json').get('explicit_return_bank') == 3:
        assert instances[0].bank == 3
    proof=read(stage/'upgrade/model-check.json'); proof['publication_order_verified']=True
    save(stage/'upgrade/model-check.json',proof)


def functional(board,label):
    from test_v2_status import fresh,boot
    from test_v2_sram_store import console
    stage=OUT/board/label; p=read(stage/'upgrade/plan.json'); prior=Path(p['backup_directory'])
    expected=images(stage/'upgrade','expected-b'); array=(prior/'spi-sram-1.bin').read_bytes()
    cpu,mem=fresh(); mem.fast=True; mem.banks=[bytearray(b) for b in images(stage/'prior-verified','b')]; mem.spi.banks=mem.banks
    mem.spi.devices[0].data[:]=array; mem.bus.rtc_regs[:32]=(prior/'rtc-registers-1.bin').read_bytes()
    mem.bus.ee[:128]=(prior/'eeprom-1.bin').read_bytes(); mem.bus.ee[240:248]=(prior/'eeprom-protected-1.bin').read_bytes()
    mem.bus.ee[255]=(prior/'eeprom-status-1.bin').read_bytes()[0]
    boot(cpu); mem.banks=[bytearray(b) for b in expected]; mem.spi.banks=mem.banks
    cells,_=m.read_s19(stage/'upgrade/installer.s19')
    for a,v in cells.items(): mem.ram[a]=v
    sy=read(BUILD/'migrator/manifest.json')['symbols']; n=sy['V2W_END']-0x7800
    mem.ram[0x7800:0x7800+n]=bytes(cells[sy['MIG_WORKER']+i] for i in range(n))
    last=p['steps'][-1]['bank']
    mem[0x7FEC]=(mem.ram[0x7FEC]&0x11)+(0xCC,0xCE,0xEC,0xEE)[last]
    cpu.x=sy['MIG_DONE']&255; cpu.y=sy['MIG_DONE']>>8
    cpu.pc=p.get('return_stub_start',p['success_checkpoint']-3); mem.tx.clear()
    boot(cpu); transcript=bytearray(mem.tx); assert p['version'].encode() in mem.tx
    def cmd(line):
        print('MODEL',board,label,line,flush=True)
        out=console(cpu,mem,line.encode()+b'\r',limit=100000000); transcript.extend(out)
        (stage/'upgrade/functional-progress.txt').write_bytes(transcript); return out
    if label=='clock':
        assert b'CLOCK 1.9' in cmd('R CLOCK'); cmd('Q')
    else:
        assert b'ASM 0.5' in cmd('ASM'); cmd('PASTE')
        text=console(cpu,mem,SOURCE.replace(b'\n',b'\r')+b'.\r',limit=100000000); transcript.extend(text)
        text=cmd('ASM'); assert b'RAM $0200-$0207' in text and b'S 1 AUTO 0200 0207 PROGRAM' in text
        assert bytes(mem.ram[0x200:0x208])==BODY; cmd('QUIT'); text=cmd('G 0200'); assert b'!' in text and b'B3>' in text
        text=cmd('BATCH MAINT;Q;SRAM;Q;WORK;Q;EDU;Q')
        assert b'BATCH done' in text and all(x in text for x in (b'MAINT 2.4',b'SRAM 1.4',b'WORK 1.4',b'EDU 1.4'))
        if board=='2205' or board=='2604': assert b'CLOCK 1.9' in cmd('R CLOCK'); cmd('Q')
        else: assert b'CLOCK 1.9' in cmd('BATCH SRAM;G CLK;Q')
        assert b'2.0b34' in cmd('J3')
    assert [bytes(b) for b in mem.banks]==expected
    assert bytes(mem.spi.devices[0].data)==array and bytes(mem.bus.ee[:128])==(prior/'eeprom-1.bin').read_bytes()
    save(stage/'upgrade/functional.json',dict(passed=True,build_sha256=p['build_sha256'],expected_hashes=p['expected_hashes'],
         installer_return_verified=True,source_sha256=sha(SOURCE),sram_sha256=sha(array),no_persistent_test_writes=True))


def qualify():
    for board in ('2205','2609','2604'):
        for label in read(OUT/board/'plan.json')['stages']: rehearse(board,label); functional(board,label)


def audit(board):
    base.build_audit(); p=read(OUT/board/'plan.json')
    for label in p['stages']:
        stage=OUT/board/label; plan=read(stage/'upgrade/plan.json')
        original=OUT/'deploy-tool-before-return-fix.py'
        sources=[sha(Path(__file__).read_bytes())]
        if original.exists():sources.append(sha(original.read_bytes()))
        assert plan['source_tool_sha256'] in sources
        if plan.get('return_fix_source_sha256'):
            assert plan['return_fix_source_sha256']==sha((ROOT/'tools/finish_v2_beta34_2604.py').read_bytes())
        assert plan['build_sha256']==sha((BUILD/'build.json').read_bytes())
        assert plan['installer_sha256']==sha((stage/'upgrade/installer.s19').read_bytes())
        for name in ('model-check','functional'):
            proof=read(stage/f'upgrade/{name}.json'); assert proof['passed'] and proof['expected_hashes']==plan['expected_hashes']
        for b,h in enumerate(plan['expected_hashes']): assert sha((stage/f'upgrade/expected-b{b}.bin').read_bytes())==h
    return p


def install(board):
    p=audit(board); prior=OUT/'fresh'/board; out=OUT/board/'hardware'; out.mkdir(exist_ok=False)
    original=None; needed=False; mode='monitor'; result=dict(board=board,passed=False,application_ram_restored=False,soak_started=False,migration_matrix_run=False)
    with base.serial_lease('beta34-fleet-'+board,priority=True),(out/'serial.jsonl').open('x') as log:
        link=m.Link(io.port(board),log)
        def cmd(line,prompt=b'\r\nB3> '):
            text=link.command(line,prompt); print('LIVE',board,line,flush=True); return text
        def flash(stage,hashes):
            for b in range(4):
                prompt=f'\r\nB{b}> '.encode();cmd(f'B{b}',prompt)
                data=b''.join(link.dump(a,a+4095,prompt) for a in range(0x8000,0x10000,4096))
                (out/f'{stage}-b{b}.bin').write_bytes(data);assert sha(data)==hashes[b],(stage,b)
                print('PASS',board,stage,'B'+str(b),flush=True)
            cmd('B3')
        try:
            base.establish_b3(link);original=io.dump_ram(link);assert original==io.dump_ram(link)
            (out/'ram-prior.bin').write_bytes(original);flash('preflight',p['original_hashes'])
            needed=True; save(out/'ram-restore-needed.json',dict(needed=True,sha256=sha(original)))
            before=io.retained(link,out,'before')
            for n in ('eeprom','eeprom-protected','eeprom-status','rtc-sram'):assert before[n]==(prior/f'{n}-1.bin').read_bytes()
            assert before['rtc-registers'][7:]==(prior/'rtc-registers-1.bin').read_bytes()[7:]
            for label in p['stages']:
                stage=OUT/board/label; plan=read(stage/'upgrade/plan.json')
                base.load_image(link,stage/'upgrade/installer.s19');mode='installer'
                cmd('G 2000',b'Y then Enter> ');link.send(b'Y\r')
                for i,step in enumerate(plan['steps']):
                    link.until(f'SEND 4096 BYTES FOR B{step["bank"]}:{step["sector"]:X}\r\n'.encode(),90)
                    data=(stage/f'upgrade/transfer-{i:02d}.bin').read_bytes()
                    for j in range(0,4096,64):link.send(data[j:j+64]);time.sleep(.01)
                    print('FLASH',board,label,f'B{step["bank"]}:{step["sector"]:X}',flush=True)
                text=link.until(plan['completion_token'].encode(),90)+link.until(b'\r\nB3> ',90)
                mode='monitor';(out/f'{label}-return.txt').write_bytes(text);assert plan['version'].encode() in text
                flash(label,plan['expected_hashes'])
            text=cmd('J3'); assert b'2.0b34' in text and b'MONITOR B gen 0000002E VALID default' in text
            assert plan['expected_wear_peak'].encode() in text;(out/'j3-boot.txt').write_bytes(text)
            mode='asm';assert b'ASM 0.5' in cmd('ASM',b'ASM> ')
            cmd('PASTE',b'Paste source; . ends, Ctrl-C cancels\r\n')
            for line in SOURCE.splitlines():link.send(line+b'\r');time.sleep(.04)
            link.send(b'.\r');link.until(b'ASM> ')
            text=cmd('ASM',b'ASM> ');assert b'RAM $0200-$0207' in text and b'S 1 AUTO 0200 0207 PROGRAM' in text
            (out/'assembly-summary.txt').write_bytes(text);cmd('QUIT');mode='monitor'
            assert link.dump(0x200,0x207)==BODY;assert b'!' in cmd('G 0200')
            text=batch(link,'MAINT;Q;SRAM;Q;WORK;Q;EDU;Q')
            assert b'BATCH done' in text and all(x in text for x in (b'MAINT 2.4',b'SRAM 1.4',b'WORK 1.4',b'EDU 1.4'))
            (out/'providers.txt').write_bytes(text)
            if board in ('2205','2604'):text=cmd('R CLOCK',b'CLOCK> ')
            else:text=cmd('SRAM',b'SRAM> ');text+=cmd('G CLK',b'CLOCK> ')
            assert b'CLOCK 1.9' in text;text+=cmd('STATUS',b'CLOCK> ')+cmd('HISTORY',b'CLOCK> ')+cmd('Q')
            (out/'clock.txt').write_bytes(text)
            link.send(b'J3\r');text=link.until(b'A/B/S,Enter default [3s]: ');link.send(b'A');text+=link.until(b'\r\nB3> ')
            assert b'2.0b28' in text;(out/'fallback-boot.txt').write_bytes(text)
            text=cmd('J3');assert b'2.0b34' in text;(out/'final-boot.txt').write_bytes(text)
            for name in ('VERSION','TIME','APPS','T 1','M1','W','C'):
                text=cmd(name);(out/f'query-{name.replace(" ","-")}.txt').write_bytes(text)
                if name=='VERSION':assert b'2.0b34' in text
                if name=='APPS':assert b'ASM installed B1:E000' in text
            flash('final',p['final_hashes'])
            array=io.array_read(link,'Final SRAM '+board);assert array==(prior/'spi-sram-1.bin').read_bytes();(out/'final-sram.bin').write_bytes(array)
            after=io.retained(link,out,'after')
            for n in ('eeprom','eeprom-protected','eeprom-status','rtc-sram'):assert before[n]==after[n]
            assert before['rtc-registers'][7:]==after['rtc-registers'][7:]
            assert before['rtc-registers'][3]&0x38==after['rtc-registers'][3]&0x38
            result.update(passed=True,version='2.0b34',asm='0.5',clock='1.9',full_flash_verified=True,
                native_utilities_verified=True,j3_verified=True,fallback='2.0b28 A',sram_preserved=True,
                eeprom_rtc_history_identity_preserved=True,b0_preserved=True,final_hashes=p['final_hashes'],
                build_sha256=plan['build_sha256'],source_tool_sha256=sha(Path(__file__).read_bytes()))
        except Exception as error:result['error']=repr(error);raise
        finally:
            try:
                if needed and original is not None:
                    if mode=='installer':result['installer_state_uncertain']=True
                    else:
                        if mode=='asm':link.send(b'\x03');link.until(b'ASM> ',10);link.command('QUIT')
                        base.establish_b3(link);io.restore_ram(link,original,out);result['application_ram_restored']=True
            finally:
                result['passed']=result['passed'] and result['application_ram_restored'];link.serial.close();save(out/'report.json',result)
    print('PASS beta34 fleet board',board,flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('stage',choices=('prepare','qualify','install'));parser.add_argument('--board',choices=('2205','2609','2604'))
    args=parser.parse_args()
    if args.stage=='install':assert args.board;install(args.board)
    else:globals()[args.stage]()
