"""Offline, capture-bound debugger install/rollback plans. Never opens a port."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import shutil
import sys

HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE/'engine'))
import runtime as r


def require(value,message):
    if not value:raise ValueError(message)


def save(path,value):
    path.write_text(json.dumps(value,indent=2)+'\n')


def safe(root,name):
    root=Path(root).resolve();path=(root/name).resolve()
    require(not Path(name).is_absolute() and path.is_relative_to(root),'Escaping file path')
    return path


def package(root=HERE):
    root=Path(root).resolve();m=r.read(root/'board-test-manifest.json')
    require(m['candidate']=='rc1-debugger-v1' and m['generation']==50 and not m['hardware_qualified'],'Wrong package')
    for name,info in m['files'].items():
        data=safe(root,name).read_bytes()
        require(len(data)==info['bytes'] and r.sha(data)==info['sha256'],'Changed package file: '+name)
    return m


def capture(root):
    root=Path(root).resolve();m=r.read(root/'capture.json')
    require(m['schema']==1 and m['repeat_verified'] is True,'Complete repeated capture required; assumed-erased captures refused')
    require(re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]{0,63}',m['board']) and m.get('usb_serial'),'Board and USB identity required')
    for name,info in m['files'].items():
        data=safe(root,name).read_bytes()
        require(len(data)==info['bytes'] and r.sha(data)==info['sha256'],'Changed capture file: '+name)
    banks=[]
    for bank in range(4):
        for suffix in ('','-repeat'):
            require(f'b{bank}{suffix}.bin' in m['files'],'Missing repeated bank')
        body=(root/f'b{bank}.bin').read_bytes()
        require(len(body)==32768 and body==(root/f'b{bank}-repeat.bin').read_bytes(),'Different repeated bank')
        banks.append(body)
    ram=(root/'application-ram.bin').read_bytes()
    require('application-ram.bin' in m['files'] and 'restore-application-ram.s19' in m['files'],'Missing application RAM archive')
    require(len(ram) in (0x6300,0x6500),'Archive must cover application RAM 0200-64FF or 0200-66FF')
    from legacy_transport import s19
    require((root/'restore-application-ram.s19').read_bytes()==s19(dict(enumerate(ram,0x200)),0x200),'RAM restore image differs from archive')
    r.clean_journal(banks)
    return m,banks


def derive(pkg,manifest,banks,direction,original=None):
    desired=list(map(bytearray,banks));_,_,row,_=r.clean_journal(banks);cfg=row[8:24]
    if direction=='install':
        old_cfg=cfg
    else:
        require(original is not None,'Rollback needs original source escrow')
        _,_,old_row,_=r.clean_journal(original);old_cfg=old_row[8:24]
    page=old_cfg[8] if old_cfg[7]==ord('P') else 0xA0
    require(page in (0xA0,0xB0),'Invalid original monitor preference')
    for sector in manifest['sectors']:
        bank=sector['bank'];off=sector['address']-0x8000
        before=(pkg/sector['baseline']).read_bytes()
        after=(pkg/sector['target']).read_bytes()
        require(banks[bank][off:off+4096]==(before if direction=='install' else after),
                f'Unrecognized source B{bank}:{sector["address"]:04X}; capture and inspect, do not force')
        target=after if direction=='install' else original[bank][off:off+4096]
        if direction=='rollback':require(target==before,'Original escrow is not admitted rc1')
        desired[bank][off:off+4096]=target
    target_cfg=r.preference(cfg,page,50 if direction=='install' else 49)
    tx,data,expected=r.transaction(banks,list(map(bytes,desired)),target_cfg,'DBG1 experimental '+direction)
    require(len(tx['operations'])==10,'Expected reservation + staging + seven firmware sectors + activation')
    require(expected[0]==banks[0] and expected[2]==banks[2],'B0/B2 changed')
    allowed={(s['bank'],s['address']) for s in manifest['sectors']}|{(3,0xC000),(3,0xD000)}
    require(all((op['bank'],op['address']&0xF000) in allowed for op in tx['operations']),'Unexpected flash destination')
    return tx,data,expected


def prepare(pkg,cap,out,direction,original_plan=None):
    pkg=Path(pkg).resolve();cap=Path(cap).resolve();out=Path(out).resolve()
    manifest=package(pkg);identity,banks=capture(cap);original=None;original_info=None
    if direction=='rollback':
        require(original_plan is not None,'--original-plan is required')
        original_info=verify(pkg,original_plan)
        require(original_info['direction']=='install','Original must be an install plan')
        require((identity['board'],identity['usb_serial'])==(original_info['board'],original_info['usb_serial']),'Rollback board/USB differs')
        original=[(Path(original_plan)/f'source-b{n}.bin').read_bytes() for n in range(4)]
    tx,data,expected=derive(pkg,manifest,banks,direction,original)
    require(not out.exists() and not out.is_relative_to(cap),'Use a new output outside the capture')
    info=r.compose(pkg/'engine/template',out,banks,tx,data,expected)
    (out/'capture').mkdir()
    for name in ['capture.json',*identity['files']]:
        dest=safe(out/'capture',name);dest.parent.mkdir(parents=True,exist_ok=True)
        shutil.copyfile(safe(cap,name),dest)
    info.update(schema=1,direction=direction,board=identity['board'],usb_serial=identity['usb_serial'],
                experimental_board_test=True,live_execution_qualified=False,
                package_manifest_sha256=r.sha((pkg/'board-test-manifest.json').read_bytes()),
                capture_manifest_sha256=r.sha((out/'capture/capture.json').read_bytes()),
                original_source_sha256=r.hashes(original) if original is not None else None)
    if original is not None:
        for n,body in enumerate(original):(out/f'original-b{n}.bin').write_bytes(body)
    save(out/'plan.json',info);(out/'.gitignore').write_text('*\n')
    verify(pkg,out)
    return info


def verify(pkg,plan):
    pkg=Path(pkg).resolve();plan=Path(plan).resolve();manifest=package(pkg);info=r.read(plan/'plan.json')
    require(info['schema']==1 and info['experimental_board_test'] and not info['live_execution_qualified'],'Not an experimental plan')
    require(info['direction'] in ('install','rollback'),'Invalid direction')
    require(info['package_manifest_sha256']==r.sha((pkg/'board-test-manifest.json').read_bytes()),'Different package')
    identity,banks=capture(plan/'capture')
    require(info['capture_manifest_sha256']==r.sha((plan/'capture/capture.json').read_bytes()),'Capture binding changed')
    require((info['board'],info['usb_serial'])==(identity['board'],identity['usb_serial']),'Identity binding changed')
    original=None
    if info['direction']=='rollback':
        original=[(plan/f'original-b{n}.bin').read_bytes() for n in range(4)]
        require(r.hashes(original)==info['original_source_sha256'],'Original escrow changed')
    tx,data,expected=derive(pkg,manifest,banks,info['direction'],original)
    require(info['transaction']==tx and info['source_sha256']==r.hashes(banks) and info['expected_sha256']==r.hashes(expected),'Re-derived transaction differs')
    for n in range(4):
        require((plan/f'source-b{n}.bin').read_bytes()==banks[n] and (plan/f'expected-b{n}.bin').read_bytes()==expected[n],'Changed source/target escrow')
    require(info['installer_sha256']==r.sha((plan/'installer-model-only.s19').read_bytes()),'Installer hash changed')
    # Re-compose the installer, not merely its data, to detect edited control tables.
    import tempfile
    with tempfile.TemporaryDirectory(prefix='dbg-plan-verify-',dir=plan.parent) as temporary:
        check=Path(temporary)/'recomposed';r.compose(pkg/'engine/template',check,banks,tx,data,expected)
        require((check/'installer-model-only.s19').read_bytes()==(plan/'installer-model-only.s19').read_bytes(),'Installer differs from re-derived transaction')
    for n,(op,body) in enumerate(zip(tx['operations'][1:],data[1:])):
        transfer=bytearray(body)
        if op['commit_address'] is not None:transfer[op['commit_address']-op['address']]=255
        require((plan/f'transfer-{n:02d}.bin').read_bytes()==transfer,'Changed transfer payload')
    return info


def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('operation',choices=('install','rollback','verify'))
    ap.add_argument('--package',type=Path,default=HERE);ap.add_argument('--capture',type=Path);ap.add_argument('--out',type=Path)
    ap.add_argument('--original-plan',type=Path);ap.add_argument('--plan',type=Path);args=ap.parse_args()
    if args.operation=='verify':require(args.plan,'--plan required');info=verify(args.package,args.plan)
    else:
        require(args.capture and args.out,'--capture and --out required')
        info=prepare(args.package,args.capture,args.out,args.operation,args.original_plan)
    print(json.dumps(dict(passed=True,board_access=False,direction=info['direction'],board=info['board'],
                         transfers=len(info['transaction']['operations'])-1,erase_order=info['transaction']['planned_erase_order']),indent=2))


if __name__=='__main__':
    try:main()
    except (ValueError,OSError,KeyError) as error:raise SystemExit('REFUSED: '+str(error))
