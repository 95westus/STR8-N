"""Offline-only b15 RAM CONFIG build bound to 2609's verified VX1 checkpoint."""
import argparse,json,shutil,sys
from pathlib import Path
HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
sys.path[:0]=[str(ROOT/'tools'),str(HERE)]
from build import long_branches
from str8build.assemble import Assembly
from str8build.formats import save,sha
from deployment_plan import snbt_records
from wdc_b15_2609 import TARGET,GENERATION,WDC_SHA
from prepare_monitor_size import ATTEMPTS

SESSION=ROOT/'output/qualification/2609-b15-onboarding-20261027T212009Z'
BIN='2609-CONFIG-RAM.bin'
F_SHA='1a1db354d49d8a9a555be1100b74f3e4b0ed14d3156f3a333086853a845717b8'


def read(path):return json.loads(Path(path).read_text())
def digest(path):return sha(Path(path).read_bytes())
def binding(path):return dict(bytes=Path(path).stat().st_size,sha256=digest(path))


def baseline():
    state=read(SESSION/'session.json');run=SESSION/'step09-VERSION-install'
    report=read(run/'report.json');audit=read(run/'audit.json');wear_path=Path(state['wear_history']);wear=read(wear_path)
    assert state['board']=='2609' and state['VERSION_CAPS_installed'] and not state['configuration_changed']
    assert report['passed'] and report['final_REC_verified'] and report['post_final_REC_commands']==0 and report['port_released']
    assert audit['passed'] and audit['report_sha256']==wear['execution_report_sha256']==digest(run/'report.json')
    banks=[]
    for bank in range(4):
        a=run/f'after-r1-b{bank}.bin';b=run/f'after-r2-b{bank}.bin'
        assert a.read_bytes()==b.read_bytes();banks.append(a.read_bytes())
    assert list(map(sha,banks))==report['expected_sha256'] and sha(banks[0])==WDC_SHA
    assert sha(banks[3][-4096:])==digest(TARGET/'payload/f-offline-component.bin')==F_SHA
    records=snbt_records(banks);seq,offset,row=max(records,key=lambda r:r[0])
    counts=[int.from_bytes(row[64+3*n:67+3*n],'little') for n in range(32)]
    assert seq==wear['sequence']==1020 and row[7]==ord('S') and row[13]==0
    assert counts==wear['counts'] and row[32:48].hex()==wear['config'] and row[160:164]==b'\xff'*4
    assert int.from_bytes(row[18:22],'little')==GENERATION and row[14:18]==b'\x08'*4
    paths=[run/'report.json',run/'audit.json',wear_path,*run.glob('after-r*-b?.bin'),
           TARGET/'symbols.json',TARGET/'prototype-report.json',TARGET/'payload/f-offline-component.bin',
           HERE/'ram-config-b15.asm',Path(__file__),HERE/'build.py']
    paths.extend(TARGET.glob('s/**/*.inc'))
    return banks,dict(board='2609',source_run=str(run),bank_sha256=list(map(sha,banks)),
        counts=counts,sequence=seq,config=wear['config'],history_unknown_mask='ffffffff',
        default='S',enabled_banks=0,entries=['8000']*4,F_sha256=F_SHA,B0_sha256=WDC_SHA,
        semantics=wear['semantics']),{str(p.resolve()):binding(p) for p in paths if p.is_file()}


