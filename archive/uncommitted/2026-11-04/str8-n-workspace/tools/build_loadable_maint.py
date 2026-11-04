"""Package the accepted full BANK MAINT core as a standalone REC $0200 BIN.

Only the small RAM map/admission adapter is assembled. The accepted editor,
copy/compare, TABLE, naming, boot configuration and guarded writer are reused.
No MON UI vector, installed MAINT copy or SPI storage is required.
"""
import argparse,binascii,hashlib,json,re,shutil,struct,subprocess,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]; REPO=ROOT/'release/str8nf-v0.2.0'
sys.path.insert(0,str(REPO/'tools'))
from build import cells
sha=lambda b:hashlib.sha256(b).hexdigest()
def symbols(path):return {n:int(v,16) for v,n in re.findall(r'^\s*([0-9A-Fa-f]{8})\s+(\w+)\s*$',path.read_text(),re.M)}
def build(out):
 base=ROOT/'BUILD/native-apps-g1-maint-r1'; m=json.loads((base/'manifest.json').read_text())
 core=bytearray((base/'BANK-MAINT-g00000001-RAM.bin').read_bytes());assert sha(core)==m['artifacts']['BANK-MAINT-g00000001-RAM.bin']['sha256']
 f=(REPO/'firmware/payload/STR8N-F-BOOT-4096.bin').read_bytes();assert sha(f)=='8f4d35ac66730daa773515980983fcf442be3b1bdf1e523d3752ec3615657cc1'
 sy=symbols(base/'bank-maint.map');out.mkdir(parents=True,exist_ok=False)
 for path in base.glob('*.inc'):
  shutil.copyfile(path,out/path.name)
 ro=(REPO/'src/core/ram-maint-ro.asm').read_text()
 def part(a,b):return ro[ro.index(a):ro.index(b)]
 guard=part('MA_START:','        LDX #<MA_TITLE')
 guard=guard.replace('#<MA_START','#<$2000').replace('#>MA_START','#>$2000').replace('MA_IMM_END-MA_START','MA_IMM_END-$2000')
 code='''; Standalone REC RAM adapter; no MON call or cached UI dependency.
        MODULE MAINT_REC_ADAPTER
        INCLUDE "str8n-v2-eq.inc"
        INCLUDE "str8n-v2-public.inc"
        INCLUDE "worker-public-symbols.inc"
        INCLUDE "boot-symbols.inc"
        INCLUDE "maint-ro-params.inc"
MA_PTR EQU $E0
MA_BP EQU $E2
        CODE
'''+guard+'''        RTS
MA_GUARD_BAD:
        ; ABI mismatch: do not call an unadmitted firmware vector.
        SEI
        BRA MA_GUARD_BAD
MA_SERVICE:
        LDA $63E0
        CMP #'W'
        BNE MA_SERVICE_M
        LDA #3
        BRA MA_SERVICE_GO
MA_SERVICE_M:
        LDA $63E1
        AND #$0F
MA_SERVICE_GO:
        STA MA_VIEW
        JSR MA_MAP_READY
        LDA #3
        JMP V2W_SELECT
'''
 code+=part('MA_HOME:','MA_READ:')
 code+=part('MA_RAW_CRC:','MA_MAP:')
 maps=part('MA_MAP_READY:','MA_SPACE:').replace('JMP MA_MENU','RTS').replace('JMP MA_MESSAGE','JMP MA_PRINT')
 code+=maps+part('MA_SPACE:','MA_TITLE:')
 code+=part('MA_GRID_TITLE:','MA_GUARD_TABLE:')
 code+='MA_GUARD_TABLE:\n        INCLUDE "maint-ro-ram-guards.inc"\nMA_IMAGE_CRC: DW 0\nMA_IMM_END:\n'
 code+=part('MA_STATE_BEGIN:','MA_END:')+'MA_END:\n        ENDMOD\n        END\n'
 (out/'maint-adapter.asm').write_text(code)
 # Fixed-size patches are checked against the accepted core before replacement.
 patches=[]
 def patch(at,before,after,label):
  assert len(before)==len(after) and core[at-0x2000:at-0x2000+len(before)]==before,label
  core[at-0x2000:at-0x2000+len(after)]=after;patches.append(dict(address=f'{at:04X}',purpose=label,before=before.hex(),after=after.hex()))
 patch(sy['MB_VERSION_CALL'],bytes.fromhex('6CF266'),bytes.fromhex('60EAEA'),'VERSION prints local tool identity')
 start=sy['MM_BM_QUIT'];at=core.index(bytes.fromhex('4C0066'),start-0x2000)+0x2000
 patch(at,bytes.fromhex('4C0066'),bytes.fromhex('4C647E'),'Q uses public Foundation reset')
 patch(sy['MB_FOUNDATION'],bytes.fromhex('4C04F0'),bytes.fromhex('4C647E'),'J3 uses public Foundation reset')
 def text(old,new):
  before=old.encode();assert len(new)<=len(old);at=core.index(before)+0x2000;patch(at,before,new.ljust(len(old)).encode(),'REC help/identity')
 text('STR8-N BANK MAINT 2.4 / BASE1 PR05 g1','STR8-N BANK MAINT 2.4 / REC 0200 r1')
 text('Q Return to monitor','Q Restart Foundation') if len('Q Restart Foundation')<=len('Q Return to monitor') else text('Q Return to monitor','Q Restart F')
 # A map adapter supersedes the private MON dispatcher call; all maps execute
 # in this packet and preserve the editor buffer at $5000-$5FFF.
 asm=shutil.which('wdc02as');link=shutil.which('wdcln');assert asm and link
 logs=[]
 for command in ([asm,'-G','-L','-S','-W','maint-adapter.asm'],[link,'-g','-s','-t','-c4300','-hm19','-j','-o','maint-adapter.s19','maint-adapter.obj']):
  p=subprocess.run(command,cwd=out,capture_output=True,text=True);logs.append(dict(command=command,returncode=p.returncode,stdout=p.stdout,stderr=p.stderr));(out/'build-log.json').write_text(json.dumps(logs,indent=2));assert p.returncode==0,p.stdout+p.stderr
 hs=symbols(out/'maint-adapter.map');assert hs['MA_END']<=0x5000,f"Map adapter overlaps editor: {hs['MA_END']:04X}"
 dispatch=core.index(bytes.fromhex('2008E0'))+0x2000
 patch(dispatch,bytes.fromhex('2008E0'),b'\x20'+struct.pack('<H',hs['MA_SERVICE']),'M1/M2/M3 use included RAM map adapter')
 mem=cells(out/'maint-adapter.s19');adapter=bytes(mem[a] for a in range(0x4300,hs['MA_END']))
 packet=bytearray(b'\xff'*(hs['MA_END']-0x200));packet[0x1e00:0x1e00+len(core)]=core;packet[0x4100:]=adapter
 # Enter through RA admission first; initialize only this utility's own state.
 magic=int(re.search(r'BQ_MAGIC\s+EQU\s+\$([0-9A-F]+)',(base/'batch-interface.inc').read_text())[1],16)
 stub=bytes.fromhex('78D8A2FF9A9CF97D9C005D')+b'\x9C'+struct.pack('<H',magic)+bytes.fromhex('A9038D007D')
 stub+=b'\x20'+struct.pack('<H',hs['MA_START'])+bytes.fromhex('A26F4C')+struct.pack('<H',sy['MB_ZERO'])
 packet[:len(stub)]=stub
 seal=hs['MA_IMAGE_CRC']-0x200;packet[seal:seal+2]=binascii.crc_hqx(packet[0x1e00:seal],65535).to_bytes(2,'big')
 assert binascii.crc_hqx(packet[0x1e00:hs['MA_IMM_END']-0x200],65535)==0
 (out/'MAINT.bin').write_bytes(packet)
 report=dict(load='0200',entry='0200',end=f"{hs['MA_END']-1:04X}",bytes=len(packet),sha256=sha(packet),F_sha256=sha(f),F_built=False,MON_required=False,stored_MAINT_required=False,SPI_SRAM_required=False,core_sha256=m['artifacts']['BANK-MAINT-g00000001-RAM.bin']['sha256'],adapter_builds=1,CPU_simulations=0,patches=patches,editor='5000-5FFF',state='6000-63FF',sector_staging='6800-77FF',RAM_copy_workspace='0200-1FFF',protected_flash='B1:8-A, B2, B3 (including golden F and C/D)',qualification='NOT_YET_RUN')
 (out/'manifest.json').write_text(json.dumps(report,indent=2)+'\n')
 (out/'README.txt').write_text(README)
 print(json.dumps(report,indent=2))
