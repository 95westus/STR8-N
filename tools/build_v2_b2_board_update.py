"""Build exact-board beta1-to-b2 RAM E/F updaters; never access a board.

E is installed first using the original beta1 RAM worker and $6900 staging.
F is installed last, with an additional exact B2:F backup guard. All loaded
bytes fit below the beta2 $5800 application ceiling. The original published
beta1 core is required outside its mutable $FFD0 pocket.
"""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import zipfile

import build_v2_config as assembler
import build_v2_b2 as firmware
from v2_b2_config import valid_boot_pocket

ROOT = assembler.ROOT
BASELINE_ZIP = ROOT / 'output/release/str8n-v2-b1.zip'
BASELINE_NAME = 'str8n-v2-a24c1-f000-ffff.bin'
BASELINE_SHA = '231fbec1b0e6a1e80f4a956009aa74f6259e4f0dfcf761f09f16755832aece36'
POCKET = slice(0xFD0, 0xFE0)
# These front entries are identical in the frozen published worker. No private
# ROM service is called during mutation or recovery.
WORKER = dict(V2W_SELECT=0x7948, V2W_SNAPSHOT=0x797A, V2W_MUTATE=0x79A3)


def sha(data):
    return hashlib.sha256(data).hexdigest()


def normalized(data):
    return data[:0xFD0] + b'\xff' * 16 + data[0xFE0:]


def baseline(path=BASELINE_ZIP):
    path = Path(path)
    if path.suffix.lower() == '.zip':
        with zipfile.ZipFile(path) as archive:
            data = archive.read(BASELINE_NAME)
    else:
        data = path.read_bytes()
    if len(data) != 4096 or sha(normalized(data)) != BASELINE_SHA:
        raise ValueError('Baseline is not the frozen published beta1 core')
    return data


def source_ef(data):
    if len(data) == 32768:
        return data[-8192:]
    if len(data) != 8192:
        raise ValueError('Source must be a full B3 bank or exactly its E/F sectors')
    return data


def backup_f(data):
    if len(data) == 32768:
        return data[-4096:]
    if len(data) != 4096:
        raise ValueError('Backup must be a full B2 bank or exactly B2:F')
    return data


def plan(source, phase, backup=None, baseline_path=BASELINE_ZIP):
    metadata = json.loads((firmware.OUT / 'build.json').read_text())
    if metadata.get('manager_storage'):
        raise ValueError('This candidate requires B/E installation; E/F-only updater is unsupported')
    source = source_ef(source)
    e, f = source[:4096], source[4096:]
    frozen = baseline(baseline_path)
    if normalized(f) != normalized(frozen):
        raise ValueError('Source F differs from published beta1 outside its boot pocket')
    candidate_e = (firmware.OUT / f'{firmware.STEM}-e000-efff.bin').read_bytes()
    candidate_f = (firmware.OUT / f'{firmware.STEM}-f000-ffff.bin').read_bytes()
    if len(candidate_e) != 4096 or len(candidate_f) != 4096:
        raise ValueError('Candidate sector length changed')
    binding = firmware.crc16(candidate_f[:0xFD0] + candidate_f[0xFE0:])
    if candidate_e[:3] != b'EM\x01' or int.from_bytes(candidate_e[4:6], 'little') != binding:
        raise ValueError('Candidate E/F manager binding mismatch')
    if phase == 'e':
        return e, candidate_e, f, 0xE0
    if phase != 'f':
        raise ValueError('Phase must be e or f')
    if e != candidate_e:
        raise ValueError('F installation requires the complete matching b2 E image first')
    if backup is None or backup_f(backup) != f:
        raise ValueError('B2:F backup must exactly equal the source configured F sector')
    settings = f[POCKET]
    if not valid_boot_pocket(settings) and settings not in (bytes(16), b'\xff' * 16):
        raise ValueError('Source boot settings are invalid under the b2 RAM bounds')
    # Preserve valid local settings exactly; no extended sector is assigned.
    saved = settings if valid_boot_pocket(settings) else b'\xff' * 16
    return f, candidate_f[:0xFD0] + saved + candidate_f[0xFE0:], e, 0xF0


