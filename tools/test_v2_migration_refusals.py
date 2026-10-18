"""No-write planning refusals against actual fleet backup fixtures."""
import json,shutil
from pathlib import Path
import migrate_v2 as u

def main():
    base=u.ROOT/'output/qualification/beta25-fleet-2026-10-14';fixtures=base/'refusal-fixtures';fixtures.mkdir(exist_ok=False);checks=[]
    for board in ('2205','2609','2512'):
        source=base/board;root=fixtures/board;root.mkdir();shutil.copytree(source/'prior-verified',root/'prior-verified');shutil.copyfile(source/'initial-state.json',root/'initial-state.json')
        if board=='2512':
            p=root/'prior-verified';b=bytearray((p/'b3.bin').read_bytes());b[0x6004]^=1
            (p/'b3.bin').write_bytes(b);(p/'b3-repeat.bin').write_bytes(b);m=u.read(p/'manifest.json');m['banks'][3]['sha256']=u.sha(b);(p/'manifest.json').write_text(json.dumps(m,indent=2)+'\n')
        try:u.prepare(root,board,None)
        except (ValueError,AssertionError) as exc:
            assert ('Unregistered shared E' if board=='2512' else 'already at target') in str(exc),str(exc)
        else:raise AssertionError('Refusal missing')
        assert not (root/'upgrade').exists();checks.append(board+': '+('unregistered E protected' if board=='2512' else 'already-current fallback protected'))
    (base/'planning-refusals.json').write_text(json.dumps(dict(passed=True,checks=checks,board_access=False),indent=2)+'\n');print('\n'.join('PASS '+c for c in checks))

if __name__=='__main__':main()