README='''STR8-N BANK MAINT 2.4 / REC $0200

In the Python serial console, use F2 to choose MAINT.bin, then F4 at REC>.
Alternatively enter L at REC>, then F3 once SEND BIN appears. The file loads
and starts at $0200. Do not send it as S19 or as an AP/02 image. No stored
MAINT app, MON UI or SPI SRAM is needed.

Commands (all numbers hexadecimal):
  ? / VERSION              Menu / this tool's identity
  M1 / M2 / M3             Grid / ranges / tracked wear
  TABLE [bank|first-last]  Stored flash catalogue; T is the short form
  NAME [name|CLEAR]        Board name; changes require YES
  BOOT                    Inspect boot policy
  BOOT B bank addr        Enable an opaque bank and set its entry
  BOOT C bank|A|B|S        Save the default boot selection
  E bank sector[-sector]  Erase; Y confirmation
  C src range dst start   Copy RAM/flash; Y confirmation
  V src range dst start   Compare RAM/flash
  R src range             Read up to 4096 bytes into the editor
  D [offset[-end]]         Display editor bytes
  P offset byte ...       Patch editor bytes
  F offset[-end] byte     Fill editor bytes
  N length byte           New filled editor buffer
  K                       Editor CRC16-CCITT-FALSE
  W dst start             Write editor and verify; Y confirmation
  J bank                  Boot an enabled bank; J3 restarts Foundation
  Q                       Restart Foundation using saved boot policy

src/dst are R (RAM) or flash bank 0-3. Flash sectors are 8-F.
Example using only the editor and RAM:
  N 1000 FF
  P 0 12 34 56
  F 10-1F A5
  D 0-1F
  K
  W R 1000
  Y
  V R 1000-100F R 1000

RAM copy workspace: $0200-$1FFF; code ends below $5000; editor $5000-$5FFF;
state $6000-$63FF; journal frame $6700; flash staging $6800-$77FF.
This utility borrows application RAM/ZP. Normal use does not restore its old
contents. The host qualification restores them from an independent escrow.

Raw writes protect B1:8-A, all B2 and all B3, including C/D and golden F.
NAME requires YES. BOOT with arguments writes settings immediately; BOOT
without arguments only inspects them. BOOT ? shows the CONFIG commands.
Exact frozen Foundation BASE1/PR05 F and RAM worker are admitted before use;
the immutable RAM tool also checks its CRC. No F rebuild or write is needed.

Q restarts Foundation: choose S at its chooser for REC>, or let the saved
default boot. It does not change the saved default.
'''
if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--out',type=Path,required=True);build(p.parse_args().out.resolve())