SOURCE = '''; Exact board updater. All erase/program/readback/recovery runs in RAM.
                        MODULE B2_BOARD_UPDATE
                        XDEF START,E_END,E_NEW,E_OLD,E_GUARD_IMAGE
                        INCLUDE "str8n-v2-eq.inc"
                        INCLUDE "e-worker-addresses.inc"
E_SRC                   EQU $C0
E_DST                   EQU $C2
E_MSG                   EQU $C4
                        CODE
START:                  SEI
                        CLD
                        LDX #$FF
                        TXS
                        LDA V2_RESIDENT
                        CMP #$03
                        BEQ E_BANK_OK
                        JMP E_WRONG_BANK
E_BANK_OK:              JSR E_GUARD
                        BCS E_GUARD_OK
                        JMP E_MISMATCH
E_GUARD_OK:             LDA #$03
                        STA V2_SELECTED
                        LDA #SECTOR
                        STA V2_SECTOR
                        JSR V2W_SNAPSHOT
                        JSR E_COMPARE_OLD
                        BCS E_OLD_OK
                        JMP E_MISMATCH
E_OLD_OK:               LDX #<E_PROMPT
                        LDY #>E_PROMPT
                        JSR E_PRINT
                        JSR $7E70
                        CMP #'Y'
                        BEQ E_CONFIRMED
                        JMP E_ABORT
E_CONFIRMED:            JSR E_GUARD
                        BCS E_CONFIRMED_GUARD
                        JMP E_MISMATCH
E_CONFIRMED_GUARD:      JSR V2W_SNAPSHOT
                        JSR E_COMPARE_OLD
                        BCS E_WRITE_NEW
                        JMP E_MISMATCH
E_WRITE_NEW:            JSR E_STAGE_NEW
                        JSR E_MUTATE
                        BCS E_ROLLBACK
                        JSR V2W_SNAPSHOT
                        JSR E_COMPARE_NEW
                        BCC E_ROLLBACK
                        LDX #<E_SUCCESS
                        LDY #>E_SUCCESS
                        JSR E_PRINT
                        JMP $F004
E_ROLLBACK:             JSR E_STAGE_OLD
                        JSR E_MUTATE
                        BCS E_REPAIR_FAIL
                        JSR V2W_SNAPSHOT
                        JSR E_COMPARE_OLD
                        BCC E_REPAIR_FAIL
                        LDX #<E_RESTORED
                        LDY #>E_RESTORED
                        JSR E_PRINT
                        JMP $F004
E_REPAIR_FAIL:          LDX #<E_FAILED
                        LDY #>E_FAILED
                        JSR E_PRINT
E_FAILED_WAIT:          JSR $7E70
                        CMP #'Y'
                        BNE E_FAILED_WAIT
                        JMP E_ROLLBACK
E_MISMATCH:             LDX #<E_OLD_BAD
                        LDY #>E_OLD_BAD
                        JSR E_PRINT
                        JMP $F007
E_WRONG_BANK:           LDX #<E_BANK_BAD
                        LDY #>E_BANK_BAD
                        JSR E_PRINT
                        JMP $F007
E_ABORT:                LDX #<E_ABORTED
                        LDY #>E_ABORTED
                        JSR E_PRINT
                        JMP $F007
E_MUTATE:               LDA #$01
                        STA V2_ERASE
                        STZ V2_SELF
                        JSR V2W_MUTATE
                        RTS
E_STAGE_NEW:            LDA #<E_NEW
                        STA E_SRC
                        LDA #>E_NEW
                        STA E_SRC+1
                        JMP E_COPY_IMAGE
E_STAGE_OLD:            LDA #<E_OLD
                        STA E_SRC
                        LDA #>E_OLD
                        STA E_SRC+1
                        JMP E_COPY_IMAGE
E_COMPARE_NEW:          LDA #<E_NEW
                        STA E_SRC
                        LDA #>E_NEW
                        STA E_SRC+1
                        JMP E_COMPARE_IMAGE
E_COMPARE_OLD:          LDA #<E_OLD
                        STA E_SRC
                        LDA #>E_OLD
                        STA E_SRC+1
                        JMP E_COMPARE_IMAGE
E_COPY_IMAGE:           STZ E_DST
                        LDA #$69
                        STA E_DST+1
                        LDX #$10
                        LDY #$00
E_COPY_BYTE:            LDA (E_SRC),Y
                        STA (E_DST),Y
                        INY
                        BNE E_COPY_BYTE
                        INC E_SRC+1
                        INC E_DST+1
                        DEX
                        BNE E_COPY_BYTE
                        RTS
E_COMPARE_IMAGE:        STZ E_DST
                        LDA #$69
                        STA E_DST+1
                        LDX #$10
                        LDY #$00
E_COMPARE_BYTE:         LDA (E_SRC),Y
                        CMP (E_DST),Y
                        BNE E_NOT_EQUAL
                        INY
                        BNE E_COMPARE_BYTE
                        INC E_SRC+1
                        INC E_DST+1
                        DEX
                        BNE E_COMPARE_BYTE
                        SEC
                        RTS
E_NOT_EQUAL:            CLC
                        RTS
E_GUARD:                LDA #$03
                        STA V2_SELECTED
                        LDA #GUARD_SECTOR
                        STA V2_SECTOR
                        JSR V2W_SNAPSHOT
                        LDA #<E_GUARD_IMAGE
                        STA E_SRC
                        LDA #>E_GUARD_IMAGE
                        STA E_SRC+1
                        JSR E_COMPARE_IMAGE
                        BCC E_GUARD_RETURN
BACKUP_GUARD
E_GUARD_RETURN:         PHP
                        LDA #$03
                        STA V2_SELECTED
                        JSR V2W_SELECT
                        LDA #SECTOR
                        STA V2_SECTOR
                        PLP
                        RTS
E_PRINT:                STX E_MSG
                        STY E_MSG+1
                        LDY #$00
E_PRINT_BYTE:           LDA (E_MSG),Y
                        BEQ E_PRINT_DONE
                        JSR $7E6D
                        INY
                        BNE E_PRINT_BYTE
E_PRINT_DONE:           RTS
E_PROMPT:               DB $0D,$0A,"B3:PHASE exact; TYPE Y to install b2> ",0
E_SUCCESS:              DB $0D,$0A,"B3:PHASE b2 VERIFIED; RESET",$0D,$0A,0
E_RESTORED:             DB $0D,$0A,"B3:PHASE OLD RESTORED; RESET",$0D,$0A,0
E_FAILED:               DB $0D,$0A,"WRITE/ROLLBACK FAILED; Y retries old image> ",0
E_OLD_BAD:              DB $0D,$0A,"OLD/GUARD IMAGE MISMATCH",$0D,$0A,0
E_BANK_BAD:             DB $0D,$0A,"B3 RESIDENCY REQUIRED",$0D,$0A,0
E_ABORTED:              DB $0D,$0A,"ABORTED",$0D,$0A,0
E_GUARD_IMAGE:          INCLUDE "guard-image.inc"
E_NEW:                 INCLUDE "new-image.inc"
E_OLD:                 INCLUDE "old-image.inc"
E_END:
                        ENDMOD
                        END
'''

