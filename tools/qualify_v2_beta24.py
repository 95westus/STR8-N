"""Preserving physical beta24 qualification on 2604/2609.

NAME appends and two EDU configuration appends are intentional. Restores the
original name and EDU mode; never erases flash or changes RTC administration.
"""
import argparse
import binascii
import json
import re
from pathlib import Path

from beta4_migration import Link, journal, metadata, config_sum
from rtc_boards import SERIALS
from rtc_prompt_sync import establish_b3
from serial_test_coordination import serial_lease
from serial.tools.list_ports import comports
from qualify_v2_spi_install import load_image
from update_v2_beta24 import audit, sha, ROOT
import run_beta23_soak as smoke


def valid_names(tail):
    result=[]
    for offset in range(0,len(tail),32):
        r=tail[offset:offset+32]
        if r[:4] == b'BN\x01\0' and r[31] == 0 and r[8] <= 8:
            assert int.from_bytes(r[28:30],'little') == binascii.crc_hqx(r[:28],0xFFFF)
            result.append((int.from_bytes(r[4:8],'little'),r[9:9+r[8]].decode()))
    return result


def qualify(board, out):
    audit()
    source=ROOT/'output/qualification/beta24-install-2026-10-14'/board
    plan=json.loads((source/'upgrade/plan.json').read_text())
    expected=[(source/f'upgrade/expected-b{b}.bin').read_bytes() for b in range(4)]
    port=next(p.device for p in comports() if p.serial_number == SERIALS[board])
    out.mkdir(parents=True,exist_ok=False)
    checks=[];report=dict(passed=False,board=board,port=port,checks=checks,physical_reset_confirmed_by_operator=True)
    def save(): (out/'report.json').write_text(json.dumps(report,indent=2)+'\n')
    def passed(label): checks.append(label);save();print('PASS',board,label,flush=True)
    with serial_lease('beta24-tests'):
        with (out/'serial.jsonl').open('x') as log:
            l=Link(port,log)
            try:
                establish_b3(l)
                def bank(b):
                    prompt=f'\r\nB{b}> '.encode();l.command(f'B{b}',prompt)
                    data=b''.join(l.dump(a,a+4095,prompt) for a in range(0x8000,0x10000,4096))
                    l.command('B3');return data
                for b in range(4):
                    data=bank(b);assert data == expected[b],f'Installed B{b} mismatch'
                    (out/f'initial-b{b}.bin').write_bytes(data)
                passed('complete 131072-byte installed image equals verified beta24 plan')
                initial3=expected[3];initial_tail=initial3[0x1C00:0x2000]
                names=valid_names(initial_tail);original=max(names)[1] if names else ''
                free=sum(initial_tail[i:i+32] == b'\xff'*32 for i in range(0,1024,32))
                assert free >= (4 if original else 3),'Insufficient append space for preserving NAME tests'
                baseline_index=Path(json.loads((ROOT/'output/qualification/active-rtc-campaign.json').read_text())['baseline_index'])
                baseline=next(b for b in json.loads(baseline_index.read_text())['boards'] if b['board']==board)
                rtc=smoke.clock_snapshot(l,baseline);smoke.guards(l)
                def cold(slot,label,name):
                    text=l.command('J3',b'Enter default [3s]: ');l.send(slot.encode());text+=l.until(b'\r\nB3> ')
                    (out/(label+'.txt')).write_bytes(text)
                    assert b'STR8-N 2.0b24' in text,text
                    if name: assert ('Board: '+name+'\r\n').encode() in text,text
                    else: assert b'Board:' not in text,text
                    return text
                cold('A','initial-slot-A',original);cold('B','initial-slot-B',original)
                passed('beta24 A/B cold startup and original name display')
                l.command('R MAINT',b'BM> ')
                def tail():
                    # MAINT D addresses its sector buffer, not banked flash.
                    l.command('Q');data=l.dump(0x9C00,0x9FFF)
                    l.command('R MAINT',b'BM> ');return data
                current_tail=tail();assert current_tail == initial_tail
                def query(name):
                    result=l.command('NAME',b'BM> ')
                    assert ('Board: '+(name or 'unnamed')).encode() in result,result
                def change(name):
                    nonlocal current_tail
                    values=valid_names(current_tail);old=max(values)[1] if values else ''
                    if old == name: query(name);return
                    offset=next(i for i in range(0,1024,32) if current_tail[i:i+32] == b'\xff'*32)
                    seq=max((r[0] for r in values),default=0)+1
                    r=bytearray(b'\xff'*32);r[:8]=b'BN\x01\0'+seq.to_bytes(4,'little')
                    r[8]=len(name);r[9:17]=name.encode().ljust(8,b'\0')
                    r[28:30]=binascii.crc_hqx(r[:28],0xFFFF).to_bytes(2,'little');r[31]=0
                    target=bytearray(current_tail);target[offset:offset+32]=r
                    l.command('NAME '+(name or 'CLEAR'),b'Save board name? Type YES: ')
                    result=l.command('YES',b'BM> ')
                    assert ('Board: '+(name or 'unnamed')).encode() in result,result
                    actual=tail();assert actual == target,'NAME did not make exactly one valid append'
                    current_tail=actual;query(name)
                try:
                    query(original)
                    for command in ('NAME ','NAME 123456789','NAME TWO WORD','NAME A B'):
                        reply=l.command(command,b'BM> ');assert b'NAME [1-8' in reply,reply
                    for confirmation in ('NO','Y'):
                        l.command('NAME TEST24',b'Save board name? Type YES: ')
                        l.command(confirmation,b'BM> ')
                    assert tail() == current_tail
                    passed('NAME query, overlength/whitespace rejection and non-YES cancellation perform no writes')
                    testname='LAB-'+board
                    change(testname)
                    assert tail() == current_tail
                    l.command('NAME '+testname,b'BM> ');assert tail() == current_tail
                    passed('eight-character NAME set, CRC/sequence/commit readback and identical-name no-op')
                    l.command('Q');assert b'Board:' not in l.command('M1')
                    cold('A','named-slot-A',testname);cold('B','named-slot-B',testname)
                    l.command('R MAINT',b'BM> ');query(testname)
                    passed('named A/B J3 retention and quiet monitor return')
                    change(board);l.command('Q');cold('A','renamed',board)
                    l.command('R MAINT',b'BM> ');query(board)
                    passed('rename readback and cold-start retention')
                    change('');l.command('Q');cold('A','cleared','')
                    l.command('R MAINT',b'BM> ');query('')
                    passed('clear readback, cold-start persistence and omitted unnamed boot line')
                finally:
                    change(original);l.command('Q')
                expected3=bytearray(initial3);expected3[0x1C00:0x2000]=current_tail
                # Configuration appends are accounted exactly; no erase is used.
                j=journal(initial3);cfg=bytearray(j[8:24]);assert cfg[13]==0
                counts=[int.from_bytes(j[24+3*i:27+3*i],'little') for i in range(32)]
                seq=int.from_bytes(j[4:8],'little');changed=False
                def mode(target):
                    nonlocal seq,expected3,changed
                    l.command('R EDU',b'EDU> ')
                    l.command(target,b'Apply after RESET? [y/N]: ')
                    assert b'Saved; RESET required.' in l.command('Y',b'EDU> ')
                    l.command('Q');changed=target=='OFF'
                    cfg[13]=0xA5 if target=='OFF' else 0;cfg[14:]=config_sum(cfg)
                    offset=max(i for i in range(0,4096,128) if expected3[0x4000+i:0x4000+i+128]!=b'\xff'*128)+128
                    assert offset < 4096,'Configuration journal full'
                    seq+=1;expected3[0x4000+offset:0x4080+offset]=metadata(cfg,counts,seq)
                    cold('A','edu-'+target,original)
                try:
                    mode('OFF')
                    assert l.dump(0x7D04,0x7D0B)==b'SV\x01\0\0\0\xff\x66'
                    old=l.dump(0x6500,0x66FF)
                    try:
                        pattern=bytes((i*13+17)&255 for i in range(512));l.write_ram(0x6500,pattern)
                        assert l.dump(0x6500,0x66FF)==pattern
                    finally:l.write_ram(0x6500,old)
                finally:
                    if changed:mode('ON')
                smoke.guards(l);passed('EDU OFF/ON cold-start, reclaimed RAM and original ON restored')
                assert smoke.clock_snapshot(l,baseline)==rtc
                groups={}
                for group in ('monitor','clock','edu','sram','work','maint'):
                    groups[group]=smoke.commands(l,group)
                (out/'command-regression.json').write_text(json.dumps(groups,indent=2)+'\n')
                probes=ROOT/'BUILD/v2-board-regression';pm=json.loads((probes/'build.json').read_text())['probes']
                assert load_image(l,probes/'abi.s19')==pm['abi']['sha256']
                assert b'RAM ABI: PASS' in l.command('G 2000')
                pointers=l.dump(0x7E00,0x7E1B)
                assert load_image(l,probes/'irq.s19')==pm['irq']['sha256']
                assert b'V2 BRK / VIA1 IRQ / A-X-Y / STACK / RTI: PASS' in l.command('G 2000')
                assert l.dump(0x7E00,0x7E1B)==pointers
                passed('monitor/CLOCK/EDU/SRAM/WORK/MAINT command smoke, RAM ABI and actual BRK/VIA1 IRQ')
                for group,address in (('rtc-sram-20',0x20),('rtc-sram-50',0x50)):
                    dest=out/group;dest.mkdir();smoke.rtc_sram(l,dest,1,address)
                dest=out/'external-sram';dest.mkdir();smoke.external_sram(l,dest,1)
                passed('RTC SRAM and external SRAM pattern write/read/restore with verified original restoration')
                assert smoke.clock_snapshot(l,baseline)==rtc
                hashes=[]
                for b in range(4):
                    data=bank(b);assert data==(expected3 if b==3 else expected[b]),f'Unexpected final B{b} change'
                    (out/f'final-b{b}.bin').write_bytes(data);hashes.append(sha(data))
                passed('exact final flash: only intended NAME/config appends; saved records, recovery and wear counts preserved')
                report.update(passed=True,original_name_restored=original,original_edu_restored=True,
                              final_flash_hashes=hashes,rtc_settings_identity_history_preserved=True,
                              physical_power_cycle_pending=True,physical_nmi_pending=True)
                pending=json.loads((source/'upgrade/install/reset-pending.json').read_text())
                pending['physical_reset_pending']=False
                (source/'upgrade/install/reset-pending.json').write_text(json.dumps(pending,indent=2)+'\n')
            except Exception as error:
                report['error']=repr(error);raise
            finally:save();l.serial.close()


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--root',type=Path,required=True)
    p.add_argument('--board',choices=('2604','2609'),required=True);a=p.parse_args();qualify(a.board,a.root/a.board)
