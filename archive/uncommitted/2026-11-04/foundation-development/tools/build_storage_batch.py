"""Build only the SRAM/WORK BATCH increment; no F build or device access."""
import argparse, binascii, json, re, shutil, subprocess
from pathlib import Path
from build_mona import ROOT, cells, sha
from storage_compact import compact
from mona_branches import conservative_branches


def source(text):
    def once(old, new):
        nonlocal text
        assert text.count(old) == 1, old
        text = text.replace(old, new, 1)
    once('SM_C_LINE EQU $6AC0', 'SM_C_LINE EQU $5B40')
    once('WK_LINE EQU $69E0', 'WK_LINE EQU $5B40')
    a, b = text.index('B29_LINE_2:'), text.index('SW_MATCH:')
    text = text[:a] + (ROOT/'monitors/native/storage-batch.inc').read_text() + '\n' + text[b:]
    # Restore MON state belowD0; retain the live queue until Q changes provider.
    once('''        INX
        BNE SW_RESTORE_MON
        LDX #0
SW_RESTORE_ZP:''', '''        INX
        CPX #$D0
        BCC SW_RESTORE_MON
        LDA BQ_MAGIC
        CMP #BQ_ON
        BEQ SB_RETURN_BATCH
SB_RETURN_TAIL:
        LDA $5D00,X
        STA $6A00,X
        INX
        BNE SB_RETURN_TAIL
        BRA SB_RETURN_ZP
SB_RETURN_BATCH:
        LDA BQ_PARENT
        STA BQ_PROVIDER
SB_RETURN_ZP:
        LDX #0
SW_RESTORE_ZP:''')
    text = text.replace('00000003', '00000004')
    return text


def build(out):
    out=Path(out).resolve(); out.mkdir(exist_ok=False)
    baseline=ROOT.parent.parent/'BUILD/named-edu-g3-r8'
    freeze=json.loads((ROOT/'F_FREEZE.json').read_text())
    assert sha((ROOT/'firmware/payload/STR8N-F-BOOT-4096.bin').read_bytes()) == freeze['sha256']
    assert all(sha((ROOT/n).read_bytes()) == v for n,v in freeze['sources'].items())
    prior=(baseline/'SW/flat.asm').read_text()
    text,_=conservative_branches(source(prior), 'SB_LONG_')
    (out/'flat.asm').write_text(text)
    logs=[]
    for cmd in ([shutil.which('wdc02as'),'-G','-L','-S','-W','flat.asm'],
                [shutil.which('wdcln'),'-g','-s','-t','-c2000','-hm19','-j','-o','image.s19','flat.obj']):
        p=subprocess.run(cmd,cwd=out,capture_output=True,text=True)
        logs.append(dict(command=cmd,returncode=p.returncode,stdout=p.stdout,stderr=p.stderr))
        (out/'build-log.json').write_text(json.dumps(logs,indent=2)+'\n')
        if p.returncode: raise RuntimeError('Inspect '+str(out/'build-log.json'))
    sy={n:int(v,16) for v,n in re.findall(r'^\s*([0-9A-Fa-f]{8})\s+(\w+)\s*$',(out/'image.map').read_text(),re.M)}
    m=cells(out/'image.s19'); assert set(m)==set(range(0x2000,sy['SW_CODE_END']))
    body=bytes(m[a] for a in range(0x2000,sy['SW_CODE_END']))
    assert sy['SW_CODE_END'] < 0x5B00
    (out/'SRAM-WORK-BATCH-2000.bin').write_bytes(body)
    (out/'symbols.json').write_text(json.dumps(sy,indent=2)+'\n')
    report=dict(status='BUILT_NOT_EXECUTION_QUALIFIED',F_rebuilt=False,F_sha256=freeze['sha256'],
        CPU_simulations=0,raw_bytes=len(body),sha256=sha(body),expanded_end=f'{sy["SW_CODE_END"]:04X}',
        source_sha256=sha(prior.encode()),hooks_sha256=sha((ROOT/'monitors/native/storage-batch.inc').read_bytes()))
    (out/'manifest.json').write_text(json.dumps(report,indent=2)+'\n')
    return pack_existing(out)


def pack_existing(out):
    """Repack already linked bytes; never reassemble them or change the decoder."""
    out=Path(out);baseline=ROOT.parent.parent/'BUILD/named-edu-g3-r8'
    report=json.loads((out/'manifest.json').read_text())
    body=(out/'SRAM-WORK-BATCH-2000.bin').read_bytes();assert sha(body)==report['sha256']
    original=(baseline/'SRAM-WORK-X-flash.bin').read_bytes()
    kernel=(baseline/'COMPACT-DECODE-6800.bin').read_bytes()
    # Move the same decoder immediately after the107-byte bootstrap, reclaiming
    # its old alignment gap. Indexed copies support an unaligned ROM source.
    stub=bytearray(original[32:139]);assert stub[-9:]==bytes.fromhex('A9 1F 48 A9 FF 48 4C 00 68')
    kernel_start=0xB000+32+len(stub);start=kernel_start+len(kernel)
    for before,after in ((0xB100,kernel_start),(0xB200,kernel_start+256)):
        old=bytes((0xBD,before&255,before>>8));new=bytes((0xBD,after&255,after>>8))
        assert stub.count(old)==1;stub=stub.replace(old,new)
    old=bytes.fromhex('A9 22 8D E0 00 A9 B2 8D E1 00')
    new=bytes((0xA9,start&255,0x8D,0xE0,0,0xA9,start>>8,0x8D,0xE1,0))
    assert stub.count(old)==1;stub=stub.replace(old,new)
    packed=compact(body);end=start+len(packed);assert end<=0xD900
    a=bytearray(original);a[32:0x2900]=b'\xff'*(0x2900-32)
    a[32:32+len(stub)]=stub
    a[kernel_start-0xB000:start-0xB000]=kernel
    a[start-0xB000:end-0xB000]=packed
    for offset,value in ((8,end-0xB020),(18,end),(26,0x2000+len(body)),(28,binascii.crc_hqx(body,65535))):
        a[offset:offset+2]=value.to_bytes(2,'little')
    a[14:18]=(4).to_bytes(4,'little')
    a[22:26]=b'BQ\x01\x01'
    a[-2:]=binascii.crc_hqx(a[:-2],65535).to_bytes(2,'big')
    assert a[0x2900:-2]==original[0x2900:-2] and binascii.crc_hqx(a,65535)==0
    (out/'SRAM-WORK-BATCH-flash.bin').write_bytes(a)
    report.update(packed_bytes=len(packed),packed_end=f'{end:04X}',packed_start=f'{start:04X}',
        kernel_start=f'{kernel_start:04X}',helper_boundary='D900',free_before_helper=0xD900-end,
        fits_existing_flash=True,flash_image_emitted=True,flash_sha256=sha(a),decoder_changed=False)
    (out/'manifest.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report,indent=2))
    return report


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--out',type=Path,required=True)
    p.add_argument('--pack-existing',action='store_true');a=p.parse_args()
    (pack_existing if a.pack_existing else build)(a.out)