BACKUP_GUARD = '''                        LDA #$02
                        STA V2_SELECTED
                        LDA #$F0
                        STA V2_SECTOR
                        JSR V2W_SNAPSHOT
                        JSR E_COMPARE_OLD
'''


def build(source, out, phase, backup=None, baseline_path=BASELINE_ZIP,
          *, planner=None, staging=0x6900, flash_backup_guard=True,
          scratch_base=0xC0, secondary_guard=None):
    source = source_ef(source)
    old, new, guard, sector = (planner or plan)(source, phase, backup, baseline_path)
    if staging not in (0x6100, 0x6900):
        raise ValueError('Unsupported staging address')
    if scratch_base not in (0xC0, 0xE0):
        raise ValueError('Unsupported updater scratch range')
    if old == new:
        raise ValueError('Selected sector already matches the requested candidate')
    out = Path(out)
    name = f'str8n-v2-b2-{phase}-update-2000'
    out.mkdir(parents=True, exist_ok=True)
    target = out / f'{name}.s19'
    if target.exists():
        raise FileExistsError(target)
    stage = out / 'asm'
    stage.mkdir(exist_ok=True)
    for filename, data in [('old-image.inc', old), ('new-image.inc', new), ('guard-image.inc', guard)]:
        assembler.include_bytes(stage / filename, data)
    (stage / 'e-worker-addresses.inc').write_text(''.join(
        f'{key:24} EQU ${value:04X}\n' for key, value in WORKER.items()), encoding='ascii')
    text = SOURCE.replace('BACKUP_GUARD', BACKUP_GUARD
                          if phase == 'f' and flash_backup_guard else '')
    if secondary_guard is not None:
        if len(secondary_guard) != 4096 or staging != 0x6100:
            raise ValueError('Secondary B guard requires a complete sector and b2 staging')
        prefix = secondary_guard.rstrip(b'\x00')
        if not 1 <= len(prefix) <= 2048:
            raise ValueError('Secondary B guard must have a bounded zero-filled tail')
        assembler.include_bytes(stage / 'secondary-image.inc', prefix)
        text = text.replace('E_GUARD_RETURN:         PHP',
                            '                        JSR E_SECOND_GUARD\nE_GUARD_RETURN:         PHP')
        extra = '''E_SECOND_GUARD:         LDA #$03
                        STA V2_SELECTED
                        LDA #$B0
                        STA V2_SECTOR
                        JSR V2W_SNAPSHOT
                        LDA #<E_SECOND_IMAGE
                        STA E_SRC
                        LDA #>E_SECOND_IMAGE
                        STA E_SRC+1
                        STZ E_DST
                        LDA #$61
                        STA E_DST+1
                        LDY #$00
E_SECOND_BYTE:          LDA (E_SRC),Y
                        CMP (E_DST),Y
                        BNE E_SECOND_BAD
                        INC E_SRC
                        BNE E_SECOND_DEST
                        INC E_SRC+1
E_SECOND_DEST:          INC E_DST
                        BNE E_SECOND_END
                        INC E_DST+1
E_SECOND_END:           LDA E_DST
                        CMP #<SECOND_PREFIX_END
                        BNE E_SECOND_BYTE
                        LDA E_DST+1
                        CMP #>SECOND_PREFIX_END
                        BNE E_SECOND_BYTE
E_SECOND_ZERO:          LDA (E_DST),Y
                        BNE E_SECOND_BAD
                        INC E_DST
                        BNE E_SECOND_ZERO
                        INC E_DST+1
                        LDA E_DST+1
                        CMP #$71
                        BNE E_SECOND_ZERO
                        SEC
                        RTS
E_SECOND_BAD:           CLC
                        RTS
E_SECOND_IMAGE:         INCLUDE "secondary-image.inc"
'''.replace('SECOND_PREFIX_END', f'${0x6100+len(prefix):04X}')
        text = text.replace('E_GUARD_IMAGE:          INCLUDE', extra+'E_GUARD_IMAGE:          INCLUDE')
    text = text.replace('LDA #$69', f'LDA #${staging >> 8:02X}')
    for offset in (0, 2, 4):
        text = text.replace(f'EQU $C{offset:X}', f'EQU ${scratch_base+offset:02X}')
    text = text.replace('GUARD_SECTOR', f'${0xF0 if phase == "e" else 0xE0:02X}')
    text = text.replace('#SECTOR', f'#${sector:02X}').replace('PHASE', phase.upper())
    asm = out / f'{name}.asm'
    asm.write_text(text, encoding='ascii')
    previous = assembler.OUT
    try:
        assembler.OUT = out
        memory, sym = assembler.assemble(name, 0x2000, shutil.which('wdc02as'),
                                        shutil.which('wdcln'), source_file=asm,
                                        include_dirs=(stage,))
    finally:
        assembler.OUT = previous
    end = sym['E_END']
    if sym['START'] != 0x2000 or end > 0x5800 or set(memory) != set(range(0x2000, end)):
        raise ValueError('Updater is not dense or exceeds the b2 application ceiling')
    lines = [assembler.record('0', 0, f'STR8-N b2 B3:{phase.upper()} exact update'.encode())]
    lines += [assembler.record('1', a, bytes(memory[v] for v in range(a, min(a+32, end))))
              for a in range(0x2000, end, 32)]
    lines.append(assembler.record('9', 0x2000))
    target.write_text('\n'.join(lines) + '\n', encoding='ascii')
    if assembler.read_s19(target) != (memory, 0x2000):
        raise ValueError('Updater S19 roundtrip mismatch')
    (out / 'staged-sector.bin').write_bytes(new)
    (out / 'old-sector.bin').write_bytes(old)
    (out / 'guard-sector.bin').write_bytes(guard)
    manifest = dict(version='2.0b2', phase=phase, entry=0x2000, end=end,
                    staging=staging, source_ef_sha256=sha(source), old_sha256=sha(old),
                    staged_sha256=sha(new), guard_sha256=sha(guard),
                    s19_sha256=sha(target.read_bytes()), baseline_sha256=BASELINE_SHA,
                    backup_sha256=sha(old) if phase == 'f' else None,
                    flash_backup_guard=flash_backup_guard,
                    scratch_base=scratch_base,
                    secondary_b_guard_sha256=sha(secondary_guard) if secondary_guard else None,
                    board_installed=False, symbols=sym)
    (out / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
    return target, new, sym


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('readback', type=Path)
    parser.add_argument('--backup', type=Path)
    parser.add_argument('--out', required=True, type=Path)
    parser.add_argument('--phase', choices=('e', 'f', 'both'), default='both')
    parser.add_argument('--baseline', type=Path, default=BASELINE_ZIP)
    args = parser.parse_args()
    source = source_ef(args.readback.read_bytes())
    backup = args.backup.read_bytes() if args.backup else None
    if args.phase == 'both':
        # Validate the backup before producing any installable artifact.
        candidate_e = (firmware.OUT / f'{firmware.STEM}-e000-efff.bin').read_bytes()
        plan(candidate_e + source[4096:], 'f', backup, args.baseline)
        target, new_e, _ = build(source, args.out / 'e-update', 'e', baseline_path=args.baseline)
        print(target)
        target, _, _ = build(new_e + source[4096:], args.out / 'f-update', 'f', backup, args.baseline)
        print(target)
    else:
        print(build(source, args.out, args.phase, backup, args.baseline)[0])


if __name__ == '__main__':
    main()
