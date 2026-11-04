"""Build only the RAM SRAM/WORK candidate; frozen F and other modules reused."""
import argparse,binascii,hashlib,json,re,shutil,subprocess
from pathlib import Path
from build import cells
from build_native_apps import normalized
from mona_branches import conservative_branches
ROOT=Path(__file__).resolve().parents[1]
sha=lambda b:hashlib.sha256(b).hexdigest()

def build(out,generation=2):
    out=Path(out).resolve()
    if out.exists():raise ValueError('Fresh output directory required')
    freeze=json.loads((ROOT/'F_FREEZE.json').read_text())
    f=(ROOT/'firmware/payload/STR8N-F-BOOT-4096.bin').read_bytes()
    assert len(f)==4096 and sha(f)==freeze['sha256']
    assert all(sha((ROOT/n).read_bytes())==h for n,h in freeze['sources'].items())
    assembler,linker=shutil.which('wdc02as'),shutil.which('wdcln')
    assert assembler and linker
    out.mkdir(parents=True)
    inputs={}
    names=['monitors/native/sram-work.asm','monitors/native/sram-work-classic.inc',
      'monitors/native/sram-work-spi.inc','monitors/src/program-spi.inc',
      'monitors/src/workbench-monitor-ui.inc','monitors/src/monitor-ui.inc',
      'monitors/src/batch-interface.inc','src/include/str8n-v2-public.inc',
      'src/core/worker-public-symbols.inc','monitors/reference/sram-work-b35.inc']
    for n in names:
        p=ROOT/n;inputs[n]=sha(p.read_bytes());(out/p.name).write_bytes(p.read_bytes())
    from port_sram_work import generate
    generate(out/'sram-work-classic.inc')
    spi=(out/'program-spi.inc').read_text()
    spi=spi[:spi.index('SP_READ64:')]+spi[spi.index('SP_TRANSFER:'):]
    spi=spi.replace('SP_TRANSFER:\n','SP_TRANSFER:\n        LDA SP_OP\n        BEQ SP_BEGIN\n',1)
    a,b=spi.index('SP_OP_CHECK:'),spi.index('SP_BEGIN:')
    spi=spi[:a]+'''SP_OP_CHECK:
        LDA SP_OP
        CMP #1
        BEQ SP_BEGIN
        CMP #2
        BNE SP_BAD_RANGE
'''+spi[b:]
    spi=spi.replace('SP_MODE_OK:\n','SP_MODE_OK:\n        LDA SP_TEMP\n        STA SW_MODE\n        LDA SP_OP\n        BEQ SP_QUERY_DONE\n',1)
    spi=spi.replace('SP_MODE_BAD:\n','SP_QUERY_DONE:\n        STZ SP_ERROR\n        JMP SP_RESTORE\nSP_MODE_BAD:\n',1)
    (out/'sram-work-spi-engine.inc').write_text(spi)
    ui=(out/'workbench-monitor-ui.inc').read_text()
    ui=ui[ui.index('W_UI_EXPECTED EQU'):ui.index('W_UI_ERROR:')]
    a,b=ui.index('W_UI_CALL:'),ui.index('W_UI_CHECK:');ui=ui[:a]+ui[b:]
    ui=re.sub(r'EQU \$663([0-8])',r'EQU $5B1\1',ui)
    ui+='''
W_PTR EQU $E0
W_CRC EQU $5B00
W_CRC_START:
        LDA #$FF
        STA W_CRC
        STA W_CRC+1
        RTS
W_CRC_BYTE:
        EOR W_CRC+1
        STA W_CRC+1
        PHX
        LDX #8
SW_CRC_BIT:
        ASL W_CRC
        ROL W_CRC+1
        BCC SW_CRC_NEXT
        LDA W_CRC
        EOR #$21
        STA W_CRC
        LDA W_CRC+1
        EOR #$10
        STA W_CRC+1
SW_CRC_NEXT:
        DEX
        BNE SW_CRC_BIT
        PLX
        RTS
W_UI_MI_MAGIC: DB "MI",1,0,3,1,0,0
W_UI_MAGIC: DB "UI",1,MU_VECTOR_COUNT,"PR05"
'''
    (out/'sram-work-ui.inc').write_text(ui)
    def flatten(name,seen=()):
        assert name not in seen
        text=(out/name).read_text(encoding='utf-8-sig')
        # Constants stay includes; all executable code shares one sizing block.
        return re.sub(r'^\s*INCLUDE "(sram-work-[^"]+\.inc)"\s*$',
            lambda m:flatten(m[1],(*seen,name)),text,flags=re.M)
    source=normalized(flatten('sram-work.asm')).replace('SW_GENERATION_TEXT',f'{generation:08X}')
    # WDC must know zero-page widths on pass1; late forward EQU symbols
    # otherwise change absolute instructions to zero-page on pass2.
    constants=re.findall(r'^\s*\w+\s+EQU\s+[^\n]+$',source,re.M)
    source=re.sub(r'^\s*\w+\s+EQU\s+[^\n]+\n','',source,flags=re.M)
    source=source.replace('        CODE\n','\n'.join(constants)+'\n        CODE\n',1)
    source,branches=conservative_branches(source,'SW_LONG_')
    (out/'sram-work.asm').write_text(source,encoding='utf-8',newline='\n')
    # Essential pre-link bounds/reference audit, not a CPU model/group suite.
    assert 'JSR $66A6' not in source and '$7D04' not in source
    logs=[]
    for cmd in ([assembler,'-G','-L','-S','-W','sram-work.asm'],
                [linker,'-g','-s','-t','-c2000','-hm19','-j','-o','sram-work.s19','sram-work.obj']):
        p=subprocess.run(cmd,cwd=out,capture_output=True,text=True)
        logs.append(dict(command=cmd,returncode=p.returncode,stdout=p.stdout,stderr=p.stderr))
        (out/'build-log.json').write_text(json.dumps(logs,indent=2)+'\n')
        if p.returncode:raise RuntimeError('Build failed: '+str(out/'build-log.json'))
    sy={n:int(v,16) for v,n in re.findall(r'^\s*([0-9A-Fa-f]{8})\s+(\w+)\s*$',(out/'sram-work.map').read_text(),re.M)}
    mem=cells(out/'sram-work.s19');assert set(mem)==set(range(0x2000,sy['SW_CODE_END']))
    body=bytes(mem[a] for a in range(0x2000,sy['SW_CODE_END']))
    assert sy['SW_CODE_END']<=0x5B00,'Code overlaps context; layout revision required'
    # Escrow RAM/ZP before this app uses legacy D0-D7 or6A scratch.
    prefix=bytes.fromhex('78 D8 A2 00 BD 00 00 9D 00 5C BD 00 6A 9D 00 5D E8 D0 F1 A9 FF 8D 02 5B 4C 00 20')
    packet=prefix.ljust(0x1E00,b'\xff')+body
    artifacts={}
    header=bytearray(b'\xFF'*32);header[:8]=b'RP\x01\x03PR05'
    header[8:10]=len(body).to_bytes(2,'little');header[10:14]=bytes.fromhex('00 20 00 20')
    header[14:18]=generation.to_bytes(4,'little')
    packed=(bytes(header)+body).ljust(12286,b'\xFF');assert len(packed)==12286
    packed+=binascii.crc_hqx(packed,65535).to_bytes(2,'big')
    for n,b in [(f'STR8N-SRAM-WORK-g{generation:08X}-RAM.bin',packet),('SRAM-WORK-library-2000.bin',body),
                (f'STR8N-STORAGE-g{generation:08X}-flash.bin',packed)]:
        (out/n).write_bytes(b);artifacts[n]=dict(bytes=len(b),sha256=sha(b))
    report=dict(status='BUILD_ONLY_NOT_EXECUTION_QUALIFIED',generation=f'{generation:08X}',F_sha256=freeze['sha256'],F_rebuilt=False,
      flash_writes=0,hardware_access=False,CPU_simulations=0,build_passes=1,assembler_linker_invocations=len(logs),
      source_sha256=inputs,artifacts=artifacts,linked_end=f'{sy["SW_CODE_END"]:04X}',linked_bytes=len(body),
      free_before_context=0x5B00-sy['SW_CODE_END'],entries={n:f'{sy[n]:04X}' for n in ('SW_START','SW_SRAM_API','SM_C_API','WK_API','SM_ENTRY','WK_ENTRY','SW_TRANSFER','SW_RETURN')},
      RAM=dict(code='2000-'+f'{sy["SW_CODE_END"]-1:04X}',context='5B00-5DFF',user_requests_data='0200-1FFF',scratch='6400-6ACF'),
      transport='EDU RevD, addressed bytes in00/40/80 modes; READ/RDMR; explicit volatile UNLOCK required for WRITE; no WRMR',
      WORK_session='A new manager instance starts an explicit lazy WORK epoch on its first mutating service; query does not start an epoch.',
      limits=['RAM overlay restricts actual CPU save/restore and request buffers to0200-1FFF; mount still inspects large legacy records.',
      'Native payload/route candidate built; no installed route changed until a reviewed deployment.'],branches=branches)
    (out/'symbols.json').write_text(json.dumps(sy,indent=2)+'\n')
    (out/'manifest.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({k:report[k] for k in ('status','linked_bytes','linked_end','free_before_context','entries')},indent=2))
    return report

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--out',type=Path,required=True)
    p.add_argument('--generation',type=lambda x:int(x,0),default=2);a=p.parse_args();build(a.out,a.generation)
