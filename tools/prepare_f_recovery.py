"""Build the isolated F-size candidate with recovery status initialization.

Use two existing padding bytes before BOOT_UPDATE_WRITE; never change the
selected source, A/B, CRC implementation, fixed entries, or available space.
"""
import argparse,difflib,shutil
from pathlib import Path
from prepare_f_size import prepare,read,offline,protected,emitter
from str8build.assemble import Assembly
from str8build.formats import save,sha
from str8build.images import boot_sector
ROOT=Path(__file__).resolve().parents[1]
SIZE_SHA='d075fb59a13a2399e67cd2dc1ace7bd820f85c969c861db00fd2cdb92f7b27f2'

def build(control,out):
    control,out=control.resolve(),out.resolve();snapshot=protected()
    prepare(control,out)
    original_image=(out/'firmware.bin').read_bytes();assert sha(original_image)==SIZE_SHA
    original_report=read(out/'f-size-build.json');original_symbols=read(out/'symbols.json')
    save(out/'size-only-build.json',original_report)
    (out/'size-only-firmware.bin').write_bytes(original_image)
    shutil.copyfile(out/'source.patch',out/'size-only-source.patch')
    a=object.__new__(Assembly);a.out=out;a.assembler=shutil.which('wdc02as');a.linker=shutil.which('wdcln');a.symbols={};a.compiled=[]
    before=emitter(a,'f-recovery-before')
    path=out/'s/core/str8n-v2-boot.asm';text=path.read_text()
    old='                        JSR BOOT_UPDATE_WRITE\n'+'                        NOP\n'*6
    new=('; Clear inherited status only after upload validation, before this attempt.\n'
         '                        STZ V2_FLASH_ERROR\n                        JSR BOOT_UPDATE_WRITE\n'+'                        NOP\n'*4)
    assert text.count(old)==1;path.write_text(text.replace(old,new))
    body,sy=a.link('core','str8n-v2-boot',0xf000,'BOOT_END')
    assert sy==original_symbols['core/str8n-v2-boot'],'No labels or entries may move'
    fixed=boot_sector(body,sy,original_symbols['core/str8n-v2-vectors'],read(ROOT/'src/current/layout.json')['boot_compatibility'])
    image=original_image[:-4096]+fixed
    # One nine-byte call/padding window changes. Its final four NOPs and every
    # byte outside the initial five-byte STZ+JSR sequence remain identical.
    pc=0xf57d;off=pc-0xf000;oldfixed=original_image[-4096:]
    assert oldfixed[off:off+9]==bytes.fromhex('205CFB')+b'\xea'*6
    assert fixed[off:off+9]==bytes.fromhex('64F6205CFB')+b'\xea'*4
    assert fixed[:off]==oldfixed[:off] and fixed[off+5:]==oldfixed[off+5:]
    assert fixed[0xab4:0xae7]==oldfixed[0xab4:0xae7]
    assert fixed[0xb93:0xf14]==oldfixed[0xb93:0xf14] and fixed[0xfe0:]==oldfixed[0xfe0:]
    after=emitter(a,'f-recovery-after');assert before[1]==after[1] and after[0]==body
    assert before[0][:off]==body[:off] and before[0][off+5:]==body[off+5:]
    before_rows=before[2];after_rows=after[2]
    assert before_rows[pc]['source']=='JSR BOOT_UPDATE_WRITE'
    assert after_rows[pc]['source']=='STZ V2_FLASH_ERROR' and after_rows[pc+2]['source']=='JSR BOOT_UPDATE_WRITE'
    a.emit('str8n-v2-recovery-f000-ffff.bin',fixed);(out/'firmware.bin').write_bytes(image)
    symbols=original_symbols;symbols['core/str8n-v2-boot']=sy;save(out/'symbols.json',symbols)
    patch=''
    for name in ('str8n-v2-boot.asm','str8n-v2-journal.inc'):
        oldtext=(ROOT/'src/current/core'/name).read_text();newtext=(out/'s/core'/name).read_text()
        patch+=''.join(difflib.unified_diff(oldtext.splitlines(True),newtext.splitlines(True),fromfile='src/current/core/'+name,tofile='src/current/core/'+name))
    (out/'source.patch').write_text(patch)
    result=dict(original_report,candidate='fixed-f-size-recovery-status',firmware_sha256=sha(image),fixed_F_sha256=sha(fixed),recovery_status_fixed=True,
        recovery_fix=dict(entry=pc,status_address=0xf6,cleared_before_write=True,existing_padding_bytes_used=2,extra_bytes=0,
            original_window=(oldfixed[off:off+9]).hex(),fixed_window=(fixed[off:off+9]).hex(),changed_addresses=[0xf000+i for i,(x,y) in enumerate(zip(oldfixed,fixed)) if x!=y],
            independent_flattened_links_match=True,all_symbols_unchanged=True),
        size_only_firmware_sha256=SIZE_SHA,tool_sha256=sha(Path(__file__).read_bytes()),protected_snapshot=snapshot)
    assert result['contiguous_free_bytes']==204 and result['interior_free_bytes']==11
    save(out/'f-size-build.json',result)
    save(out/'build-report.json',dict(passed=True,candidate_only=True,candidate_id=result['candidate'],board_access=False,installation_permitted=False,
        firmware_sha256=sha(image),baseline_sha256=result['baseline_sha256'],source_patch_sha256=sha(patch.encode()),recovery_status_fixed=True))
    assert protected()==snapshot
    print('PASS recovery-status candidate; STZ before write; zero growth; unchanged symbols, A/B, CRC, worker and vectors',flush=True)
if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--control',type=Path,required=True);p.add_argument('--out',type=Path,required=True);args=p.parse_args()
    offline();build(args.control,args.out)
