"""Compose separate model-only transaction images; no serial or device access.

The original template gets one explicit JMP detour plus its documented plan
data. Original template and sealed bank payloads are never modified in place.
"""
import argparse,json,re,shutil,subprocess,sys
from pathlib import Path
import plan_beta35_journal_transaction as journal
p=journal.p
ROOT=p.ROOT
sys.path.insert(0,str(ROOT/'release/beta35'))
from build import read_s19,s19
MANIFEST_SHA='5612d0121df646728b64057df53de1c6faa2c8f324ee7cb16679b8341c261aed'

def fnv(data):
    v=0x811c9dc5
    for x in data:v=((v^x)*0x1000193)&0xffffffff
    return v

def fixture(board):
    base=ROOT/'output/qualification/beta34-fleet-2026-10-16';folder=base/'fresh/2512' if board=='2512' else base/board/'hardware'
    prefix='flash-1-b' if board=='2512' else 'final-b'
    return [(folder/f'{prefix}{i}.bin').read_bytes() for i in range(4)]

def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--helper-build',required=True,type=Path);parser.add_argument('--out',required=True,type=Path);a=parser.parse_args()
    out=a.out.resolve();assert not out.exists() and len(str(out))<=65
    helper=p.read(a.helper_build/'build-report.json');binary=(a.helper_build/'reservation.bin').read_bytes()
    prior=p.read(ROOT/'output/qualification/beta35-prerelease-2026-10-17/reservation-helper-0826-r2/report.json')
    assert helper['binary_sha256']==p.sha(binary)==prior['helper_binary_sha256']
    assert p.sha((a.helper_build/'build-report.json').read_bytes())==prior['build_report_sha256']
    assert p.sha((ROOT/'release/beta35-prerelease/source/reservation.asm').read_bytes())==helper['source_sha256']
    manifest_path=ROOT/'BUILD/v2-beta35-candidate/migrator/manifest.json';assert p.sha(manifest_path.read_bytes())==MANIFEST_SHA
    mf=p.read(manifest_path);payload=ROOT/'tmp/c35e/payload';_,_,_,files=p.load_inputs(payload)
    template_path=payload/'migrator/rtc-migrator-2000.s19';assert p.sha(template_path.read_bytes())==mf['sha256']
    original=read_s19(template_path);start=mf['symbols']['MIG_NEXT']
    assert bytes(original[i] for i in range(start,start+3))==b'\xae\0\x62'
    out.mkdir(parents=True);stage=out/'asm';stage.mkdir()
    source=ROOT/'release/beta35-prerelease/source/reservation-entry.asm';shutil.copyfile(source,stage/'reservation-entry.asm')
    (stage/'transaction-links.inc').write_text(f'MIG_NEXT_CONTINUE EQU ${start+3:04X}\nMIG_FAIL EQU ${mf["symbols"]["MIG_FAIL"]:04X}\n')
    assembler=shutil.which('wdc02as');linker=shutil.which('wdcln');assert assembler and linker
    logs=[]
    for cmd in [[assembler,'-G','-L','-S','-W','-I',str(stage),'reservation-entry.asm'],
        [linker,'-g','-s','-t','-c3300','-hm19','-j','-o','reservation-entry.s19','reservation-entry.obj']]:
        result=subprocess.run(cmd,cwd=stage,capture_output=True,text=True)
        logs.append(dict(command=cmd,returncode=result.returncode,stdout=result.stdout,stderr=result.stderr))
        (stage/'build.log.json').write_text(json.dumps(logs,indent=2)+'\n');assert result.returncode==0,(result.stdout,result.stderr)
    symbols={n:int(v,16) for v,n in re.findall(r'^\s*([0-9a-fA-F]{8}) (\w+)\s*$',(stage/'reservation-entry.map').read_text(),re.M)}
    wrapper=read_s19(stage/'reservation-entry.s19');assert set(wrapper)==set(range(0x3300,symbols['T_END'])) and symbols['T_END']<0x3500
    boards=[]
    for board in ['2205','2512','2604','2609']:
        banks=fixture(board);tx,data,expected=journal.transaction(banks,0xA0,payload,banks,activation='select-B35')
        assert not tx['no_change'] and len(tx['operations'])==9
        image=dict(original);image.update(dict(enumerate(binary,0x3000)));image.update(wrapper)
        image.update({i:0 for i in range(max(original)+1,0x3700) if i not in image})
        image.update(dict(enumerate(b'\x4c\0\x33',start)))
        image.update(dict(enumerate(b''.join(fnv(b).to_bytes(4,'little') for b in banks),0x3500)))
        image.update(dict(enumerate(tx['operations'][0]['address'].to_bytes(2,'little'),0x3510)))
        page=data[0]+b'\xff'*128
        image.update(dict(enumerate(fnv(page).to_bytes(4,'little'),0x3512)));image.update(dict(enumerate(page,0x3600)))
        rows=tx['operations'][1:];image[mf['count']]=len(rows);image[mf['commit_after']]=0
        for i in range(mf['max_sectors']):
            image[mf['banks']+i]=0;image[mf['commits']+i]=0
            for k in range(4):image[mf['commit_addresses']+4*i+k]=0
        pending=[bytearray(b) for b in banks];off=tx['reservation_offset'];pending[3][off:off+128]=data[0]
        transfers=[]
        for i,(op,body) in enumerate(zip(rows,data[1:])):
            bank=op['bank'];address=op['address'];sector=address>>12;offset=address-0x8000
            assert p.bank_hashes(pending)==op['source_bank_sha256']
            transfer=bytearray(body);commit=op['commit_address'] if op['kind']=='payload-sector' else None
            if commit is not None:transfer[commit-address]=255
            row=bytes([sector<<4])+fnv(pending[bank]).to_bytes(4,'little')+fnv(transfer).to_bytes(4,'little')
            image.update(dict(enumerate(row,mf['table']+9*i)));image[mf['banks']+i]=bank
            if commit is not None:
                image[mf['commits']+i]=bank+1
                image.update(dict(enumerate(commit.to_bytes(2,'little'),mf['commit_addresses']+4*i)))
            pending[bank][offset:offset+4096]=transfer
            if commit is not None:pending[bank][commit-0x8000]=body[commit-address]
            assert p.bank_hashes(pending)==op['proposed_bank_sha256'];transfers.append(bytes(transfer))
        assert [bytes(b) for b in pending]==expected
        allowed={start,start+1,start+2,mf['count'],mf['commit_after']}
        for key,n in [('banks',16),('commits',16),('commit_addresses',64),('table',mf['table_bytes'])]:allowed.update(range(mf[key],mf[key]+n))
        assert all(image[i]==v for i,v in original.items() if i not in allowed)
        directory=out/board;directory.mkdir();raw=bytes(image[i] for i in range(0x2000,0x3700));installer=s19(raw,0x2000,0x2000)
        (directory/'installer-model-only.s19').write_bytes(installer)
        for i,b in enumerate(transfers):(directory/f'transfer-{i:02d}.bin').write_bytes(b)
        for i,b in enumerate(expected):(directory/f'expected-b{i}.bin').write_bytes(b)
        info=dict(board=board,transaction=tx,steps=[[op['bank'],op['address']>>12] for op in rows],
            installer_sha256=p.sha(installer),transfer_sha256=[p.sha(x) for x in transfers],
            expected_sha256=p.bank_hashes(expected),source_sha256=p.bank_hashes(banks),
            template_sha256=mf['sha256'],template_manifest_sha256=MANIFEST_SHA,
            template_instruction_patch=dict(address=start,before_hex='ae0062',after_hex='4c0033',meaning='Detour through once-only reservation wrapper; original LDX replayed'),
            helper_binary_sha256=p.sha(binary),wrapper_symbols=symbols,helper_entry=0x3000,entry=0x2000,
            model_only=True,installation_permitted=False,release_qualified=False,board_access=False)
        (directory/'plan.json').write_text(json.dumps(info,indent=2)+'\n');boards.append(dict(board=board,plan_sha256=p.sha((directory/'plan.json').read_bytes()),installer_sha256=p.sha(installer)))
    report=dict(passed=True,wrapper_source_sha256=p.sha(source.read_bytes()),wrapper_bytes=symbols['T_END']-0x3300,
        helper_binary_sha256=p.sha(binary),builder_sha256=p.sha(Path(__file__).read_bytes()),boards=boards,
        toolchain_sha256={Path(x).name:p.sha(Path(x).read_bytes()) for x in (assembler,linker)},
        model_qualified=False,installation_permitted=False,release_qualified=False,board_access=False)
    (out/'build-report.json').write_text(json.dumps(report,indent=2)+'\n');print('PASS four separate eight-sector model-only transaction images; original template/payloads unchanged')

if __name__=='__main__':main()
