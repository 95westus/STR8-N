"""One capture-bound planner/verifier/restore path for all candidate profiles."""
from pathlib import Path
import shutil
import tempfile

from . import capture, package
from .common import check_board, safe, save
from .engine import runtime as r


def identify(root, manifest, banks):
    _,_,row,_=r.clean_journal(banks)
    for guard in manifest['admission_slices']:
        off=guard['address']-0x8000
        r.require(banks[guard['bank']][off:off+guard['bytes']]==safe(root,guard['file']).read_bytes(), 'Changed immutable admission slice')
    matches=[name for name,p in manifest['profiles'].items() if
        (not p['erased_b0'] or banks[0]==b'\xff'*32768) and all(
        banks[s['bank']][s['address']-0x8000:s['address']-0x7000]==safe(root,s['file']).read_bytes() for s in p['sectors'])]
    r.require(len(matches)==1, 'Unknown/mixed firmware; never force')
    r.require(int.from_bytes(row[17:21],'little')==manifest['generation'], 'Journal generation differs')
    return matches[0]


def derive(root, manifest, banks, target):
    source=identify(root,manifest,banks)
    r.require(target in manifest['profiles'], 'Unknown target')
    policy=manifest['cleanup']
    if policy:r.require(target==manifest['default_target'], 'This erase-only candidate has no restore target')
    if source==target:return source,None,[],banks
    desired=list(map(bytearray,banks))
    for row in manifest['profiles'][target]['sectors']:
        off=row['address']-0x8000
        desired[row['bank']][off:off+4096]=safe(root,row['file']).read_bytes()
    owner=policy['owner_erase'] if policy else []
    for item in owner:
        off=item['address']-0x8000
        r.require(r.sha(banks[0][off:off+4096])==item['sha256'], 'Demo source differs')
        desired[0][off:off+4096]=b'\xff'*4096
    cfg=r.clean_journal(banks)[2][8:24]
    tx,data,expected=r.transaction(banks,list(map(bytes,desired)),cfg,
        'profile installer '+source+' -> '+target,owner_erases=owner)
    declared={(bank,off+0x8000) for bank in range(4) for off in range(0,32768,4096)
              if banks[bank][off:off+4096]!=desired[bank][off:off+4096]}
    allowed=declared|{(3,0xC000),(3,0xD000)}
    r.require(len(tx['operations'])==len(declared)+3 and all(
        (op['bank'],op['address']&0xF000) in allowed for op in tx['operations']), 'Wrong declared-sector transaction')
    r.require(expected[0]==(b'\xff'*32768 if policy else banks[0]), 'Owner-bank preservation differs')
    r.require(expected[3][0x1000:0x2000]==banks[3][0x1000:0x2000], 'RTC/TZ history changed')
    for bank in range(4):
        for off in range(0,32768,4096):
            if (bank,off+0x8000) not in allowed:
                r.require(expected[bank][off:off+4096]==banks[bank][off:off+4096], 'Preservation failure')
    return source,tx,data,expected


def prepare(root, cap, out, target=None, board=None):
    root,cap,out=(Path(p).resolve() for p in (root,cap,out))
    manifest=package.validate(root);identity,banks=capture.validate(cap,board or manifest['board'])
    if manifest['board']:check_board(identity,manifest['board'])
    r.require(not out.exists() and not out.is_relative_to(cap) and not out.is_relative_to(root), 'Fresh output outside kit/capture required')
    source,tx,data,expected=derive(root,manifest,banks,target or manifest['default_target'])
    if tx is None:
        out.mkdir(parents=True)
        info=dict(transaction=None,action='already-current-no-write',source_sha256=r.hashes(banks),expected_sha256=r.hashes(banks))
    else:
        info=r.compose(root/'installer/engine/template',out,banks,tx,data,expected)
        info['action']='model-only-transaction'
    shutil.copytree(cap,out/'capture');(out/'.gitignore').write_text('*\n')
    info.update(schema=2,board=identity['board'],usb_serial=identity['usb_serial'],source_profile=source,
        target_profile=target or manifest['default_target'],board_access=False,installation_permitted=False,
        hardware_qualified=False,package_sha256=r.sha((root/'installer-manifest.json').read_bytes()),
        capture_sha256=r.sha((out/'capture/capture.json').read_bytes()))
    save(out/'plan.json',info);verify(root,out)
    return info


def verify(root, folder):
    root,folder=(Path(p).resolve() for p in (root,folder))
    manifest=package.validate(root);info=r.read(folder/'plan.json')
    r.require(info['schema']==2 and info['installation_permitted'] is False and info['hardware_qualified'] is False, 'Changed admission')
    r.require(info['package_sha256']==r.sha((root/'installer-manifest.json').read_bytes()), 'Changed kit binding')
    identity,banks=capture.validate(folder/'capture',manifest['board'])
    r.require(info['capture_sha256']==r.sha((folder/'capture/capture.json').read_bytes()), 'Changed capture binding')
    r.require((info['board'],info['usb_serial'])==(identity['board'],identity['usb_serial']), 'Changed identity')
    source,tx,data,expected=derive(root,manifest,banks,info['target_profile'])
    r.require(info['source_profile']==source and info['transaction']==tx and info['source_sha256']==r.hashes(banks)
              and info['expected_sha256']==r.hashes(expected), 'Re-derived plan differs')
    if tx is None:
        r.require(info['action']=='already-current-no-write' and not (folder/'installer-model-only.s19').exists()
                  and not list(folder.glob('transfer-*.bin')), 'Invalid no-write plan')
    else:
        r.require(info['action']=='model-only-transaction' and info['installer_sha256']==r.sha((folder/'installer-model-only.s19').read_bytes()), 'Changed installer binding')
        r.require(info['template_manifest_sha256']==r.sha((root/'installer/engine/template/manifest.json').read_bytes()), 'Changed template')
        with tempfile.TemporaryDirectory(prefix='installer-check-',dir=folder.parent) as tmp:
            check=Path(tmp)/'plan';r.compose(root/'installer/engine/template',check,banks,tx,data,expected)
            for path in check.iterdir():
                if path.name!='plan.json':r.require(path.read_bytes()==(folder/path.name).read_bytes(), 'Changed re-derived member: '+path.name)
    return info


def restore(root, original_plan, cap, out):
    original=verify(root,original_plan);manifest=package.validate(Path(root))
    r.require(manifest['cleanup'] is None, 'This erase-only candidate has no restore target')
    r.require(original['transaction'] is not None, 'No-write plan needs no restore')
    identity,_=capture.validate(cap)
    r.require((identity['board'],identity['usb_serial'])==(original['board'],original['usb_serial']), 'Wrong board escrow')
    return prepare(root,cap,out,original['source_profile'],identity['board'])
