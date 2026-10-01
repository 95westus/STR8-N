"""Build exact-image alpha26-to-alpha27 RAM E/F updaters for board 2205."""
import hashlib
import json
from pathlib import Path
import build_v2_a26 as old
import build_v2_a27 as new
from build_v2_a25_guarded_ef import make_updater

OUT = new.ROOT / 'BUILD/board/a27-2205'
EXPECTED_EF = '62656ba960292c11104d15457b1a0ddb5480011eacdffd7fa1b3079d981127ae'
EXPECTED_E = '0e8e8e2295b9d3b51b09ab3512377a366d758619ab1524fe9ace936604853492'
EXPECTED_F = '53f1ef4974c104007be03b4dbeedb1f6c3c6fe7a5c4038c30efb80c0f8a3ea69'


def sha(data):
    return hashlib.sha256(data).hexdigest()


def main():
    first = (OUT / 'ef-before-1.bin').read_bytes()
    second = (OUT / 'ef-before-2.bin').read_bytes()
    if len(first) != 8192 or first != second or sha(first) != EXPECTED_EF:
        raise ValueError('Independent board-2205 E/F preimages disagree with recorded a26')
    old_e, old_f = first[:4096], first[4096:]
    if sha(old_e) != EXPECTED_E or sha(old_f) != EXPECTED_F:
        raise ValueError('Installed a26 sector identity changed')
    previous = (old.OUT / f'{old.STEM}-e000-ffff.bin').read_bytes()
    if first != previous:
        raise ValueError('Live a26 image differs from canonical build')
    target = (new.OUT / f'{new.STEM}-e000-ffff.bin').read_bytes()
    if len(target) != 8192:
        raise ValueError('Build a27 before preparing updater')
    new_e, new_f = target[:4096], target[4096:]
    if (new_e[:4] != b'RT\x02\x00' or
            new_e[0x800:0x805] != b'SR\x01\x01\x18' or
            old_f[-32:] != new_f[-32:]):
        raise ValueError('A27 ABI, S/R entries, or F vector tail changed')
    worker = json.loads((old.OUT / 'build.json').read_text())['worker']
    other = json.loads((new.OUT / 'build.json').read_text())['worker']
    for symbol in ('V2W_SNAPSHOT', 'V2W_MUTATE'):
        if worker[symbol] != other[symbol]:
            raise ValueError(f'Flash worker address changed: {symbol}')
    e_path, e_symbols = make_updater('str8n-v2-alpha27-board2205-e-install-2000',
        new.SOURCE / 'str8n-v2-e-repair-2000.asm', old_e, new_e, None,
        worker, OUT)
    f_path, f_symbols = make_updater('str8n-v2-alpha27-board2205-f-install-2000',
        new.SOURCE / 'str8n-v2-f-update-2000.asm', old_f, new_f, new_e,
        worker, OUT)
    for name,data in (('old-e.bin',old_e),('old-f.bin',old_f),
                      ('new-e.bin',new_e),('new-f.bin',new_f)):
        (OUT / name).write_bytes(data)
    report = dict(board='W65C02SXB COM3 FT245 A10MPUPNA with EDU, board 2205',
                  source_ef_sha256=sha(first),
                  old_e_sha256=sha(old_e), old_f_sha256=sha(old_f),
                  new_e_sha256=sha(new_e), new_f_sha256=sha(new_f),
                  e_updater=str(e_path), e_updater_sha256=sha(e_path.read_bytes()),
                  e_updater_end=e_symbols['E_END'],
                  f_updater=str(f_path), f_updater_sha256=sha(f_path.read_bytes()),
                  f_updater_end=f_symbols['E_END'],
                  board_installed_by_builder=False)
    (OUT / 'manifest.json').write_text(json.dumps(report, indent=2)+'\n')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
