"""Shared checksums, sealed regions and established S-record serialization."""
import binascii
import hashlib
import json
import re


def sha(data):
    return hashlib.sha256(data).hexdigest()


def crc(data, seed=0xffff):
    return binascii.crc_hqx(data, seed)


def save(path, value):
    path.write_text(json.dumps(value, indent=2)+'\n', encoding='utf-8')


def sealed(data, size):
    if len(data) > size-2:
        raise ValueError(f'{len(data)} bytes exceed {size}-byte sealed region')
    data = data+b'\xff'*(size-2-len(data))
    result = data+crc(data).to_bytes(2, 'big')
    if crc(result):
        raise ValueError('Invalid sealed region')
    return result


def db(path, data, label=''):
    path.write_text(label+''.join(' DB '+','.join(f'${b:02X}' for b in data[i:i+16])+'\n'
                                 for i in range(0, len(data), 16)), encoding='ascii')


def record(kind, address, data=b''):
    raw = bytes([len(data)+3])+address.to_bytes(2, 'big')+data
    return 'S'+kind+(raw+bytes([255-(sum(raw)&255)])).hex().upper()


def s19(data, address, entry):
    # The historical S0 label and LF serialization are part of the baseline.
    lines = [record('0', 0, b'STR8-N 2.0b4 exact source migration')]
    lines += [record('1', address+i, data[i:i+32]) for i in range(0, len(data), 32)]
    return ('\n'.join(lines+[record('9', entry)])+'\n').encode('ascii')


def read_s19(path):
    cells = {}
    for line in path.read_text(encoding='ascii').splitlines():
        if not line:
            continue
        if not re.fullmatch(r'S[019][0-9A-Fa-f]+', line):
            raise ValueError(f'Unsupported S-record: {path}')
        raw = bytes.fromhex(line[2:])
        if len(raw) != raw[0]+1 or sum(raw)&255 != 255:
            raise ValueError(f'Invalid S-record count/checksum: {path}')
        if line[1] == '1':
            for address, value in enumerate(raw[3:-1], int.from_bytes(raw[1:3], 'big')):
                if address in cells:
                    raise ValueError(f'Overlapping S-record: {path}')
                cells[address] = value
    return cells
