"""Assemble all four named-constant demos offline on both supported CPUs."""
import hashlib,json,os,re
from pathlib import Path
os.environ.setdefault('STR8_SOURCE_BUILD','BUILD/current')
from test_rc1_source_store import Harness,packed,ROOT

def main():
    cases=[];images={}
    for cpu in ('65c02','65c816-e'):
        h=Harness(cpu,'B',edu=True);h.command_limit=30000000;h.open()
        for stem in ('sxb-cs-patterns','edu-led31','sxb-cs-patterns-loop','edu-led31-loop'):
            path=ROOT/'examples/source-cycle'/(stem+'.asm');lines=path.read_text().splitlines()
            assert all(not re.search(r"\$[0-9A-Fa-f]+|'.'",line.split(';')[0]) for line in lines if '=' not in line)
            source=packed([(10*(i+1),line) for i,line in enumerate(lines)])
            h.set_source(source);h.command('ASM',contains='OK ')
            n=int.from_bytes(h.m.ram[h.asm['RESULT_LEN']:h.asm['RESULT_LEN']+2],'little')
            image=bytes(h.m.ram[0x200:0x200+n])
            if stem in images:assert image==images[stem]
            images[stem]=image
            reference=(ROOT/'BUILD/rc1-edu-loop/program.bin' if stem=='edu-led31-loop' else
                       ROOT/'BUILD/rc1-dev-samples/listings'/(stem+'.bin'))
            if reference.exists():assert image==reference.read_bytes()
            cases.append(dict(cpu=cpu,sample=stem,code_bytes=n,packed_source_bytes=len(source),
                              source_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
                              image_sha256=hashlib.sha256(image).hexdigest()))
            print('PASS',cpu,stem,n,'bytes',flush=True)
    (ROOT/'BUILD/rc1-demo-named-constants.json').write_text(json.dumps(dict(passed=True,board_access=False,cases=cases),indent=2)+'\n')
if __name__=='__main__':main()
