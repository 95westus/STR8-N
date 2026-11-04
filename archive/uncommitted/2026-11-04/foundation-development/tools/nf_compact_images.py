"""Prepare the compact MON/ASM/DBG profile from private captures; no serial IO.

F and C/D are never sector payloads. Native wear reservations/peer rotation
are forecast from the supplied journal; the operator reviews the actual scope.
"""
import argparse,hashlib,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
for folder in (ROOT/'migration-host',ROOT/'foundation/migration-host'):
    sys.path.insert(0,str(folder))
from journal_rotation_plan import reserve
from native_journal_room import classify_journal,valid_snapshot
sha=lambda b:hashlib.sha256(b).hexdigest()

def prepare(root,captures,cpu,out,retire=False):
    root,out=Path(root).resolve(),Path(out).resolve()
    catalog=json.loads((root/'NATIVE-COMPONENTS.json').read_text())
    if catalog.get('schema')!=3 or cpu not in ('65c02','65c816e'):
        raise ValueError('Compact schema 3 and explicit --cpu 65c02|65c816e required')
    if set(captures)!=set(range(4)) or any(v is None for v in captures.values()):
        raise ValueError('All four --current-b0/b1/b2/b3 captures are required for occupied-image review')
    banks={b:Path(p).read_bytes() for b,p in captures.items()}
    if any(len(v)!=32768 for v in banks.values()):raise ValueError('Every bank capture must be exactly 32768 bytes')
    if sha(banks[3][-4096:])!=catalog['F_sha256']:raise ValueError('B3 capture does not contain frozen Foundation F')
    before=classify_journal(banks[3])
    if before['kind']!='valid-snbt':raise ValueError('Provision/inspect C/D first: an unambiguous valid SNBT journal is required')
    selected=list(catalog['targets'])+(list(catalog['retirement_targets']) if retire else [])
    prepared=[];seen=set();state=banks[3];ops=[]
    for item in selected:
        bank,address=item['bank'],int(item['address'],16)
        if bank not in range(4) or address not in range(0x8000,0x10000,4096) or (bank==3 and address in (0xc000,0xd000,0xf000)):
            raise ValueError('Protected/noncanonical sector in catalog')
        if (bank,address) in seen:raise ValueError('Duplicate sector in catalog')
        seen.add((bank,address));variant=item['variants'][cpu] if 'variants' in item else item
        member=(root/variant['file']).resolve()
        if not member.is_relative_to(root):raise ValueError('Catalog path escapes candidate')
        body=member.read_bytes()
        if sha(body)!=variant['sha256']:raise ValueError('Changed payload: '+variant['file'])
        if item.get('preserve_RTC_metadata'):
            if (bank,address,len(body))!=(3,0x9000,3072):raise ValueError('Invalid RTC code-prefix allocation')
            body+=banks[3][0x1c00:0x2000]
        if len(body)!=4096:raise ValueError('A prepared sector must be 4096 bytes')
        offset=address-0x8000;old=banks[bank][offset:offset+4096]
        change=body!=old;operation=None
        if change:
            state,operation=reserve(state,bank*8+offset//4096);ops.append(operation)
        prepared.append((item,body,dict(bank=bank,address=f'{address:04X}',role=item['role'],image=f'B{bank}-{address:04X}.bin',sha256=sha(body),original_sha256=sha(old),identical_to_capture=not change,requires_replace=change,journal_operation=operation)))
    after=classify_journal(state);old_rows=[];replaced=[]
    for off in range(0x4000,0x6000,256):
        row=banks[3][off:off+256]
        if valid_snapshot(row):
            info=dict(address=f'{off+0x8000:04X}',sequence=int.from_bytes(row[8:12],'little'),sha256=sha(row));old_rows.append(info)
            if row!=state[off:off+256]:replaced.append(info)
    rotations=[s for op in ops for s in op['journal_sector_erases']]
    plan=dict(schema=3,status='PLAN_ONLY_NO_DEVICE_ACCESS',CPU=cpu,F_writes=0,MON_generation='00000010',direct_C_D_payloads=False,serial_access=False,retire_obsolete_requested=retire,
        source_bank_sha256={f'B{b}':sha(v) for b,v in banks.items()},targets=[x[2] for x in prepared],component_erases=sum(x[2]['requires_replace'] for x in prepared),journal_sector_erases=rotations,journal_appends=sum(len(x['journal_appends']) for x in ops),
        total_erases=sum(x[2]['requires_replace'] for x in prepared)+len(rotations),journal_before=before,journal_after=after,old_journal_rows=old_rows,old_rows_replaced_on_chip=replaced,
        RTC_metadata_preserved=True,SPI_RTC_data_or_settings_writes=False,boot_policy_changed=False,optional_default_selection_append_included=False,
        source_rule='Keep board idle; recapture/reprepare after any image/settings/journal change',
        execution='Review occupied targets and history replacement first. Use matched native OPAQUE writer, not a raw programmer; it commits each wear reservation before erasing. This script never opens a port.',
        ownership='Host plan contains private captures and journal history. Do not redistribute. Runtime tools borrow RAM; escrow/restore separately.',
        default_binding='Changing MON generation may require a separately reviewed CONFIG C A/B append. Preserving bytes does not automatically rebind an old generation.')
    if out.exists():raise ValueError('Fresh output directory required')
    out.mkdir(parents=True);(out/'.gitignore').write_text('*\n');backup=out/'private-before';backup.mkdir()
    for b,v in banks.items():(backup/f'B{b}.bin').write_bytes(v)
    (out/'retained-CD-history.bin').write_bytes(banks[3][0x4000:0x6000])
    for item,body,info in prepared:(out/info['image']).write_bytes(body)
    (out/'install-plan.json').write_text(json.dumps(plan,indent=2)+'\n')
    print(f"Prepared {len(prepared)} sectors; {plan['component_erases']} replacements + {len(rotations)} journal erases = {plan['total_erases']}. No port opened; F is not a target.")
    return plan

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--root',type=Path,default=ROOT);p.add_argument('--cpu',choices=('65c02','65c816e'),required=True)
    for b in range(4):p.add_argument(f'--current-b{b}',type=Path,required=True)
    p.add_argument('--retire-obsolete',action='store_true',help='Also propose clearing all 9 designated legacy/free sectors; review every occupied preimage')
    p.add_argument('--out',type=Path,required=True);a=p.parse_args();prepare(a.root,{b:getattr(a,f'current_b{b}') for b in range(4)},a.cpu,a.out,a.retire_obsolete)
if __name__=='__main__':main()
