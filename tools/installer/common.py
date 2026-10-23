"""File validation and board/candidate profiles shared by installer operations."""
import json
import os
from pathlib import Path

from .engine import runtime as r

HERE = Path(__file__).resolve().parent
REGISTRY = json.loads((HERE/'profiles.json').read_text(encoding='utf-8'))


def safe(root, name):
    root = Path(root).resolve(); path = (root/name).resolve()
    r.require(not Path(name).is_absolute() and path.is_relative_to(root), 'Escaping file path')
    return path


def save(path, value):
    path = Path(path); temporary = path.with_suffix('.tmp')
    with temporary.open('w',encoding='utf-8') as stream:
        json.dump(value,stream,indent=2); stream.write('\n'); stream.flush(); os.fsync(stream.fileno())
    temporary.replace(path)


def board_profile(board):
    r.require(board in REGISTRY['boards'], 'Unknown board profile')
    return REGISTRY['boards'][board]


def check_board(identity, board=None):
    profile = board_profile(board or identity['board'])
    r.require((identity['board'],identity['usb_serial'])==(profile['board'],profile['usb_serial']), 'Board/USB identity differs')
    return profile


def inventory(root):
    return {p.relative_to(root).as_posix():dict(bytes=p.stat().st_size,sha256=r.sha(p.read_bytes()))
            for p in sorted(root.rglob('*')) if p.is_file() and '__pycache__' not in p.parts
            and p.name not in ('installer-manifest.json','.gitignore')}
