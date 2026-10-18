"""Replay-bound offline legacy recovery admission. No port or live launcher."""
import json
from pathlib import Path
import plan_bf1_2512_legacy as p

def prepare(manifest_path,manifest_sha256,case,cut_count,current):
    assert p.sha(manifest_path.read_bytes())==manifest_sha256,'Recovery certificate changed'
    certificate=p.read(manifest_path);assert certificate['passed'] and certificate['offline_only']
    root=Path(certificate['root']).resolve()
    def load(name):
        path=(root/name).resolve();assert path.is_relative_to(root) and name in certificate['files']
        raw=path.read_bytes();assert p.sha(raw)==certificate['files'][name],'Recovery input changed: '+name
        return raw
    report=json.loads(load('report.json'));assert report['passed'] and report['planner_sha256']==p.sha(Path(p.__file__).read_bytes())
    check=next(x for x in report['checks'] if x['name']==case and x.get('outcome')=='complete');assert check['passed']
    plan=json.loads(load(case+'/plan.json'));tx=plan['transaction']
    source=[load(case+f'/source-b{n}.bin') for n in range(4)]
    desired=[load(case+f'/expected-b{n}.bin') for n in range(4)]
    assert p.hashes(source)==plan['source_sha256']==tx['source_sha256']
    assert p.hashes(desired)==plan['expected_sha256']==check['bank_sha256']
    events=json.loads(load(case+'/events.json'));assert len(events)==check['mutation_events'] and 0<=cut_count<=len(events)
    state=list(map(bytearray,source));attempts=[0]*32;erases=[]
    reserve=tx['operations'][0]['address'];allowed=set(map(tuple,tx['planned_erase_order']))
    for kind,bank,address,value in events[:cut_count]:
        assert 0<=bank<4 and 0x8000<=address<=0xffff and 0<=value<=255
        off=address-0x8000
        if kind=='erase':
            assert address&4095==0;erases.append([bank,address>>12]);assert erases==tx['planned_erase_order'][:len(erases)]
            state[bank][off:off+4096]=b'\xff'*4096;attempts[bank*8+(address>>12)-8]+=1
        else:
            assert kind=='program' and ((bank,address>>12) in allowed or bank==3 and reserve<=address<reserve+128)
            assert state[bank][off]&value==value;state[bank][off]=value
        latest=p.latest(state)[2]
        assert all(int.from_bytes(latest[24+i*3:27+i*3],'little')>=tx['counts_before'][i]+attempts[i] for i in range(32)), 'Wear reservation below observed attempts'
    assert list(map(bytes,state))==list(map(bytes,current)), 'Unexplained recovery preimage mismatch'
    return p.transaction(current,desired,bytes.fromhex(tx['target_config']),case+' cut recovery',attested_cut=True)
