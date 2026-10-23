"""Complete repeated flash/RAM escrow and exact recovery-image validation."""
from pathlib import Path

from .common import check_board, inventory, safe, save
from .engine import legacy_transport as wire, runtime as r


def validate(root, board=None):
    root = Path(root).resolve(); identity = r.read(root/'capture.json')
    r.require(identity['schema']==1 and identity['repeat_verified'] is True, 'Complete repeated capture required')
    check_board(identity,board)
    for name, info in identity['files'].items():
        body = safe(root,name).read_bytes()
        r.require(len(body)==info['bytes'] and r.sha(body)==info['sha256'], 'Changed capture member: '+name)
    banks = []
    for n in range(4):
        names = [f'b{n}.bin',f'b{n}-repeat.bin']
        r.require(all(name in identity['files'] for name in names), 'Missing repeated bank')
        first, second = [(root/name).read_bytes() for name in names]
        r.require(len(first)==32768 and first==second, 'Different repeated bank')
        banks.append(first)
    names = ['application-ram.bin','application-ram-repeat.bin','restore-application-ram.s19']
    r.require(all(name in identity['files'] for name in names), 'Missing repeated RAM or restore image')
    ram = (root/names[0]).read_bytes()
    r.require(len(ram) in (0x6300,0x6500) and ram==(root/names[1]).read_bytes(), 'Different repeated RAM')
    r.require((root/names[2]).read_bytes()==wire.s19(dict(enumerate(ram,0x200)),0x200), 'RAM restore image differs')
    r.clean_journal(banks)
    return identity,banks


def write(root, profile, banks, ram, *, synthetic=False):
    root = Path(root); r.require(not root.exists(), 'Fresh capture directory required')
    root.mkdir(parents=True); (root/'.gitignore').write_text('*\n')
    r.valid_banks(banks)
    for n, body in enumerate(banks):
        for suffix in ('','-repeat'):(root/f'b{n}{suffix}.bin').write_bytes(body)
    for name in ('application-ram.bin','application-ram-repeat.bin'):(root/name).write_bytes(ram)
    (root/'restore-application-ram.s19').write_bytes(wire.s19(dict(enumerate(ram,0x200)),0x200))
    identity = dict(schema=1,board=profile['board'],usb_serial=profile['usb_serial'],repeat_verified=True,
                    synthetic_model_fixture=synthetic,hardware_capture=not synthetic,files=inventory(root))
    save(root/'capture.json',identity); validate(root)
    return identity
