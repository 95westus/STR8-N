"""Offline b12: remove recovery D/V; keep shared PR04 entry addresses fixed."""
import argparse,json,re,sys
from pathlib import Path
import build_b11 as previous
HERE=previous.HERE;ROOT=previous.ROOT
HELP=b'L=RLP1 R=run\r\nA/B=MON 0-3=bank C1=USB/2=ACIA/3=both\r\n'
RECOVERY='Recovery L/R A/B 0-3 C1/2/3 ?'
SPARES={}

def pad(label,count,byte='$FF'):
    assert count>=0
    SPARES[label]=count
    return label+':\n'+('        DB '+','.join([byte]*count)+'\n' if count else '')

def b12_source(source):
    source=previous.b11_source(source)
    # Keep all shared entries at their b11 addresses. Reuse the eliminated
    # 98-byte binary-output region for 94 bytes formerly appended at F's end.
    tail=source[source.index('BOOT_CONSUMING:'):]
    source=source[:source.index('BOOT_CONSUMING:')]
    a,b=source.index('RL_DUMP:'),source.index('BOOT_READ_RECORD:')
    source=source[:a]+tail+pad('B12_FREE_OUTPUT',4)+source[b:]
    a,b=source.index("        CMP #'D'",source.index('BOOT_MENU:')),source.index("        CMP #'A'",source.index('BOOT_MENU:'))
    source=source[:a]+pad('B12_FREE_DISPATCH',14,'$EA')+source[b:]
    a,b=source.index('DC_BINARY_TX_BAD:'),source.index('B11_NO_IMAGE:')
    source=source[:a]+pad('B12_FREE_TX_ERROR',32)+source[b:]
    # Retain the two existing help-string allocations; expose shorter text's
    # spare bytes as an explicit reusable hole rather than moving the writer.
    for label,body,capacity in [('B11_HELP_TEXT',HELP[:30],31),('B11_HELP_TAIL',HELP[30:],45)]:
        pattern=label+r': DB [0-9,]+\n'
        replacement=label+': DB '+','.join(str(x) for x in body+b'\0')+'\n'
        replacement+=pad('B12_FREE_'+label,capacity-len(body)-1)
        source,n=re.subn(pattern,lambda _:replacement,source);assert n==1,label
    old='Recovery L/R/D/V A/B 0-3 C1/2/3'
    marker='BR_RECOVERY: DB "'+old+'",13,10,0'
    assert source.count(marker)==1
    source=source.replace(marker,'BR_RECOVERY: DB "'+RECOVERY+'",13,10,0\n'+pad('B12_FREE_BANNER',len(old)-len(RECOVERY)))
    old='LOADED; R runs, V reads back';new='LOADED; R runs'
    source=source.replace('RL_OK: DB "'+old+'",13,10,0','RL_OK: DB "'+new+'",13,10,0\n'+pad('B12_FREE_LOADED',len(old)-len(new)))
    marker='        DB $EA,$EA,$EA,$EA,$EA,$EA,$EA\nRL_GET:'
    assert source.count(marker)==1
    source=source.replace(marker,pad('B12_EXISTING_MENU_PAD',7,'$EA')+'RL_GET:')
    source=source.replace('B11_HELP','B12_HELP').replace('B11_NO_IMAGE','B12_NO_IMAGE')
    assert all(label+':' not in source for label in ('RL_DUMP','RL_VERIFY','RL_OUTPUT','DC_BINARY_TX_BAD'))
    return source

def main():
    # The b11 builder is frozen. Its base build is reused with b12 source,
    # banner and generation, then its obsolete D/V report field is replaced.
    source=Path(previous.__file__).read_text()
    source=source[source.index('def main():'):source.index("if __name__=='__main__':")]
    source=source.replace('0x8000000B','0x8000000C').replace('2.0proto b11','2.0proto b12')
    source=source.replace('b11_source','b12_source')
    namespace=dict(__file__=__file__,HERE=HERE,ROOT=ROOT,Path=Path,argparse=argparse,json=json,sys=sys,HELP=HELP,b12_source=b12_source)
    exec(compile(source,str(Path(previous.__file__)),'exec'),namespace);namespace['main']()
    out=Path(sys.argv[sys.argv.index('--out')+1]);path=out/'prototype-report.json';report=json.loads(path.read_bytes())
    report.pop('b11_recovery_patch')
    old=json.loads((ROOT/'BUILD/pr04-b11-help-r7/symbols.json').read_bytes());new=json.loads((out/'symbols.json').read_bytes())
    exceptions={'BOOT_END','_END_CODE','BOOT_CONSUMING','B07_PRINT_CHOICES','B07_PREFIX','B07_CHOICES','B08_RECOVERY_LINE','B08_BANK_LINE','B10_WAIT_FIRST','B10_CANCEL_FIRST'}
    for module,labels in old.items():
        for label,address in labels.items():
            if label in exceptions:continue
            if module=='core/str8n-v2-boot' and (label in exceptions or label.startswith(('B11_','P_LONG_34','P_LONG_35','P_LONG_68','P_LONG_69','P_LONG_70','P_LONG_71','P_LONG_72','P_LONG_73','RL_DUMP','RL_VERIFY','RL_OUTPUT','RL_OUT_BYTE','DC_BINARY_TX_BAD','DC_TX_ERROR'))):continue
            assert new[module].get(label)==address,(module,label)
    for name in ('ram-config-offline.bin','ram-installer-offline.bin','ram-installer-offline.rlp1'):
        assert (out/'payload'/name).read_bytes()==(ROOT/'BUILD/pr04-b11-help-r7/payload'/name).read_bytes(),name
    report['b12_recovery_patch']=dict(removed_commands=['D','V'],help=HELP.decode(),recovery_banner=RECOVERY,
        recovery_RAM_may_be_overwritten=True,RLP1_CRC_and_range_validation_retained=True,
        removed_output_region_bytes=98,relocated_tail_bytes=94,shared_PR04_entry_addresses_unchanged=True,
        standalone_RAM_tools_byte_identical_to_b11=True,internal_spare_regions={k.replace('B11_HELP','B12_HELP'):v for k,v in SPARES.items()},
        internal_spare_bytes=sum(SPARES.values()),contiguous_F_free_bytes=report['f']['free'],
        total_spare_bytes=report['f']['free']+sum(SPARES.values()),newly_reclaimed_bytes=181,
        prior_free_bytes_including_known_padding=8,hardware_flashed=False)
    report['new_f_features']=[x for x in report['new_f_features'] if x!='RAM readback and escrow']
    path.write_text(json.dumps(report,indent=2)+'\n')
    print('PASS b12 F budget:',report['f'],'internal spare',sum(SPARES.values()),flush=True)

if __name__=='__main__':main()
