"""Inspect zero-erase append capacity of the native CONFIG/OPAQUE journal writer.

This is a read-only allocation check, not a CPU model. Native JE_SPACE reserves
page F as the peer-erase intent; counting it as an ordinary slot is incorrect.
"""
import argparse
import json
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'migration-host'))
from nf_migrate import classify_journal,valid_snapshot

def inspect(bank3):
    status=classify_journal(bank3)
    if status['kind']!='valid-snbt':raise ValueError('Valid, unambiguous complete B3 required')
    newest=[off for off in range(0x4000,0x6000,256)
            if valid_snapshot(bank3[off:off+256]) and int.from_bytes(bank3[off+8:off+12],'little')==status['sequence']]
    if len(newest)!=1:raise ValueError('Multiple newest copies: inspect the live boot-selected page first')
    off=newest[0]
    if (off&0xf00)==0xf00:
        raise ValueError('Newest page is an erase intent: inspect recovery state before planning writes')
    sector=off&0xf000;peer=sector^0x1000
    slots=[i+0x8000 for i in range(off+256,sector+0xf00,256) if bank3[i:i+256]==b'\xff'*256]
    peer_blank=bank3[peer:peer+4096]==b'\xff'*4096
    return dict(latest_page=f'{off+0x8000:04X}',sequence=status['sequence'],
        ordinary_blank_pages=[f'{i:04X}' for i in slots],reserved_intent_page=f'{sector+0x8f00:04X}',
        peer_sector=f'{peer+0x8000:04X}',peer_blank=peer_blank,
        zero_erase_native_operations=len(slots)+(15 if peer_blank else 0),
        next_overflow=('move to blank peer, no erase' if peer_blank else 'commit intent, erase occupied peer, commit root'),
        hardware_access=False)

def require_zero_erase_room(bank3,operations):
    if type(operations) is not int or operations<0:
        raise ValueError('Nonnegative native operation count required')
    room=inspect(bank3)
    if operations>room['zero_erase_native_operations']:
        raise ValueError(f"Plan needs {operations} native operations; only {room['zero_erase_native_operations']} fit without a C/D erase; {room['reserved_intent_page']} is reserved")
    return room

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('bank3',type=Path)
    parser.add_argument('--require-zero-erase-operations',type=int)
    args=parser.parse_args();body=args.bank3.read_bytes()
    result=inspect(body) if args.require_zero_erase_operations is None else require_zero_erase_room(body,args.require_zero_erase_operations)
    print(json.dumps(result,indent=2))
