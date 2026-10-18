"""Offline planner qualification: destination ownership, settings and backups.

These are logical planning/file-restoration checks, not installer execution,
program interruption or electrical/physical recovery tests.
"""
import argparse,binascii,copy,hashlib,json,random,shutil,subprocess,sys
from datetime import datetime,timezone
from pathlib import Path
import plan_beta35_offline as p

def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--out',required=True,type=Path);a=ap.parse_args()
    a.out.mkdir(parents=True,exist_ok=False);checks=[];payload=p.ROOT/'tmp/c35e/payload'
    source,destination,layout,files=p.load_inputs(payload)
    def passed(label,**detail):checks.append(dict(name=label,passed=True,**detail))
    def run(b,active=0xA0,backup=None):return p.plan(b,active,payload,b if backup is None else backup)
    def refuse(label,b,contains,active=0xA0,backup=None):
        try:run(b,active,backup)
        except ValueError as e:
            assert contains in str(e),(label,contains,str(e));passed(label,refusal=str(e))
        else:raise AssertionError('Unsafe plan accepted: '+label)
    def clone(b):return [bytearray(x) for x in b]
    def fixture(board,after=False):
        if after:
            folder=p.ROOT/f'output/qualification/beta35-fleet-2026-10-16/{board}';prefix='expected-b'
        else:
            base=p.ROOT/'output/qualification/beta34-fleet-2026-10-16'
            folder=base/'fresh/2512' if board=='2512' else base/board/'hardware';prefix='flash-1-b' if board=='2512' else 'final-b'
        return [(folder/f'{prefix}{i}.bin').read_bytes() for i in range(4)]
    def replace_settings(b,mutate):
        b=clone(b);identity=p.identify(b,0xA0,source);saved=p.settings(b,identity);off=saved['journal_offset']
        record=bytearray(b[3][off:off+128]);mutate(record)
        record[120:122]=p.crc(record[:120]).to_bytes(2,'little');b[3][off:off+128]=record
        return b
    try:
        for board in ['2205','2512','2604','2609']:
            before=fixture(board);historical=fixture(board,True);result,expected=run(before)
            assert len(result['proposed_payload_sectors'])==6 and not result['route_qualified']
            assert result['preferred_generation_matches_proposal'] is False
            assert not result['journal_transaction_planned']
            assert result['proposed_payload_sectors'][-1]['bank']==3 and result['proposed_payload_sectors'][-1]['sector']==11
            for bank in range(4):
                wanted=bytearray(historical[bank])
                if bank==3:wanted[0x4000:0x6000]=before[3][0x4000:0x6000]
                assert expected[bank]==wanted,(board,bank)
            assert expected[3][0x2000:0x3000]==before[3][0x2000:0x3000]
            (a.out/(board+'-logical-plan.json')).write_text(json.dumps(result,indent=2)+'\n')
            passed(board+' exact six-sector logical proposal; journal retained, activation unresolved')
            refuse(board+' active B refused',before,'unqualified A35',active=0xB0)
            current=fixture(board,True);noop,unchanged=run(current)
            assert noop['no_payload_change'] and not noop['proposed_payload_sectors'] and unchanged==current
            passed(board+' existing beta35 payloads produce no-op from active A')
        before=fixture('2512');base,_=run(before)
        # Seed every explicitly unowned interval, including shared erase-sector holes.
        mask=[bytearray(32768) for _ in range(4)]
        for r in layout['segments']:mask[r['bank']][r['address']-0x8000:r['address']-0x8000+r['bytes']]=b'\1'*r['bytes']
        changed=clone(before);rng=random.Random(0xB350624)
        protected=[(3,0x2000,0x3000),(3,0x4000,0x6000)]
        for bank in range(4):
            for i in range(32768):
                if not mask[bank][i] and not any(bank==b and start<=i<stop for b,start,stop in protected):
                    changed[bank][i]=rng.randrange(256)
        result,expected=run(changed)
        for bank in range(4):
            assert all(x==y for i,(x,y) in enumerate(zip(changed[bank],expected[bank])) if not mask[bank][i])
        passed('seeded full unowned ranges, mutable 9C tail and shared-sector holes preserved',seed='B350624')
        for r in layout['segments']:
            b=clone(before);off=r['address']-0x8000;b[r['bank']][off+min(127,r['bytes']-1)]^=1
            refusal=('Unregistered or altered source core' if r['address']==0xF000 and r['bank']==3
                else 'checksum mismatch' if r['address']==0xB000 and r['bank']==3
                else 'Source E conversion' if r['address']==0xE000 and r['bank']==3 else 'Unknown or occupied')
            refuse('occupied/corrupt '+r['file'],b,refusal)
        erased=replace_settings(before,lambda r:(r.__setitem__(slice(15,21),bytes(6)),r.__setitem__(slice(22,24),p.config_checksum(r[8:24]))))
        erased[3][0x3000:0x4000]=b'\xff'*4096
        result,_=run(erased);assert result['proposed_payload_sectors'][-1]['bank']==3
        passed('erased inactive B destination with automatic preference may be proposed')
        for i in range(4):
            stale=clone(before);stale[i][123]^=1
            try:p.validate_preimages(base,stale)
            except ValueError as e:assert 'Stale' in str(e)
            else:raise AssertionError('Stale preimage accepted')
            passed('stale bank '+str(i)+' invalidates full plan')
            refuse('backup mismatch bank '+str(i),before,'backup does not match',backup=stale)
        for label,index,value in [('version',8,2),('enable',9,2),('bank',10,4),('delay',13,9),('mode',14,2),('EDU tag',21,1)]:
            def mutate(r,index=index,value=value):
                r[index]=value;r[22:24]=p.config_checksum(r[8:24])
            refuse('invalid settings '+label,replace_settings(before,mutate),'Invalid stored startup settings')
        refuse('configuration checksum bad inside valid journal CRC',replace_settings(before,lambda r:r.__setitem__(22,r[22]^1)),
               'Invalid stored startup settings')
        refuse('protected RAM startup',replace_settings(before,lambda r:(r.__setitem__(slice(11,13),(0x6500).to_bytes(2,'little')),
               r.__setitem__(slice(22,24),p.config_checksum(r[8:24])))),'protected RAM')
        for label,tag,value in [('EDU OFF',0xA5,0x66ff),('EDU ON',0,0x64ff)]:
            b=replace_settings(before,lambda r,tag=tag,value=value:(r.__setitem__(21,tag),r.__setitem__(slice(11,13),value.to_bytes(2,'little')),
                r.__setitem__(slice(22,24),p.config_checksum(r[8:24]))))
            result,expected=run(b);assert expected[3][0x4000:0x6000]==b[3][0x4000:0x6000]
            passed(label+' valid startup/settings retained')
        refuse('malformed preference',replace_settings(before,lambda r:(r.__setitem__(15,ord('X')),r.__setitem__(slice(22,24),p.config_checksum(r[8:24])))),
               'Invalid monitor preference')
        refuse('stale preference generation',replace_settings(before,lambda r:(r.__setitem__(17,r[17]+1),r.__setitem__(slice(22,24),p.config_checksum(r[8:24])))),
               'Stale monitor preference')
        refuse('journal sequence exhaustion',replace_settings(before,lambda r:r.__setitem__(slice(4,8),b'\xff'*4)),'sequence exhausted')
        refuse('erase counter exhaustion',replace_settings(before,lambda r:r.__setitem__(slice(24+11*3,27+11*3),b'\xff'*3)),'counter exhausted')
        b=clone(before);b[3][0x4000:0x6000]=b'\xff'*8192;refuse('missing journal refuses defaults',b,'No valid configuration')
        b=clone(before);saved=p.settings(b,p.identify(b,0xA0,source));r=bytearray(b[3][saved['journal_offset']:saved['journal_offset']+128])
        r[8+5]=11;r[22:24]=p.config_checksum(r[8:24]);r[120:122]=p.crc(r[:120]).to_bytes(2,'little')
        b[3][0x5F80:0x6000]=r;refuse('ambiguous latest journal sequence',b,'Ambiguous latest')
        # Recognized sources still refuse until a target-specific conversion exists.
        for name,message in [('v2-beta4','Source F conversion'),('v2-beta28','Private ABI conversion')]:
            b=clone(before);folder=p.ROOT/'BUILD'/name
            for page in (0xA0,0xB0):b[3][(page-0x80)*256:(page-0x80)*256+4096]=(folder/f'str8n-v2-recovery-slot-{page:02x}.bin').read_bytes()
            b[3][0x7000:]=(folder/'str8n-v2-recovery-f000-ffff.bin').read_bytes();refuse(name+' conversion refused',b,message)
        legacy=clone(before);legacy[3][0x7000:]=(p.ROOT/'BUILD/v2-a24c1/str8n-v2-a24c1-f000-ffff.bin').read_bytes()
        refuse('legacy recognized but conversion refused',legacy,'Legacy conversion',active=None)
        # Backup integrity is checked on disk, not inferred from a declared hash list.
        backupdir=a.out/'private-backup-fixture';p.write_backup(backupdir,before)
        restored=p.read_backup(backupdir);assert restored==before;passed('full four-bank backup/file restoration byte exact')
        for i in range(4):
            path=backupdir/f'b{i}.bin';data=path.read_bytes();bad=bytearray(data);bad[53]^=1;path.write_bytes(bad)
            try:p.read_backup(backupdir)
            except ValueError as e:assert 'integrity mismatch' in str(e)
            else:raise AssertionError('Corrupt backup accepted')
            path.write_bytes(data);passed('backup member '+str(i)+' corruption refuses')
        manifest=backupdir/'manifest.json';original=manifest.read_bytes();m=json.loads(original);m['banks'][0]['name']='../b0.bin';manifest.write_text(json.dumps(m))
        try:p.read_backup(backupdir)
        except ValueError as e:assert 'Invalid backup member' in str(e)
        else:raise AssertionError('Unsafe backup path accepted')
        manifest.write_bytes(original);passed('backup path traversal refuses')
        # Exercise CLI plan output with serial import mechanically forbidden.
        code='import builtins,runpy,sys\norig=builtins.__import__\ndef checked(name,*a,**k):\n if name=="serial" or name.startswith("serial."):raise RuntimeError("Serial import forbidden")\n return orig(name,*a,**k)\nbuiltins.__import__=checked\nsys.path.insert(0,"tools")\nsys.argv='+repr(['plan_beta35_offline.py','plan','--banks-dir',str(backupdir),'--backup-dir',str(backupdir),'--payload-dir',str(payload),'--active','A','--out',str(a.out/'cli-plan.json')])+'\nrunpy.run_path("tools/plan_beta35_offline.py",run_name="__main__")\n'
        process=subprocess.run([sys.executable,'-c',code],cwd=p.ROOT,capture_output=True,text=True)
        (a.out/'cli.stdout.txt').write_text(process.stdout);(a.out/'cli.stderr.txt').write_text(process.stderr)
        assert process.returncode==0,process.stderr
        cli=json.loads((a.out/'cli-plan.json').read_text());assert not cli['execution_permitted']
        passed('CLI plan works with serial imports forbidden')
        # Pin every target file, including non-layout example/bootstrap inputs.
        tampered=a.out/'tampered-payload';shutil.copytree(payload,tampered)
        meta=json.loads((p.ROOT/'release/beta35/release.json').read_text())
        for name in meta['expected']:
            path=tampered/name;data=path.read_bytes();bad=bytearray(data);bad[-1]^=1;path.write_bytes(bad)
            try:p.plan(before,0xA0,tampered,before)
            except ValueError as e:assert 'Target payload integrity mismatch' in str(e)
            else:raise AssertionError('Altered target accepted: '+name)
            path.write_bytes(data);passed('tampered target refuses '+name)
    except Exception:
        import traceback
        (a.out/'failure.json').write_text(json.dumps(dict(passed=False,checks=checks,error=traceback.format_exc()),indent=2)+'\n');raise
    report=dict(passed=True,cases=len(checks),checks=checks,finished_utc=datetime.now(timezone.utc).isoformat(),
        planner_sha256=p.sha((p.ROOT/'tools/plan_beta35_offline.py').read_bytes()),
        test_sha256=p.sha(Path(__file__).read_bytes()),source_catalog_sha256=p.SOURCE_SHA,destination_catalog_sha256=p.DESTINATION_SHA,
        board_access=False,serial_import_forbidden_cli=True,route_qualified=False,installation_permitted=False,release_qualified=False,
        journal_transaction_qualified=False,installer_execution_qualified=False,physical_restoration_qualified=False,
        scope='Logical B-target planning, ownership/settings/refusal and archived backup file restoration only')
    (a.out/'report.json').write_text(json.dumps(report,indent=2)+'\n')
    print('PASS',len(checks),'offline logical-plan/refusal/backup scenarios; journal and installer gates remain open')

if __name__=='__main__':main()
