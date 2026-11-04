"""Prepare/verify a RAM-only, exact-F/source-bound first journal initializer.

No serial import or live command. The BIN is an application for F's raw L at
$0200, never a sector image. The two prospective erases are only reserved in
the plan; the owner's authoritative wear history is not changed here.
"""
import argparse
import json
import shutil
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path[:0] = [str(ROOT / 'tools'), str(HERE)]
from installer.engine import legacy_transport as wire, runtime as r
from installer.common import save
from str8build.assemble import Assembly
from str8build.formats import read_s19
from build import long_branches
from deployment_plan import snapshot, snbt_records
from wdc_b15_2609 import TARGET, GENERATION, WDC_SHA, digest, bind

SESSION = ROOT / 'output/qualification/2609-b15-onboarding-20261027T212009Z'
F_SHA = '1a1db354d49d8a9a555be1100b74f3e4b0ed14d3156f3a333086853a845717b8'
ORDER = (0xd000, 0xc000)


def rows(history):
    counts = history['counts']
    r.require(len(counts) == 32 and all(type(n) is int and 0 <= n <= 0xffffff for n in counts), 'Invalid tracked wear')
    r.require(history['board'] == '2609' and history['history_unknown_mask'] == 'ffffffff', 'Unknown-lifetime provenance required')
    seq = history['sequence']
    r.require(1 <= seq <= 0xfffffffd, 'Sequence exhausted')
    cfg = bytes.fromhex(history['config'])
    r.require(len(cfg) == 16 and cfg[14:] == wire.config_sum(cfg) and cfg[1] == 0, 'Invalid/unsafe legacy configuration')
    # Preserve the legacy settings as history. F reads only the SNBT header;
    # it does not apply the legacy console byte from the record body. New SNBT
    # choices default to recovery with no opaque launch enabled, pinned to b15.
    reserved = counts.copy()
    for address in ORDER:
        i = 24 + (address >> 12) - 8
        r.require(reserved[i] < 0xffffff, 'Wear counter exhausted')
        reserved[i] += 1
    result = []
    for n in range(2):
        row = bytearray(snapshot(bytes(cfg), reserved, seq + n + 1, 'A', GENERATION))
        row[7], row[13] = ord('S'), 0
        row[30:32] = wire.crc(row[:30]).to_bytes(2, 'little')
        row[252:254] = wire.crc(row[:252]).to_bytes(2, 'little')
        result.append(bytes(row))
    return reserved, bytes(cfg), result


def db(label, data):
    lines = [label + ':']
    for start in range(0, len(data), 16):
        lines.append('        DB ' + ','.join(f'${v:02X}' for v in data[start:start+16]))
    return '\n'.join(lines) + '\n'


