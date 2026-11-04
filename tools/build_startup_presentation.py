"""Build selected MON presentation and changed STATUS core only; never F.

Text and gF guarded SRAM/RTC details retain their admitted allocations/bytes.
ROM/RAM are distinct link targets, each assembled once. No simulations or I/O.
"""
import argparse, binascii, json, re, shutil, subprocess
from pathlib import Path
from build_mona import ROOT, build as build_mon, cells, sha
from mona_branches import conservative_branches

WORKSPACE = ROOT.parents[1]

def build(out):
    out = Path(out).resolve()
    out.mkdir(exist_ok=False, parents=True)
    mon = build_mon(out/'MON', 0x10)
    artifacts = {}; logs = []
    sources = {'monitors/status/status-core.asm': sha((ROOT/'monitors/status/status-core.asm').read_bytes())}
    for variant, base, previous in (
        ('ROM', 0xAC00, WORKSPACE/'BUILD/status-g1-r4'),
        ('RAM', 0x3000, WORKSPACE/'BUILD/status-g1-RAM-r1')):
        stage = out/variant; stage.mkdir()
        for name in ('str8n-v2-public.inc','status-interface.inc','status-bindings.inc','status-text.inc','status-sram.inc'):
            shutil.copyfile(previous/'status-core'/name,stage/name)
        source = (ROOT/'monitors/status/status-core.asm').read_text(encoding='utf-8')
        source = re.sub(r'^\s*SAY (\w+)\s*$',lambda m:f'        LDX #<{m[1]}\n        LDY #>{m[1]}\n        JSR ST_PRINT',source,flags=re.M)
        source,_ = conservative_branches(source,'presentation_'+variant+'_')
        (stage/'status-core.asm').write_text(source,encoding='utf-8',newline='\n')
        for command in (
            [shutil.which('wdc02as'),'-G','-L','-S','-W','status-core.asm'],
            [shutil.which('wdcln'),'-g','-s','-t',f'-c{base:04X}','-hm19','-j','-o','status-core.s19','status-core.obj']):
            result = subprocess.run(command,cwd=stage,capture_output=True,text=True)
            logs.append(dict(variant=variant,command=command,returncode=result.returncode,stdout=result.stdout,stderr=result.stderr))
            (out/'build-log.json').write_text(json.dumps(logs,indent=2)+'\n')
            if result.returncode: raise RuntimeError('STATUS core build failed; inspect build-log.json')
        sy={n:int(v,16) for v,n in re.findall(r'^\s*([0-9A-Fa-f]{8})\s+(\w+)\s*$',(stage/'status-core.map').read_text(),re.M)}
        memory = cells(stage/'status-core.s19')
        assert set(memory) == set(range(base,sy['SC_END']))
        body = bytes(memory[a] for a in range(base,sy['SC_END']))
        assert len(body) <= 1022
        image = body.ljust(1022,b'\xff')
        image += binascii.crc_hqx(image,65535).to_bytes(2,'big')
        name = f'STATUS-{variant}.bin'; (out/name).write_bytes(image)
        artifacts[name] = dict(bytes=len(image),linked_bytes=len(body),free_bytes=1022-len(body),sha256=sha(image))
        # Unchanged strings/details are dependencies, not new builds.
        prior = json.loads((previous/'manifest.json').read_text())
        for text_name, info in prior['artifacts'].items():
            if not text_name.startswith('STATUS-text-'): continue
            data = (previous/text_name).read_bytes(); assert sha(data)==info['sha256']
            (stage/text_name).write_bytes(data)
        detail_name = f'STATUS-{variant}.bin'
        detail_dir = WORKSPACE/'BUILD/status-autoprep-r1'
        detail = (detail_dir/detail_name).read_bytes()
        detail_manifest = json.loads((detail_dir/'manifest.json').read_text())
        assert sha(detail)==detail_manifest['artifacts'][detail_name]['sha256']
        (stage/'STATUS-details.bin').write_bytes(detail)
        print(variant,'STATUS core',len(body),'bytes; free',1022-len(body),flush=True)
    report=dict(component='Traditional firmware startup / detailed VERSION',generation='00000010',
        status='BUILD_ONLY_NOT_EXECUTION_QUALIFIED',MON_manifest=str(out/'MON/manifest.json'),
        artifacts=artifacts,source_sha256=sources,F_sha256=mon['F_sha256'],F_rebuilt=False,
        unchanged_text_and_gF_details_reused=True,build_passes=1,CPU_simulations=0,hardware_access=False,
        flash_scope='not authorized; MON A/B and STATUS core are candidates only')
    (out/'manifest.json').write_text(json.dumps(report,indent=2)+'\n')
    return report

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--out',type=Path,required=True)
    build(p.parse_args().out)
