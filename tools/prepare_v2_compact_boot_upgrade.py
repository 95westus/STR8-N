"""Prepare an exact-backup beta22 -> frozen beta23 installer; no board access."""
import argparse
import hashlib
import json
from pathlib import Path
import beta4_migration as m

ROOT = Path(__file__).resolve().parents[1]
sha = lambda b: hashlib.sha256(b).hexdigest()
read = lambda p: json.loads(p.read_text())


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--root', required=True, type=Path)
    p.add_argument('--board', required=True, choices=('2512', '2205', '2609'))
    p.add_argument('--build', type=Path, default=ROOT/'BUILD/v2-compact-boot')
    a = p.parse_args(); build = a.build
    prior = read(a.root/'prior/manifest.json')
    assert prior['repeat_verified'] and prior['board'] == a.board
    banks = [(a.root/f'prior/b{i}.bin').read_bytes() for i in range(4)]
    for i, b in enumerate(banks):
        assert len(b) == 32768 and b == (a.root/f'prior/b{i}-repeat.bin').read_bytes()
        assert sha(b) == prior['banks'][i]['sha256']
    old = ROOT/'BUILD/v2-spi-startup'
    meta = read(build/'build.json'); audit = read(build/'compact-boot-candidate-check.json')
    assert meta['version'] == '2.0b23' and meta['generation'] == 32
    assert audit['passed'] and audit['build_sha256'] == sha((build/'build.json').read_bytes())
    assert audit['artifacts'] == meta['artifacts']
    for name, digest in meta['artifacts'].items():
        assert sha((build/name).read_bytes()) == digest, name
    for name, digest in audit['model_report_hashes'].items():
        assert sha((build/name).read_bytes()) == digest and read(build/name)['passed'], name
    regions = [(3, 0, 'str8n-rtc-component-8000-8fff.bin', 4096),
               (3, 0x1000, 'str8n-journal-9000-9fff.bin', 3072),
               (3, 0x2000, 'str8n-v2-recovery-slot-a0.bin', 4096),
               (3, 0x3000, 'str8n-v2-recovery-slot-b0.bin', 4096),
               (3, 0x6000, 'str8n-v2-recovery-e000-efff.bin', 4096),
               (3, 0x7000, 'str8n-v2-recovery-f000-ffff.bin', 4096),
               (2, 0x4800, 'boot-status/asset.bin', 2560),
               (2, 0x6000, 'local-display/asset.bin', 1536)]
    final = [bytearray(b) for b in banks]
    for b, offset, name, length in regions:
        assert banks[b][offset:offset+length] == (old/name).read_bytes()[:length], name
        final[b][offset:offset+length] = (build/name).read_bytes()[:length]
    for page, offset in ((0xA0, 0x2000), (0xB0, 0x3000)):
        slot = banks[3][offset:offset+4096]
        assert m.slot_valid(slot, page) and int.from_bytes(slot[8:12], 'little') == 31
    assert (build/'clock/clock.bin').read_bytes() == (old/'clock/clock.bin').read_bytes()
    clock = (build/'clock/clock.bin').read_bytes()
    record = b'SR\x01\x3f\0\x20'+len(clock).to_bytes(2, 'little')+b'CLOCK'.ljust(16, b'\0')+clock
    assert banks[1][0x3000:0x3000+len(record)] == record, 'Current CLOCK changed'
    # Metadata, relinked provider/journal, sealed helpers, then B/A monitors.
    order = [(3, 12), (3, 8), (3, 9), (2, 13), (2, 12), (2, 14), (3, 11), (3, 10)]
    journal = m.journal(banks[3]); assert journal
    cfg = bytearray(journal[8:24]); assert cfg[14:] == m.config_sum(cfg)
    saved_edu = cfg[13]
    if cfg[7] == ord('P'): cfg[9:13] = meta['generation'].to_bytes(4, 'little')
    cfg[14:] = m.config_sum(cfg)
    counts = [int.from_bytes(journal[24+3*i:27+3*i], 'little') for i in range(32)]
    before = counts[:]
    for b, s in order:
        idx = b*8+s-8; assert counts[idx] < 0xFFFFFF; counts[idx] += 1
    seq = int.from_bytes(journal[4:8], 'little'); assert seq < 0xFFFFFFFF
    final[3][0x4000:0x5000] = m.metadata(cfg, counts, seq+1)+b'\xff'*(4096-128)
    assert cfg[13] == saved_edu and final[0] == banks[0] and final[1] == banks[1]
    assert final[3][0x1C00:0x2000] == banks[3][0x1C00:0x2000], 'Identity/offset tail changed'
    assert final[3][0x5000:] == banks[3][0x5000:], 'Recovery/other records changed'
    assert final[2][:0x4800] == banks[2][:0x4800]
    assert final[2][0x5200:0x6000] == banks[2][0x5200:0x6000] and final[2][0x6600:] == banks[2][0x6600:]
    mf = read(build/'migrator/manifest.json')
    cells, entry = m.read_s19(build/'migrator/rtc-migrator-2000.s19')
    cells[mf['count']] = len(order); cells[mf['commit_after']] = 0
    expected = [bytearray(b) for b in banks]; payload = []
    for i, (b, s) in enumerate(order):
        offset = (s-8)*4096; data = bytes(final[b][offset:offset+4096])
        row = bytes((s<<4,))+m.fnv(expected[b]).to_bytes(4, 'little')+m.fnv(data).to_bytes(4, 'little')
        for pos, v in enumerate(row, mf['table']+9*i): cells[pos] = v
        cells[mf['banks']+i] = b; cells[mf['commits']+i] = 0
        for pos in range(mf['commit_addresses']+4*i, mf['commit_addresses']+4*i+4): cells[pos] = 0
        expected[b][offset:offset+4096] = data; payload.append(data)
    assert expected == final, 'Unmodeled final sector changes'
    out = a.root/'upgrade'; out.mkdir(exist_ok=False)
    installer = m.s19(cells, entry); (out/'installer.s19').write_bytes(installer)
    plan = dict(board=a.board, source_generation=31, version=meta['version'], generation=32,
                steps=[dict(bank=b, sector=s) for b, s in order], prior_hashes=[sha(b) for b in banks],
                expected_hashes=[sha(b) for b in final], installer_sha256=sha(installer),
                build_sha256=audit['build_sha256'], candidate_audit_sha256=sha((build/'compact-boot-candidate-check.json').read_bytes()),
                config=cfg.hex(), saved_edu=saved_edu, counts_before=before, counts_after=counts,
                storage_update=True, commit_records=[], clock_update=False, journal_update=False,
                provider_relink=True, journal_relink=True, compact_boot_update=True, local_time_update=True,
                no_sram_format=True, preserved='B0/B1, saved records, journal identity/offset tail, saved EDU, fixed recovery; no device writes')
    (out/'plan.json').write_text(json.dumps(plan, indent=2)+'\n')
    for i, data in enumerate(payload): (out/f'transfer-{i:02d}.bin').write_bytes(data)
    for b, data in enumerate(final): (out/f'expected-b{b}.bin').write_bytes(data)
    print('PREPARED', a.board, len(order), 'sectors; beta22 -> beta23; saved EDU', hex(saved_edu))


if __name__ == '__main__': main()
