"""Offline fixed b14 MON removal/restore kit; no firmware rebuild or I/O."""
import argparse,binascii,json,shutil,sys
from pathlib import Path
HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
sys.path[:0]=[str(ROOT/'tools'),str(HERE)]
from str8build.assemble import Assembly
from str8build.formats import db,save,sha
from build import long_branches

def data_rows(data):
    return ''.join('        DB '+','.join(f'${b:02X}' for b in data[i:i+16])+'\n' for i in range(0,len(data),16))

def build(out,source,plan):
    out=out.resolve();assert not out.exists(),'Fresh output required'
    out.mkdir(parents=True);shutil.copytree(source/'s',out/'s');shutil.copytree(source/'payload',out/'payload')
    shutil.copy2(source/'prototype-report.json',out/'prototype-report.json')
    a=object.__new__(Assembly);a.out=out;a.assembler=shutil.which('wdc02as');a.linker=shutil.which('wdcln');a.compiled=[]
    a.symbols=json.loads((source/'symbols.json').read_text());core=out/'s/core'
    banks=[(plan/f'expected-b{n}.bin').read_bytes() for n in range(4)]
    prefix='        MODULE MON_ABSENT\n        INCLUDE "str8n-v2-eq.inc"\n        INCLUDE "str8n-v2-public.inc"\n        INCLUDE "vectors-symbols.inc"\n        INCLUDE "boot-symbols.inc"\n'
    def link(name,body,address,end):
        (core/(name+'.asm')).write_text(long_branches(prefix+'        CODE\n'+body+'\n        ENDMOD\n        END\n'))
        data,sy=a.link('core',name,address,end);a.emit(name+'.bin',data);return data,sy
    service,ss=link('mon-service',(HERE/'mon-absent-service.inc').read_text(),0x6800,'MS_END')
    bootstrap='MS_BOOTSTRAP:\n        SEI\n        CLD\n'
    # An explicit unrolled copy avoids borrowing any owner ZP before execution.
    for off in range(len(service)):
        bootstrap+=f'        LDA MS_BLOB+{off}\n        STA ${0x6800+off:04X}\n'
    bootstrap+='        JMP $6800\nMS_BLOB:\n'+data_rows(service)+'\nMS_LOAD_END:\n'
    load,ls=link('mon-service-load',bootstrap,0x200,'MS_LOAD_END')
    fsum=binascii.crc_hqx(banks[3][-4096:],65535)
    body=f'F_SUM_LO EQU ${fsum&255:02X}\nF_SUM_HI EQU ${fsum>>8:02X}\n'+(HERE/'mon-absent-tool.inc').read_text()
    body+='\n        INCLUDE "prototype-engine.inc"\nMA_IMAGE_A:\n'+data_rows(banks[3][0x2000:0x3000])+'\nMA_IMAGE_B:\n'+data_rows(banks[3][0x3000:0x4000])+'\nMA_SUM: DB 0,0\nMA_END:\n'
    tool,ts=link('mon-kit',body,0x200,'MA_END');assert ts['MA_SUM']==ts['MA_END']-2
    tool=tool[:-2]+binascii.crc_hqx(tool[:-2],65535).to_bytes(2,'little');a.emit('mon-kit.bin',tool)
    assert ts['MA_END']<0x6500 and ss['MS_END']<0x7800 and len(load)<=0x6300
    save(out/'symbols.json',a.symbols)
    report=dict(passed=True,hardware=False,source_build=str(source.resolve()),source_plan=str(plan.resolve()),
        source_bank_sha256=[sha(b) for b in banks],F_sha256=sha(banks[3][-4096:]),
        tool_bytes=len(tool),service_bytes=len(service),service_loader_bytes=len(load),
        targets=['B3:A','B3:B'],writer_bytes=ts['JE_END']-ts['JE_ENTER'],
        RAM_restore_range='0200-64FF',reserved_service_range=f'6800-{ss["MS_END"]-1:04X}',
        compiled=a.compiled,sources={p.name:sha(p.read_bytes()) for p in [Path(__file__),HERE/'mon-absent-tool.inc',HERE/'mon-absent-service.inc']},
        artifacts={p.name:sha(p.read_bytes()) for p in (out/'payload').glob('*.bin')})
    save(out/'mon-absent-build.json',report);return report

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--out',type=Path,required=True)
    p.add_argument('--source',type=Path,default=ROOT/'BUILD/pr04-b14-raw-r4');p.add_argument('--plan',type=Path,default=ROOT/'tmp/pr04-b14-2512-native-plan')
    x=p.parse_args();print(json.dumps(build(x.out,x.source,x.plan),indent=2))
