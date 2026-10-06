"""Check the clean beta4 profile and unchanged MAINT's actual RST opcodes."""
import hashlib
import json
import build_v2_beta4_launcher as apps
apps.OUT=apps.ROOT/'BUILD/v2-beta4'
apps.configure()
import test_v2_recovery as model

def main():
    passed=[]
    def done(name):passed.append(name);print('PASS '+name,flush=True)
    for keys in (b'',b'A\r',b'B\r'):
        cpu,mem=model.boot(keys=keys)
        assert b'STR8-N 2.0b4' in mem.tx
        assert b'installed' not in model.command(cpu,b'APPS\r')
        assert mem.banks[3][:8192]==b'\xff'*8192
        assert all(b==b'\xff'*32768 for b in mem.banks[:3])
    done('clean beta4 default/A/B boot and empty application/storage profile')
    source=apps.OUT/'kit/str8n-bank-maint-1.5-2000.s19'
    cells,entry=apps.fw.link.read_s19(source)
    body=bytes(cells[a] for a in range(entry,max(cells)+1))
    assert entry==0x2000 and max(cells)==0x3d53 and len(body)==7508
    assert hashlib.sha256(body).hexdigest()=='57a21e4076aeda84cad2fff920d282311f0a65ef2a254f966396484409b437db'
    done('BANK MAINT 1.5 is byte-identical to the retained program')
    cpu,mem=model.boot();before=[bytes(b) for b in mem.banks]
    stream=b'L\r'+source.read_bytes().replace(b'\n',b'\r\n')
    result=model.command(cpu,stream,limit=16000000)
    assert bytes(mem.ram[entry:max(cells)+1])==body,result
    assert [bytes(b) for b in mem.banks]==before
    done('host S19 load changes RAM only')
    assert b'Done' in model.command(cpu,b'S 1 8000 2000 3D53 MAINT\r',limit=16000000)
    assert b'B1:8000 2000-3D53 1D54 C MAINT' in model.command(cpu,b'T 1\r',limit=16000000)
    saved=[bytes(b) for b in mem.banks]
    mem.ram[entry:entry+8]=bytes(8)
    assert b'Done' in model.command(cpu,b'R 1 MAINT L\r',limit=16000000)
    assert mem.ram[entry:max(cells)+1]==body
    assert [bytes(b) for b in mem.banks]==saved
    done('SAVE/TABLE and byte-exact load-only RESTORE')
    assert b'BANK MAINT 1.5' in model.command(cpu,b'R 1 MAINT\r',limit=16000000)
    assert b'BM>' in model.command(cpu,b'T 1\r',limit=16000000)
    refused=model.command(cpu,b'E 3 A-F\r')
    assert b'CANCELED' in refused and [bytes(b) for b in mem.banks]==saved,refused
    assert b'VERIFIED' in model.command(cpu,b'E 1 8-9\rY\r',limit=16000000)
    assert b'B3>' in model.command(cpu,b'Q\r')
    assert mem.banks[0]==before[0] and mem.banks[1]==before[1] and mem.banks[2]==before[2]
    assert b'MAINT' not in model.command(cpu,b'T 1\r',limit=16000000)
    done('run RESTORE, protected B3 refusal and removal of optional saved copy')
    import zipfile
    with zipfile.ZipFile(apps.ROOT/'output/release/str8n-v2-b4.zip') as archive:
        manifest=json.loads(archive.read('manifest.json'))
        assert set(archive.namelist())==set(manifest['artifacts'])|{'manifest.json'}
        assert manifest['board_backups_included'] is False
        for name,digest in manifest['artifacts'].items():
            assert hashlib.sha256(archive.read(name)).hexdigest()==digest
    done('kit allowlist/hashes; no bank backups or applications')
    (apps.OUT/'beta4-test-results.json').write_text(json.dumps(dict(passed=passed,
        physical_hardware_tested=False,native_816_execution_tested=False),indent=2)+'\n')

if __name__=='__main__':main()
