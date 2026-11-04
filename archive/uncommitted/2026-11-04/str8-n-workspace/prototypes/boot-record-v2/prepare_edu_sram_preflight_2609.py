"""Build the same read-only inspection service entirely in RAM before ROM install."""
import argparse,shutil
from pathlib import Path
import prepare_edu_sram_2609 as p
from str8build.assemble import Assembly
from str8build.formats import crc

BIN='2609-EDU-SRAM-PREFLIGHT-RAM.bin'


def build(provider_build,out):
    provider_build,out=Path(provider_build).resolve(),Path(out).resolve();info=p.verify(provider_build)
    assert not out.exists() and out.is_relative_to(p.ROOT/'output/qualification')
    out.mkdir(parents=True);(out/'.gitignore').write_text('*\n');shutil.copytree(provider_build/'s',out/'s');(out/'payload').mkdir()
    core=out/'s/core';text=(p.HERE/'edu-sram-ro-client.asm').read_text()
    begin=text.index('        LDX #63\nEC_HEADER:');end=text.index('        JSR $8004\n',begin)
    text=text[:begin]+text[end:]
    for address,label in (('8004','ES_INIT'),('8007','ES_QUERY'),('800A','ES_READ'),('800D','ES_PREP')):
        text=text.replace('JSR $'+address,'JSR '+label)
    text=text.split('EC_IMAGE_CRC:',1)[0]
    text=text.replace('MODULE EDU_SRAM_RO_CLIENT','MODULE EDU_SRAM_RO_PREFLIGHT')
    text=text.replace('ES1 EDU/SRAM READ ONLY / 2609 b15','ES1 EDU/SRAM RAM PREFLIGHT / READ ONLY / 2609 b15')
    # Fixed RAM state is outside the immutable code/CRC and outside request/data.
    address=0x6300
    for label,width in (('EC_SRC',2),('EC_COUNT',2),('EC_CRC',2),('EC_VALUE',3),('EC_INDEX',1),('EC_LENGTH',1),('EC_RESULT',1),('EC_ERROR',1)):
        text+=f'{label} EQU ${address:04X}\n';address+=width
    provider=(p.HERE/'edu-sram-ro-provider.asm').read_text()
    declarations=provider.split('ER EQU ',1)[1].split('        CODE\n',1)[0]
    code=provider.split('        CODE\n',1)[1].split('ES_END:',1)[0]
    text+='        INCLUDE "edu-sram-params.inc"\nER EQU '+declarations+code
    text+='EC_IMAGE_CRC: DW 0\nEC_IMM_END:\nEC_END:\n        ENDMOD\n        END\n'
    (core/'edu-preflight.asm').write_text(p.base.long_branches(text).replace('P_LONG_','EP_LONG_'))
    a=object.__new__(Assembly);a.out=out;a.assembler=shutil.which('wdc02as');a.linker=shutil.which('wdcln')
    a.compiled=[];a.symbols=p.base.read(provider_build/'symbols.json')
    body,sy=a.link('core','edu-preflight',0x200,'EC_END');body=bytearray(body)
    offset=sy['EC_IMAGE_CRC']-0x200;body[offset:offset+2]=crc(body[:offset]).to_bytes(2,'big')
    assert crc(body)==0 and sy['EC_END']<0x2000;a.emit(BIN,body)
    shutil.copy2(provider_build/'payload/f-offline-component.bin',out/'payload/f-offline-component.bin')
    for name in ('prototype-report.json','baseline.json'):
        shutil.copy2(provider_build/name,out/name)
    for n in range(4):shutil.copy2(provider_build/f'source-b{n}.bin',out/f'source-b{n}.bin')
    p.base.save(out/'symbols.json',a.symbols)
    paths=[Path(__file__),p.HERE/'edu-sram-ro-provider.asm',p.HERE/'edu-sram-ro-client.asm',provider_build/'plan.json']
    artifacts=[out/'payload'/BIN,out/'symbols.json',core/'edu-preflight.asm',*out.glob('source-b?.bin')]
    result=dict(passed=True,hardware=False,board_access=False,serial_access=False,flashed=False,SRAM_writes=False,
        BIN=BIN,bytes=len(body),sha256=p.base.sha(body),load_address='0200',end_exclusive=f'{sy["EC_END"]:04X}',
        provider_build=str(provider_build),provider_build_sha256=p.base.digest(provider_build/'plan.json'),
        inputs={str(path.resolve()):p.base.binding(path) for path in paths},
        artifacts={str(path.relative_to(out)):p.base.binding(path) for path in artifacts})
    p.base.save(out/'build.json',result);print('BUILT RAM-only preflight',len(body),'bytes; no flash install required',flush=True);return result


def verify(out):
    out=Path(out).resolve();info=p.base.read(out/'build.json');p.verify(info['provider_build'])
    for path,value in info['inputs'].items():assert p.base.digest(path)==value['sha256']
    for path,value in info['artifacts'].items():assert p.base.digest(out/path)==value['sha256']
    assert crc((out/'payload'/BIN).read_bytes())==0
    return info


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('command',choices=('build','verify'));parser.add_argument('--build',type=Path);parser.add_argument('--out',type=Path,required=True)
    args=parser.parse_args();build(args.build,args.out) if args.command=='build' else verify(args.out)
