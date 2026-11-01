"""Identity of the 1077-byte RTC phase image qualified on November 1, 2026."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_BUILD = ROOT / 'BUILD/rtc-phase'
BASE = 0x2000
SIZE = 1077
IMAGE_SHA256 = '28c6ad2421d2d6425dee27605dca5df3d3f58e4efcfb4766cf0f4fffc8550b92'


def verify_image(image, symbols):
    contract = json.loads((ROOT / 'tests/baselines/rtc-phase.json').read_text(encoding='utf-8'))
    if len(image) != SIZE or hashlib.sha256(image).hexdigest() != IMAGE_SHA256:
        raise ValueError('RTC phase image differs from the qualified image')
    if symbols != contract['symbols']:
        raise ValueError('RTC phase symbols differ from the qualified address map')


def load_image(build=DEFAULT_BUILD):
    build = Path(build)
    image = (build / 'phase.bin').read_bytes()
    symbols = json.loads((build / 'symbols.json').read_text(encoding='utf-8'))
    verify_image(image, symbols)
    proof = json.loads((build / 'proof.json').read_text(encoding='utf-8'))
    cases = {'observe', 'calibrate', 'pause', 'advance', 'advance-59', 'bad-key',
             'zero', 'over-limit', 'PF', 'alarm', 'trim', 'absent', 'stuck-scl',
             'stuck-sda', 'stopped'}
    expected = {(cpu, case) for cpu in ('65C02', '65C816 emulation') for case in cases}
    checks = proof.get('checks', [])
    if (proof.get('passed') is not True or proof.get('image_sha256') != IMAGE_SHA256
            or len(checks) != len(expected)
            or {(c.get('CPU'), c.get('case')) for c in checks} != expected
            or any(c.get('passed') is not True for c in checks)):
        raise ValueError('RTC phase image requires all 30 passing CPU/I2C model cases')
    return image, symbols, proof