def prepare(out, session=SESSION):
    out, session = Path(out).resolve(), Path(session).resolve()
    r.require(not out.exists(), 'Fresh output required')
    state = r.read(session / 'session.json')
    report_path = session / 'step03-F-only-install/report.json'
    report = r.read(report_path)
    history_path = Path(state['wear_history'])
    history = r.read(history_path)
    r.require(state['board'] == '2609' and state['b15_F_installed'] and not state['MON_installed'] and not state['journals_initialized'], '2609 F-only checkpoint required')
    r.require(report['passed'] and report['transaction_device_verified'] and report['REC_verified'] and report['post_REC_commands'] == 0, 'Verified single-F hardware checkpoint required')
    r.require(history['device_erase_program_verify_passed'] and not history['onboard_journal_initialized'] and history['execution_report_sha256'] == digest(report_path), 'Verified wear execution binding required')
    previous = Path(report['plan']).parent
    source = [(previous / f'expected-b{n}.bin').read_bytes() for n in range(4)]
    r.valid_banks(source)
    r.require(r.hashes(source) == report['expected_hashes'] and digest(TARGET/'payload/f-offline-component.bin') == F_SHA and r.sha(source[0]) == WDC_SHA, 'Changed F-only source or B0 backup')
    r.require(r.sha(source[3][-4096:]) == F_SHA and not snbt_records(source), 'Exact b15 F with no SNBT required')
    reserved, cfg, journal = rows(history)
    symbols = r.read(TARGET/'symbols.json')
    worker = read_s19(TARGET/'s/core/str8n-v2-worker.s19')
    vectors = read_s19(TARGET/'s/core/str8n-v2-vectors.s19')
    helper_ranges = [(min(c), max(c)+1, bytes(c[a] for a in range(min(c), max(c)+1))) for c in (worker, vectors)]
    r.require([(a,b) for a,b,_ in helper_ranges] == [(0x7800,0x7be8),(0x7e20,0x7ee4)], 'Unexpected b15 RAM ABI')
    out.mkdir(parents=True)
    core = out/'s/core'
    core.mkdir(parents=True)
    (out/'payload').mkdir()
    for name in ('str8n-v2-eq.inc', 'service-eq.inc'):
        shutil.copy2(TARGET/'s/include'/name, core/name)
    shutil.copy2(TARGET/'s/core/worker-public-symbols.inc', core/'worker-public-symbols.inc')
    params = db('JI_RAM_RANGES', b''.join(a.to_bytes(2,'little')+b.to_bytes(2,'little') for a,b,_ in helper_ranges))
    params += db('JI_RAM_HASHES', b''.join(wire.fnv(body).to_bytes(4,'little') for _,_,body in helper_ranges))
    params += db('JI_BANK_HASHES', b''.join(wire.fnv(body).to_bytes(4,'little') for body in source))
    wear_text = '2609 tracked lower bounds; prior lifetime UNKNOWN (FFFFFFFF)\r\n'
    for bank in range(4):
        wear_text += f'B{bank} 8-F before: '+ ' '.join(map(str,history['counts'][bank*8:bank*8+8]))+'\r\n'
    wear_text += f'Planned C {history["counts"][28]}->{reserved[28]}, D {history["counts"][29]}->{reserved[29]}; F stays {reserved[31]}. Both erases reserved before D.\r\n'
    params += db('JI_WEAR_TEXT', wear_text.encode('ascii')+b'\0')
    params += db('JI_ROW_D', journal[0]) + db('JI_ROW_C', journal[1])
    (core/'journal-init-params.inc').write_text(params, encoding='ascii')
    (core/'ram-journal-init.asm').write_text(long_branches((HERE/'ram-journal-init-2609.asm').read_text()), encoding='ascii')
    a = object.__new__(Assembly)
    a.out, a.assembler, a.linker = out, shutil.which('wdc02as'), shutil.which('wdcln')
    r.require(a.assembler and a.linker, 'WDC assembler/linker required')
    a.symbols, a.compiled = {}, []
    image, sy = a.link('core','ram-journal-init',0x200,'JI_END')
    r.require(sy['JI_START'] == 0x200 and sy['JI_END'] <= 0x6200 and sy['JI_SELF_HASH'] == sy['JI_END']-4, 'RAM image overlaps scratch')
    image = image[:-4] + wire.fnv(image[:-4]).to_bytes(4,'little')
    a.emit('2609-journal-init-RAM.bin', image)
    save(out/'symbols.json', sy)
    expected = list(map(bytearray, source))
    for address,row in zip(ORDER,journal):
        expected[3][address-0x8000:address-0x7000] = row + b'\xff'*3840
    for n in range(4):
        (out/f'source-b{n}.bin').write_bytes(source[n])
        (out/f'expected-b{n}.bin').write_bytes(expected[n])
    for name,row in zip(('D','C'),journal):
        (out/f'snapshot-{name}.bin').write_bytes(row)
    plan = dict(schema=1,board='2609',purpose='First SNBT journal from exact installed b15 F; offline only',
        hardware=False,serial_access=False,flashed=False,MON_installed=False,
        load_address='0200',end_exclusive=f'{sy["JI_END"]:04X}',bytes=len(image),
        image_sha256=r.sha(image),F_sha256=F_SHA,generation='8000000F',
        source_sha256=r.hashes(source),expected_sha256=r.hashes(expected),
        planned_erase_order=['B3:D000','B3:C000'],counts_before=history['counts'],counts_reserved=reserved,
        counts_semantics='Tracked lower bounds; prior lifetime unknown. Reservations become actual only after device verification.',
        history_unknown_mask='ffffffff',sequences=[history['sequence']+1,history['sequence']+2],
        config_before=history['config'],config_proposed=cfg.hex(),default='S',enabled_banks=0,console='Initializer USB FT245 only; F reset retains its existing BOTH-console behavior',
        B0_backup_sha256=WDC_SHA,host_wear_history_updated=False,
        bootstrap_reservation='Host plan reserves both erases before the first D erase; D commit carries both before C erase. No onboard reservation can predate the first journal.',
        partial_failure='Halt; retain host plan/log and assess changed preimages. Never replay this original plan blindly.',
        source_provenance='Previous F-only device-verified target images; fresh board preimages are required by the RAM program before I.',
        inputs={str(p):bind(p) for p in [report_path,history_path,Path(__file__),HERE/'ram-journal-init-2609.asm',TARGET/'symbols.json',TARGET/'payload/f-offline-component.bin']},
        files={p.relative_to(out).as_posix():bind(p) for p in [out/'payload/2609-journal-init-RAM.bin',out/'symbols.json',*out.glob('source-b*.bin'),*out.glob('expected-b*.bin'),*out.glob('snapshot-*.bin')]},
        limitations=['CPU/NOR tests pending; no board access', 'FNV detects accidental corruption/stale preimages; it is not authentication', 'Raw L has no framing; no automatic partial-failure retry', 'ACIA is not board-tested; this initializer uses USB only'])
    save(out/'plan.json', plan)
    verify(out)
    return plan


