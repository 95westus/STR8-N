"""Offline ASM 0.4 source -> independent bytes -> chess -> S/T/R proof."""
import hashlib
import json
from pathlib import Path
import re
import shutil
import build_microchess_asm04 as b
import test_asm as a
import build_v2_config as compiler
import beta4_migration as records


def main():
    b.OUT=b.ROOT/'BUILD/microchess-asm05'
    info=b.prepare();out=b.OUT
    source=(b.SRC/'microchess.asm').read_bytes()
    cpu,m=a.setup(shell=True)
    original=[bytes(bank) for bank in m.banks]
    retained=(bytes(m.spi.devices[0].data),bytes(m.bus.ee),bytes(m.bus.rtc_regs))
    transcript=bytearray()
    def cmd(s):
        text=a.command(cpu,s.encode()+b'\r');transcript.extend(text)
        print('MODEL',s,flush=True);(out/'progress.txt').write_bytes(transcript);return text
    assert b'Paste source' in cmd('PASTE')
    text=a.command(cpu,source.replace(b'\r\n',b'\n').replace(b'\n',b'\r')+b'.\r');transcript.extend(text)
    assert b'Error' not in text,text[-200:]
    assert int.from_bytes(m.ram[a.S['SRC_END']:a.S['SRC_END']+2],'little')-a.SRC==info['packed_source_bytes']
    text=cmd('ASM');assert b'OK ' in text,text
    save_line=re.search(rb'\r\n(S 1 AUTO 0200 [0-9A-F]{4} PROGRAM)\r\n',text)
    assert save_line,text
    save_command=save_line[1].decode()
    (out/'assembly-summary.txt').write_bytes(text)
    n=int.from_bytes(m.ram[a.S['RESULT_LEN']:a.S['RESULT_LEN']+2],'little')
    body=bytes(m.ram[0x200:0x200+n]);assert body
    assert b'0200:' in cmd('DUMP')
    assert b'B3>' in cmd('QUIT')
    print('PASS actual PASTE and ASM 0.4 compilation',n,'bytes',flush=True)
    # Independently compile the readable source, not the compact symbol map.
    readable=(b.SRC/'microchess-readable.asm').read_text()
    oracle=[]
    for line in readable.splitlines():
        if line.startswith(';') or line.startswith('ORG '):continue
        line=re.sub(r'^(\w+) = ',r'\1 EQU ',line)
        line=re.sub(r'\b(?:BYTE|TEXT)\b','DB',line)
        oracle.append(('' if ':' in line or ' EQU ' in line else ' ')+line)
    path=out/'oracle.asm';path.write_text(' MODULE MICROCHESS\n CHIP W65C02S\n CODE\n'+'\n'.join(oracle)+'\n')
    compiler.OUT=out;compiler.SOURCE=b.ROOT/'src/v2-config';(out/'asm').mkdir(exist_ok=True)
    memory,symbols=compiler.assemble('microchess-oracle',0x200,shutil.which('wdc02as'),shutil.which('wdcln'),source_file=path)
    independent=bytes(memory[x] for x in range(0x200,0x200+len(memory)))
    assert body==independent,'Readable WDC build differs from on-board assembler output'
    # Both C/V states must survive output; Microchess uses those flags for
    # move/capture analysis. Hold the public call to a hostile stub so the
    # test does not depend on a console backend accidentally preserving them.
    registers={r:getattr(cpu,r) for r in ('pc','sp','a','x','y','p')}
    stack=bytes(m.ram[0x100:0x200])
    target=bytes(m.ram[0x7E6D:0x7E70]);m.ram[0x7E6D:0x7E70]=b'\x18\xB8\x60'
    for flags in (0,0x41):
        cpu.a=ord('.');cpu.x=0x12;cpu.y=0x34;cpu.p=cpu.UNUSED|cpu.INTERRUPT|flags
        a.model.call(cpu,symbols['SYSCHOUT'],10000)
        assert (cpu.a,cpu.x,cpu.y)==(ord('.'),0x12,0x34) and cpu.p&0x41==flags
    m.ram[0x7E6D:0x7E70]=target
    m.ram[0x100:0x200]=stack
    for r,v in registers.items():setattr(cpu,r,v)
    (out/'microchess.bin').write_bytes(body)
    (out/'microchess.s19').write_bytes(records.s19(dict(enumerate(body,0x200)),0x200))
    print('PASS byte-identical readable WDC / compact ASM output',flush=True)
    text=cmd('G 0200');assert b'Microchess Copyright 1976 Peter Jennings benlo.com' in text
    assert b'|WK|' in text and b'|BK|' in text
    assert bytes(m.ram[0x10:0x30])==bytes.fromhex('0304000702050106101711161215141373747077727571766067616662656463')
    assert b'?' in text
    def keys(s):
        text=a.command(cpu,s.encode());transcript.extend(text)
        print('KEYS',repr(s),flush=True);return text
    keys('P');assert m.ram[0x10+15]==0x33,'Opening pawn move was not made'
    keys('6343\r');assert m.ram[0x10+31]==0x43,'Human pawn move was not made'
    keys('E');assert m.ram[0xB7]==1
    keys('C');assert m.ram[0x10+15]==0x13 and m.ram[0x10+31]==0x63
    assert b'B3>' in keys('Q')
    assert bytes(m.ram[0x200:0x200+n])==body and m.ram[0xF4]==0
    print('PASS initialized board, computer opening, human move, exchange, reset and public HOLD',flush=True)
    end=0x200+n-1
    assert save_command==f'S 1 AUTO 0200 {end:04X} PROGRAM'
    assert b'Done' in cmd(save_command)
    table=cmd('T 1');assert b'PROGRAM' in table and f'0200-{end:04X}'.encode() in table
    m.ram[0x200:0x200+n]=bytes(n)
    assert b'Done' in cmd('R 1 PROGRAM L')
    assert bytes(m.ram[0x200:0x200+n])==body
    assert b'Microchess Copyright' in cmd('R 1 PROGRAM')
    assert b'B3>' in keys('Q') and m.bank==3
    assert all(bytes(m.banks[i])==original[i] for i in (0,2,3))
    assert bytes(m.banks[1][0x6000:])==original[1][0x6000:]
    assert not any(event[0]=='erase' for event in m.events)
    assert retained==(bytes(m.spi.devices[0].data),bytes(m.bus.ee),bytes(m.bus.rtc_regs))
    (out/'workflow.txt').write_bytes(transcript)
    report=dict(info,passed=True,executable_bytes=n,last_address=end,record_bytes=n+24,
        binary_sha256=hashlib.sha256(body).hexdigest(),source_sha256=hashlib.sha256(source).hexdigest(),
        candidate_build_sha256=hashlib.sha256((a.OUT.parent/'build.json').read_bytes()).hexdigest(),
        actual_paste_assemble_verified=True,printed_save_command_verified=True,assembler_version=a.REPORT['version'],readable_wdc_byte_comparison=True,board_and_moves_verified=True,
        store_table_restore_verified=True,retained_data_preserved=True,flash_erases=0,
        source_files_sha256={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(b.SRC.iterdir()) if p.is_file()})
    (out/'qualification.json').write_text(json.dumps(report,indent=2)+'\n')
    (a.OUT.parent/'beta34-microchess.json').write_text(json.dumps(report,indent=2)+'\n')
    print('PASS Microchess source, executable, moves and S/T/R; model only, no board access',flush=True)


if __name__=='__main__':main()
