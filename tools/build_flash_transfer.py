"""Build only FLASH/S19 and high-RAM flash records; reuse qualified support."""
import argparse
import binascii
import json
from pathlib import Path
import re
import shutil
import subprocess

from build_mona import ROOT, cells, sha
from mona_branches import conservative_branches


def parser_source():
    source = (ROOT/'monitors/native/s19-loader.asm').read_text()
    return source[source.index('SL_RECORD_READ:'):source.index('SL_PRINT:')]


def number_source():
    source = (ROOT/'monitors/native/store-front.asm').read_text()
    source = source[source.index('SF_WORD:'):source.index('SF_PRINT:')].replace('SF_', 'FR_')
    return source.replace('FR_WORD_END:\n', 'FR_WORD_END:\n        STX FR_PARSE_INDEX\n')


def build(out, prior, reuse_flash=None,reuse_record=None):
    out, prior = Path(out).resolve(), Path(prior).resolve()
    if out.exists():
        raise ValueError('Use a fresh build directory')
    freeze = json.loads((ROOT/'F_FREEZE.json').read_text())
    assert sha((ROOT/'firmware/payload/STR8N-F-BOOT-4096.bin').read_bytes()) == freeze['sha256']
    for name, digest in freeze['sources'].items():
        assert sha((ROOT/name).read_bytes()) == digest
    # Reuse only the qualified build's generated support includes. Neither
    # CLOCK, BANK MAINT, MON, loader nor F is rebuilt by this command.
    out.mkdir(parents=True)
    for path in prior.glob('*.inc'):
        shutil.copyfile(path, out/path.name)
    inputs = ['monitors/native/board-tool.asm', 'monitors/native/flash-s19.inc',
              'monitors/native/flash-record.asm', 'monitors/native/s19-loader.asm',
              'monitors/native/store-front.asm','monitors/native/flash-transfer-gate.asm']
    source_hashes = {name:sha((ROOT/name).read_bytes()) for name in inputs}
    for name in ('worker-public-symbols.inc', 'boot-symbols.inc'):
        shutil.copyfile(ROOT/'src/core'/name, out/name)
    shutil.copyfile(ROOT/'src/include/str8n-v2-eq.inc', out/'str8n-v2-eq.inc')
    shutil.copyfile(ROOT/'src/include/str8n-v2-public.inc', out/'str8n-v2-public.inc')
    (out/'flash-s19-parser.inc').write_text(parser_source())
    (out/'flash-record-number.inc').write_text(number_source())
    text, _ = conservative_branches((ROOT/'monitors/native/flash-s19.inc').read_text(), 'FI_LONG_')
    (out/'flash-s19.inc').write_text(text)
    logs = []

    def assemble(stem, origin, last):
        source = ROOT/f'monitors/native/{stem}.asm'
        text, _ = conservative_branches(source.read_text(), stem.replace('-', '_')+'_LONG_')
        (out/source.name).write_text(text)
        for cmd in ([shutil.which('wdc02as'), '-G','-L','-S','-W',source.name],
                    [shutil.which('wdcln'), '-g','-s','-t',f'-c{origin:04X}', '-hm19','-j','-o',stem+'.s19',stem+'.obj']):
            assert cmd[0]
            result = subprocess.run(cmd, cwd=out, capture_output=True, text=True)
            logs.append(dict(command=cmd, returncode=result.returncode, stdout=result.stdout, stderr=result.stderr))
            (out/'build-log.json').write_text(json.dumps(logs, indent=2)+'\n')
            if result.returncode:
                raise RuntimeError('Build failed; see build-log.json')
        symbols = {n:int(v,16) for v,n in re.findall(r'^\s*([0-9A-Fa-f]{8})\s+(\w+)\s*$', (out/(stem+'.map')).read_text(),re.M)}
        memory = cells(out/(stem+'.s19'))
        return bytes(memory[a] for a in range(origin, symbols[last])), symbols

    if reuse_flash:
        reuse = Path(reuse_flash).resolve()
        old = json.loads((reuse/'manifest.json').read_text())
        for name in ('monitors/native/board-tool.asm','monitors/native/flash-s19.inc','monitors/native/s19-loader.asm'):
            assert source_hashes[name] == old['source_sha256'][name]
        for path in out.glob('*.inc'):
            if path.name != 'flash-record-number.inc':
                assert path.read_bytes() == (reuse/path.name).read_bytes(), path.name
        board = (reuse/'FLASH-S19-RAM.bin').read_bytes()
        assert sha(board) == old['artifacts']['FLASH-S19-RAM.bin']['sha256']
    else:
        board, bs = assemble('board-tool', 0x2000, 'BOARD_END')
    if reuse_record:
        prior_record=Path(reuse_record).resolve()
        old_record=json.loads((prior_record/'manifest.json').read_text())
        for name in ('monitors/native/flash-record.asm','monitors/native/store-front.asm'):
            assert source_hashes[name]==old_record['source_sha256'][name]
        assert (out/'flash-record-number.inc').read_bytes()==(prior_record/'flash-record-number.inc').read_bytes()
        old_worker=(prior_record/'FLASH-RECORD-6B00.bin').read_bytes()
        assert sha(old_worker)==old_record['artifacts']['FLASH-RECORD-6B00.bin']['sha256']
        record=old_worker[:old_record['flash_record_linked_bytes']]
    else:
        record, rs = assemble('flash-record', 0x6B00, 'FR_END_CODE')
    gate, gs = assemble('flash-transfer-gate', 0x7300, 'GG_END')
    assert len(board) <= 8192-34, f'FLASH body {len(board)} exceeds its two-sector allocation'
    assert len(board)<=0x1A30, 'FLASH padding contains STATUS at FA50; use build_flash_status_correction.py'
    assert len(record) <= 2046, f'Flash records {len(record)} exceeds existing BANK MAINT A800 padding'
    h = bytearray(b'\xff'*32)
    h[:8] = b'RP\x01\x01PR05'
    h[8:10] = len(board).to_bytes(2, 'little')
    h[10:12] = h[12:14] = (0x2000).to_bytes(2,'little')
    h[14:18] = (2).to_bytes(4,'little')
    flash = (bytes(h)+board).ljust(8190,b'\xff')
    flash += binascii.crc_hqx(flash,65535).to_bytes(2,'big')
    worker = record.ljust(2046,b'\xff')
    worker += binascii.crc_hqx(worker,65535).to_bytes(2,'big')
    assert len(gate)<=1022
    gate_image=gate.ljust(1022,b'\xff')
    gate_image+=binascii.crc_hqx(gate_image,65535).to_bytes(2,'big')
    artifacts = {}
    for name,data in (('FLASH-S19-RAM.bin',board), ('FLASH-S19-flash.bin',flash), ('FLASH-RECORD-6B00.bin',worker),('FLASH-TRANSFER-GATE-7300.bin',gate_image)):
        (out/name).write_bytes(data)
        artifacts[name] = dict(bytes=len(data),sha256=sha(data))
    report = dict(status='BUILD_ONLY_NOT_EXECUTION_QUALIFIED', F_rebuilt=False, F_sha256=freeze['sha256'],
        source_sha256=source_hashes, support_build=str(prior), support_sha256={p.name:sha(p.read_bytes()) for p in prior.glob('*.inc')},
        artifacts=artifacts, FLASH_linked_bytes=len(board), FLASH_free_bytes=8158-len(board),
        flash_record_linked_bytes=len(record), flash_record_free_bytes=2046-len(record),
        gate_linked_bytes=len(gate),gate_free_bytes=1022-len(gate),
        native_I='R FLASH; BANK 0|1; I first last; complete sectors8000-DFFF; live YES',
        large_Store='STORE 0|1 AUTO|addr start end name; source0200-66FF; commit last; no erase',
        wide_Restore='RESTORE 0|1 name L; checked SR01 header; load-only through66FF',
        integration='RAM candidates only; high worker native dispatch/packing not installed',
        CPU_simulations=0, build_passes=1)
    (out/'manifest.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({k:report[k] for k in ('FLASH_linked_bytes','FLASH_free_bytes','flash_record_linked_bytes','flash_record_free_bytes')},indent=2))


if __name__ == '__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--out',required=True)
    p.add_argument('--support',required=True)
    p.add_argument('--reuse-flash',help='Reuse the unchanged FLASH assembly after an isolated record-worker correction')
    p.add_argument('--reuse-record',help='Reuse unchanged high record code for an isolated gate correction')
    a=p.parse_args()
    build(a.out,a.support,a.reuse_flash,a.reuse_record)