def verify(out):
    out = Path(out).resolve()
    plan = r.read(out/'plan.json')
    r.require(plan['board']=='2609' and plan['planned_erase_order']==['B3:D000','B3:C000'] and not plan['flashed'], 'Unsupported initializer plan')
    for name,info in plan['files'].items():
        path = (out/name).resolve()
        r.require(path.is_relative_to(out) and digest(path)==info['sha256'] and path.stat().st_size==info['bytes'], 'Changed initializer artifact: '+name)
    for name,info in plan['inputs'].items():
        r.require(digest(name)==info['sha256'], 'Changed initializer input: '+name)
    source = [(out/f'source-b{n}.bin').read_bytes() for n in range(4)]
    expected = [(out/f'expected-b{n}.bin').read_bytes() for n in range(4)]
    r.require(r.hashes(source)==plan['source_sha256'] and r.hashes(expected)==plan['expected_sha256'], 'Changed bank metadata')
    r.require(source[:3]==expected[:3] and source[3][:0x4000]==expected[3][:0x4000] and source[3][0x6000:]==expected[3][0x6000:] and r.sha(source[0])==WDC_SHA, 'Non-C/D byte changed')
    image = (out/'payload/2609-journal-init-RAM.bin').read_bytes()
    r.require(wire.fnv(image[:-4])==int.from_bytes(image[-4:],'little') and r.sha(image)==plan['image_sha256'], 'RAM checksum/image mismatch')
    history = dict(board='2609',counts=plan['counts_before'],config=plan['config_before'],sequence=plan['sequences'][0]-1,history_unknown_mask=plan['history_unknown_mask'])
    reserved,cfg,journal = rows(history)
    r.require(reserved==plan['counts_reserved'] and cfg.hex()==plan['config_proposed'], 'Changed reservation/configuration')
    for address,row in zip(ORDER,journal):
        r.require(expected[3][address-0x8000:address-0x7000]==row+b'\xff'*3840, 'Changed journal postimage')
    r.require(len(snbt_records(expected))==2 and not snbt_records(source), 'Unexpected journal records')
    return plan


if __name__ == '__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('command',choices=['prepare','verify'])
    p.add_argument('--out',type=Path,required=True)
    p.add_argument('--session',type=Path,default=SESSION)
    args=p.parse_args()
    result=prepare(args.out,args.session) if args.command=='prepare' else verify(args.out)
    print(json.dumps({k:result[k] for k in ('board','bytes','image_sha256','planned_erase_order','counts_reserved','flashed')},indent=2))