def build(out):
    out=Path(out).resolve();assert out.is_relative_to(ROOT/'output/qualification') and not out.exists(),'Fresh private output required'
    banks,base,inputs=baseline()
    report=read(TARGET/'prototype-report.json');assert report['banner']=='2.0proto b15' and report['journal_duplicate_guard']
    out.mkdir(parents=True);(out/'.gitignore').write_text('*\n')
    shutil.copytree(TARGET/'s',out/'s');(out/'payload').mkdir()
    engine=(TARGET/'s/core/prototype-engine.inc').read_text()
    old='        CMP #3\n        BEQ JE_PROMOTE\n        LDA JE_REQUEST\n'
    assert engine.count(old)==1 and 'JSR JE_CHECK_DUPLICATES' in engine
    engine=engine.replace(old,'        CMP #3\n        BEQ JE_PROMOTE\n'
        '        CMP #6\n        BNE CONFIG_NOT_BANK\n        JMP CONFIG_BANK_APPLY\nCONFIG_NOT_BANK:\n'
        '        LDA JE_REQUEST\n',1)
    core=out/'s/core'
    (core/'config-engine.inc').write_text(long_branches(engine).replace('P_LONG_','CE_LONG_'))
    (core/'ram-config.asm').write_text(long_branches((HERE/'ram-config-b15.asm').read_text()).replace('P_LONG_','CF_LONG_'))
    a=object.__new__(Assembly);a.out=out;a.assembler=shutil.which('wdc02as');a.linker=shutil.which('wdcln')
    assert a.assembler and a.linker
    a.compiled=[];a.symbols=read(TARGET/'symbols.json')
    body,sy=a.link('core','ram-config',0x200,'CONFIG_END')
    assert sy['CONFIG_START']==0x200 and sy['CONFIG_END']==0x200+len(body)<=0x6500
    a.emit(BIN,body);a.emit('ram-config-offline.bin',body)
    a.emit('f-offline-component.bin',banks[3][-4096:])
    save(out/'symbols.json',a.symbols)
    report['config']=dict(start=0x200,end=sy['CONFIG_END'],bytes=len(body),writer_start=sy['JE_ENTER'],writer_bytes=sy['JE_END']-sy['JE_ENTER'])
    save(out/'prototype-report.json',report);save(out/'baseline.json',base)
    for n,data in enumerate(banks):(out/f'source-b{n}.bin').write_bytes(data)
    artifacts=[*list((out/'payload').glob('*.bin')),out/'symbols.json',out/'prototype-report.json',out/'baseline.json',*out.glob('source-b?.bin'),core/'ram-config.asm',core/'config-engine.inc']
    result=dict(passed=True,hardware=False,board_access=False,serial_access=False,flashed=False,
        saved_setting_writes=False,board='2609',BIN=BIN,app_bytes=len(body),app_sha256=sha(body),
        load_address='0200',end_exclusive=f'{sy["CONFIG_END"]:04X}',remaining_application_bytes=0x6500-sy['CONFIG_END'],
        source_build=str(TARGET),F_sha256=F_SHA,generation='8000000F',baseline=base,inputs=inputs,
        artifacts={str(p.relative_to(out)):binding(p) for p in artifacts},
        commands=['?','B','C','W','Q','B bank entry (writes)','C target (writes)','I (blank only; writes)'],
        inspection_sequence=['C1<Enter>','L<Enter>','SEND exact RAM BIN after SEND BIN','?<Enter>','B<Enter>','C<Enter>','W<Enter>','Q<Enter>'],
        journal_format_unchanged=True,frozen_engine_sha256=digest(TARGET/'s/core/prototype-engine.inc'),
        limitations=['Requires exact matching b15 F/RAM services; not a universal loader',
                      'Settings commands take effect immediately; no draft or Save menu',
                      'Preparation only; no RAM upload, flash or saved-setting write',
                      'ACIA model coverage does not establish board qualification'])
    assert not ATTEMPTS
    save(out/'ram-config-build.json',result)
    return result


def verify(out):
    out=Path(out).resolve();info=read(out/'ram-config-build.json')
    for name,value in info['inputs'].items():assert digest(name)==value['sha256'],'Changed input '+name
    for name,value in info['artifacts'].items():assert digest(out/name)==value['sha256'],'Changed artifact '+name
    assert digest(out/'payload'/BIN)==info['app_sha256'] and info['F_sha256']==F_SHA
    return info


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('command',choices=['prepare','verify']);parser.add_argument('--out',type=Path,required=True)
    args=parser.parse_args();result=build(args.out) if args.command=='prepare' else verify(args.out)
    print(json.dumps({k:result[k] for k in ('passed','BIN','app_bytes','app_sha256','F_sha256','saved_setting_writes')},indent=2),flush=True)
