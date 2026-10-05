"""Guarded service-revision -> autoload B/C/E/F RAM updaters; no serial I/O."""
import argparse
import json
from pathlib import Path
import build_v2_b2_board_update as update
import build_v2_b2 as firmware
from v2_b2_config import valid_boot_pocket, decode_locator, decode_header

OLD_B = '22dd20ef7b9f158a0aedf2e1db1cb6d8e98b16f97801fe4cb6896b9c24713ef8'
OLD_C = '4ea48ee72006265bed88301805d77a00f1c86bfcea9b8a1ed18d7a57fc11c35b'
OLD_F = 'e4fd452810074ba27bc772cb05a29546027ca4b647bc7b7211ee06427d6866ad'

# Extra whole-resident-bank CRC excludes the one sector being replaced. Exact
# target/guard comparisons remain the qualified updater's primary guards.
EXTRA = '''E_CRC                   EQU $E6
E_EXTRA_GUARD:          LDA #$FF
                        STA E_CRC
                        STA E_CRC+1
                        STZ E_SRC
                        LDA #$80
                        STA E_SRC+1
                        LDY #$00
E_CRC_BYTE:             LDA E_SRC+1
                        AND #$F0
                        CMP #CRC_SKIP
                        BNE E_CRC_READ
                        LDA E_SRC+1
                        CLC
                        ADC #$10
                        STA E_SRC+1
                        BNE E_CRC_BYTE
                        BRA E_CRC_END
E_CRC_READ:             LDA (E_SRC),Y
                        EOR E_CRC+1
                        STA E_CRC+1
                        LDX #$08
E_CRC_BIT:              ASL E_CRC
                        ROL E_CRC+1
                        BCC E_CRC_NEXT
                        LDA E_CRC
                        EOR #$21
                        STA E_CRC
                        LDA E_CRC+1
                        EOR #$10
                        STA E_CRC+1
E_CRC_NEXT:             DEX
                        BNE E_CRC_BIT
                        INC E_SRC
                        BNE E_CRC_BYTE
                        INC E_SRC+1
                        BNE E_CRC_BYTE
E_CRC_END:              LDA E_CRC
                        CMP #CRC_LOW
                        BNE E_CRC_BAD
                        LDA E_CRC+1
                        CMP #CRC_HIGH
                        BNE E_CRC_BAD
                        SEC
                        RTS
E_CRC_BAD:              CLC
                        RTS
'''


def prepare(before):
    if len(before) != 32768:
        raise ValueError('Full fresh B3 readback required')
    if update.sha(before[0x3000:0x4000]) != OLD_B or update.sha(before[0x4000:0x5000]) != OLD_C:
        raise ValueError('Unknown installed B/C revision')
    if update.sha(update.normalized(before[-4096:])) != OLD_F:
        raise ValueError('Unknown installed F outside mutable pocket')
    installed_e = (firmware.ROOT/'output/qualification/b2-2205-2026-10-04/'
        'service-install-1791125311788929100/e-updater/staged-sector.bin').read_bytes()
    if before[0x6000:0x7000] != installed_e:
        raise ValueError('Unknown installed SERVICE.REGISTER E')
    if not valid_boot_pocket(before[-4096:][update.POCKET]):
        raise ValueError('Invalid boot/config pocket')
    if before[0x7FD1] != 0:
        raise ValueError('This exact installer requires application autostart disabled')
    if decode_locator(before[0x7FD0:0x7FE0]) != (3,13):
        raise ValueError('This exact installer requires the existing B3:D configuration')
    decode_header(before[0x5000:0x5010],3,13)
    # No unknown module or opaque data in the newly adopted AL region.
    if before[0x5010:0x5050] != b'\xff'*64:
        raise ValueError('Existing config AL region is occupied')
    qualification = json.loads((firmware.OUT/'autoload-qualification.json').read_text())
    if qualification['host_check_groups'] != 37:
        raise ValueError('Complete autoload host qualification required')
    for relative,digest in qualification['images'].items():
        if update.sha((firmware.ROOT/relative).read_bytes()) != digest:
            raise ValueError(f'Changed qualified artifact {relative}')
    ef = (firmware.OUT/(firmware.STEM+'-e000-ffff.bin')).read_bytes()
    desired = dict(b=(firmware.OUT/(firmware.STEM+'-b000-bfff.bin')).read_bytes(),
        c=(firmware.ROOT/'BUILD/v2-b2-command-example/str8n-v2-b2-h-x-c000-cfff.bin').read_bytes(),
        e=ef[:4096], f=ef[4096:0x1FD0]+before[0x7FD0:0x7FE0]+ef[0x1FE0:])
    if any(len(data)!=4096 for data in desired.values()):
        raise ValueError('Complete sectors required')
    return desired


def build(before,folder,desired=None,phases=('b','c','e','f')):
    desired = prepare(before) if desired is None else desired
    folder = Path(folder)
    phase_bank = bytearray(before)
    summary=[]
    for phase in phases:
        base = int(phase,16)*4096-0x8000
        source = bytes(phase_bank)
        old = source[base:base+4096]
        guard_sector = 0xF0 if phase=='e' else 0xE0
        guard_base = guard_sector*256-0x8000
        guard = source[guard_base:guard_base+4096]
        crc = firmware.crc16(source[:base]+source[base+4096:])
        def plan(ef,which,backup=None,unused=None):
            if ef != source[-8192:] or which != phase:
                raise ValueError('Source phase changed')
            return old,desired[phase],guard,0x80+base//256
        original = update.SOURCE
        extra = EXTRA.replace('CRC_SKIP',f'${0x80+base//256:02X}').replace(
            'CRC_LOW',f'${crc&255:02X}').replace('CRC_HIGH',f'${crc>>8:02X}')
        update.SOURCE = original.replace('E_GUARD_RETURN:         PHP',
            '                        JSR E_EXTRA_GUARD\nE_GUARD_RETURN:         PHP').replace(
            'E_GUARD_IMAGE:          INCLUDE',extra+'E_GUARD_IMAGE:          INCLUDE')
        try:
            result = update.build(source,folder/(phase+'-updater'),phase,
                planner=plan,staging=0x6100,flash_backup_guard=False,scratch_base=0xE0)
        finally:
            update.SOURCE = original
        path=folder/(phase+'-updater/manifest.json')
        meta=json.loads(path.read_text())
        meta.update(source_full_b3_sha256=update.sha(source),whole_bank_crc16=crc,
            sector=phase.upper(),source_version='b2-services-3984',
            host_f_backup_sha256=update.sha(before[-4096:]),
            baseline_sha256=OLD_F,guard_sector=guard_sector,
            preserves_boot_pocket=True,board_installed=False)
        path.write_text(json.dumps(meta,indent=2)+'\n')
        phase_bank[base:base+4096]=desired[phase]
        summary.append(dict(phase=phase,artifact=str(result[0]),
            before_sha256=update.sha(source),after_sha256=update.sha(phase_bank)))
    (folder/'expected-installed-b3.bin').write_bytes(phase_bank)
    (folder/'autoload-update-plan.json').write_text(json.dumps(summary,indent=2)+'\n')
    return summary


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('evidence',type=Path)
    args=parser.parse_args()
    for row in build((args.evidence/'before-b3.bin').read_bytes(),args.evidence):
        print(row['artifact'])


if __name__=='__main__':main()
