"""Exercise offline source recognition against project and historical fixtures."""
import argparse
import binascii
from datetime import datetime,timezone
import hashlib
import json
from pathlib import Path

from inspect_beta35_source import identify,ROOT,CATALOG


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out',required=True,type=Path);args=parser.parse_args()
    assert not args.out.exists()
    catalog=json.loads(CATALOG.read_text());checks=[]
    def accept(label,banks,active,version,*,target=False):
        result=identify(banks,active,catalog)
        assert result['source_version']==version and not result['execution_permitted'] and not result['route_qualified']
        if active is not None:assert result['target_monitor_present']==target
        checks.append(dict(name=label,passed=True,disposition=result['disposition']))
    def refuse(label,banks,active,contains):
        try:identify(banks,active,catalog)
        except ValueError as e:
            assert contains in str(e),(contains,str(e));checks.append(dict(name=label,passed=True,refusal=str(e)))
        else:raise AssertionError('Unsafe source accepted: '+label)
    def banks_from(build):
        folder=ROOT/'BUILD'/build;banks=[bytearray(b'\xff'*32768) for _ in range(4)]
        banks[3][0x7000:]=(folder/'str8n-v2-recovery-f000-ffff.bin').read_bytes()
        for page in (0xA0,0xB0):
            off=(page-0x80)*256;banks[3][off:off+4096]=(folder/f'str8n-v2-recovery-slot-{page:02x}.bin').read_bytes()
        return banks
    sample=None
    for board in ['2205','2512','2604','2609']:
        old=ROOT/'output/qualification/beta34-fleet-2026-10-16'
        folder=old/'fresh/2512' if board=='2512' else old/board/'hardware'
        prefix='flash-1-b' if board=='2512' else 'final-b'
        before=[bytearray((folder/f'{prefix}{i}.bin').read_bytes()) for i in range(4)]
        after=[bytearray((ROOT/f'output/qualification/beta35-fleet-2026-10-16/{board}/expected-b{i}.bin').read_bytes()) for i in range(4)]
        for page,version in [(0xA0,'2.0b28'),(0xB0,'2.0b34')]:accept(board+' historical beta34 '+hex(page),before,page,version)
        for page,version in [(0xA0,'2.0b28'),(0xB0,'2.0b35')]:accept(board+' historical beta35 '+hex(page),after,page,version,target=True)
        sample=before
    for build,version in [('v2-beta4','2.0b4'),('v2-beta28','2.0b28'),('v2-beta28-b23','2.0b28')]:
        for page in (0xA0,0xB0):accept(build+' '+hex(page),banks_from(build),page,version)
    legacy=[bytearray(b'\xff'*32768) for _ in range(4)]
    legacy[3][0x7000:]=(ROOT/'BUILD/v2-a24c1/str8n-v2-a24c1-f000-ffff.bin').read_bytes()
    accept('legacy exact code is conversion-only',legacy,None,'beta1/a24c1')
    mutable=[bytearray(b) for b in legacy];mutable[3][0x7FD0:0x7FE0]=bytes(range(16))
    accept('legacy mutable startup region is recognized, not approved',mutable,None,'beta1/a24c1')
    refuse('legacy cannot claim inactive-slot semantics',legacy,0xB0,'no A/B active-slot contract')
    refuse('active slot must be explicit',sample,None,'Explicit A/B active monitor required')
    corrupt=[bytearray(b) for b in sample];corrupt[3][0x7123]^=1
    refuse('altered F refuses despite familiar ABI token',corrupt,0xB0,'Unregistered or altered source core')
    corrupt=[bytearray(b) for b in sample];corrupt[3][0x3123]^=1
    refuse('bad active-slot checksum',corrupt,0xB0,'checksum mismatch')
    corrupt=[bytearray(b) for b in sample];slot=bytearray(corrupt[3][0x3000:0x4000]);slot[128]^=1
    slot[18:20]=binascii.crc_hqx(slot[:18]+slot[32:],0xFFFF).to_bytes(2,'little');corrupt[3][0x3000:0x4000]=slot
    refuse('unknown opcode refuses even with valid CRC and ABI',corrupt,0xB0,'Unregistered monitor code')
    corrupt=[bytearray(b) for b in sample];corrupt[3][0x2123]^=1
    refuse('corrupt inactive destination is not silently accepted',corrupt,0xB0,'checksum mismatch')
    mismatch=banks_from('v2-beta4');mismatch[3][0x7000:]=banks_from('v2-beta28')[3][0x7000:]
    refuse('known images with incompatible private ABI refuse',mismatch,0xA0,'ABI profile mismatch')
    erased=[bytearray(b) for b in sample];erased[3][0x3000:0x4000]=b'\xff'*4096
    refuse('erased active monitor refuses',erased,0xB0,'Active monitor is erased')
    erased=[bytearray(b) for b in sample];erased[3][0x2000:0x3000]=b'\xff'*4096
    accept('empty inactive slot is recognized but not a write authorization',erased,0xB0,'2.0b34')
    changed=[bytearray(b) for b in sample];changed[0][123]^=1
    accept('unrelated bank data does not change code identity or permit writes',changed,0xB0,'2.0b34')
    report=dict(passed=True,checks=checks,cases=len(checks),board_access=False,
        source_inspection_only=True,execution_permitted=False,migration_route_qualified=False,
        finished_utc=datetime.now(timezone.utc).isoformat(),
        catalog_sha256=hashlib.sha256(CATALOG.read_bytes()).hexdigest(),
        inspector_sha256=hashlib.sha256((ROOT/'tools/inspect_beta35_source.py').read_bytes()).hexdigest(),
        test_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest())
    args.out.parent.mkdir(parents=True,exist_ok=True);args.out.write_text(json.dumps(report,indent=2)+'\n')
    print('PASS',len(checks),'offline source-inspection scenarios; no installation authorization')


if __name__=='__main__':main()
