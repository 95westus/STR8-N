"""Shared identity, backup, execution/readback and RAM recovery workflow.

Links are supplied by the caller. Importing this module never enumerates or
opens ports. All real port access is confined to the explicit live CLI adapter.
"""
from datetime import datetime, timezone
from pathlib import Path
import time
import traceback

from . import capture, package, plan
from .common import board_profile, check_board, save
from .engine import legacy_transport as wire, install_transport as transport, runtime as r


def idle(marker):
    r.require(marker['soak_owner_stopped'] and marker['RTC_sampling_owner_stopped'], 'Campaigns must remain stopped')
    blocked=('block_snapshot','application_RAM_restore_pending','physical_reset_pending','owner_application_running')
    r.require(not any(marker.get(k) for k in blocked) and not any(
        value for key,value in marker.items() if key.endswith('_worker_active') or key=='current_soak_worker_pid'), 'Board operation pending')


def marker_identity(marker, board):
    r.require(marker.get('board')==board_profile(board)['board'], 'Operation marker belongs to another board')


def recovery_ready(marker, board, folder, run):
    marker_identity(marker,board)
    r.require(marker.get('application_RAM_restore_pending') and
              marker.get('installer_plan_sha256')==r.sha((Path(folder)/'plan.json').read_bytes()) and
              marker.get('installer_run')==str(Path(run).resolve()), 'No matching pending RAM escrow')
    r.require(marker['soak_owner_stopped'] and marker['RTC_sampling_owner_stopped'], 'Campaigns must remain stopped')
    r.require(not marker.get('owner_application_running') and not marker.get('current_soak_worker_pid') and
              not any(value for key,value in marker.items() if key.endswith('_worker_active')), 'Board worker active')


def authorization(auth, board, action, *, root=None, folder=None):
    profile=board_profile(board)
    r.require(auth.get('owner_authorized') is True and auth.get('action')==action and
              (auth.get('board'),auth.get('usb_serial'))==(profile['board'],profile['usb_serial']) and
              not auth.get('other_boards_authorized') and not auth.get('RTC_campaign_resume_authorized'), 'Owner scope differs')
    if root:
        r.require(auth.get('manifest_sha256')==r.sha((Path(root)/'installer-manifest.json').read_bytes()), 'Authorization kit differs')
    if folder:
        r.require(auth.get('plan_sha256')==r.sha((Path(folder)/'plan.json').read_bytes()), 'Authorization plan differs')
    return profile


def identity(link, profile):
    r.require(link.command('').endswith(b'\r\nB3> '), 'Idle B3 required')
    version=link.command('VERSION')
    r.require(f"Board: {profile['board']}".encode() in version and profile['cpu'].encode() in version and b'2.0rc1' in version, 'Wrong board/CPU identity')
    for slot in ('A','B'):r.require(f'MONITOR {slot} gen 00000032 VALID'.encode() in version, 'Monitor invalid')
    r.require(link.dump(0x7BFC,0x7BFF)==bytes(4), 'Debugger active')
    return version.decode('ascii')


def read_range(link, first, last, prompt=b'\r\nB3> '):
    return b''.join(link.dump(a,min(a+4095,last),prompt) for a in range(first,last+1,4096))


def flash(link):
    banks=[]
    try:
        for bank in range(4):
            prompt=f'\r\nB{bank}> '.encode();link.command(f'B{bank}',prompt)
            banks.append(read_range(link,0x8000,0xFFFF,prompt))
    finally:link.command('B3')
    return banks


def preflight(root, link, board, out, marker, auth, *, synthetic=False):
    root,out=Path(root),Path(out);marker_identity(marker,board);idle(marker)
    profile=authorization(auth,board,'capture',root=root)
    manifest=package.validate(root)
    if manifest['board']:r.require(manifest['board']==board, 'Candidate board differs')
    r.require(not out.exists(), 'Fresh run directory required')
    version=identity(link,profile)
    monitor=dict(discovery=link.dump(0x7D04,0x7D0C).hex(),active_monitor=link.dump(0x7D30,0x7D30).hex(),
                 preferences={cmd:link.command(cmd).decode('ascii') for cmd in ('C','P','W')})
    first,second=flash(link),flash(link);r.require(first==second, 'Repeated flash differs')
    limit=int.from_bytes(link.dump(0x7D0A,0x7D0B),'little')
    r.require(limit in (0x64FF,0x66FF), 'Application RAM limit differs')
    ram=read_range(link,0x200,limit);r.require(ram==read_range(link,0x200,limit), 'Repeated RAM differs')
    source=plan.identify(root,manifest,first)
    out.mkdir(parents=True);(out/'.gitignore').write_text('*\n')
    capture.write(out/'before',profile,first,ram,synthetic=synthetic)
    save(out/'device-operation-before.json',marker);save(out/'owner-authorization.json',auth)
    report=dict(passed=True,board=board,source_profile=source,version=version,source_sha256=r.hashes(first),
                RAM_sha256=r.sha(ram),RAM_bytes=len(ram),flash_written=False,RAM_loaded=False,**monitor)
    save(out/'preflight.json',report)
    return report


def proof(root, folder, receipt):
    r.require(receipt['passed'] is True and receipt.get('board_access') is False and
              receipt.get('hardware_qualified') is False, 'Offline model proof required')
    r.require(receipt['manifest_sha256']==r.sha((Path(root)/'installer-manifest.json').read_bytes()) and
              receipt['plan_sha256']==r.sha((Path(folder)/'plan.json').read_bytes()), 'Model admission differs')
    r.require({x['CPU'] for x in receipt['models']}=={'65C02','65C816 E=1'} and
              all(x['passed'] for x in receipt['models']), 'Both CPU models required')
    from . import model
    r.require(receipt['model_source_sha256']==r.sha(Path(model.__file__).read_bytes()), 'Model implementation differs')


def load_ram(link, path):
    cells={};entry=None
    for row in Path(path).read_text().splitlines():
        raw=bytes.fromhex(row[2:]);r.require(sum(raw)&255==255 and len(raw)==raw[0]+1, 'Bad S19')
        address=int.from_bytes(raw[1:3],'big')
        if row.startswith('S1'):
            for i,value in enumerate(raw[3:-1]):
                r.require(address+i not in cells, 'Overlapping S19');cells[address+i]=value
        elif row.startswith('S9'):r.require(entry is None, 'Duplicate S9');entry=address
        else:r.require(row.startswith('S0'), 'Unknown S19')
    end=int.from_bytes(link.dump(0x7D0A,0x7D0B),'little')
    r.require(end in (0x64FF,0x66FF) and entry is not None and 0x200<=min(cells)<=entry<=max(cells)<=end, 'RAM range')
    r.require(set(cells)==set(range(min(cells),max(cells)+1)), 'Sparse S19')
    link.command('L',b'S19')
    for row in Path(path).read_bytes().splitlines():link.send(row+b'\r\n');time.sleep(.04)
    reply=link.until(b'\r\nB3> ')
    r.require(f'Entry {entry:04X}'.encode() in reply and not any(x in reply for x in (b'Bad',b'Protected',b'Wrap',b'Error')), 'RAM load refused')
    r.require(read_range(link,min(cells),max(cells))==bytes(cells[a] for a in sorted(cells)), 'RAM readback differs')


def restore_ram(link, cap):
    original=(Path(cap)/'application-ram.bin').read_bytes()
    load_ram(link,Path(cap)/'restore-application-ram.s19')
    for _ in range(2):r.require(read_range(link,0x200,0x200+len(original)-1)==original, 'Restored full RAM differs')


def execute(root, folder, run, link, board, marker, auth, receipt, *, marker_path=None):
    root,folder,run=map(Path,(root,folder,run))
    marker_identity(marker,board);idle(marker);profile=authorization(auth,board,'execute',root=root,folder=folder)
    info=plan.verify(root,folder);r.require(info['board']==board, 'Plan board differs');proof(root,folder,receipt)
    r.require(not (run/'flash-report.json').exists(), 'Fresh execution receipt required; do not repeat a write')
    escrow,banks=capture.validate(folder/'capture',board);original_ram=(folder/'capture/application-ram.bin').read_bytes()
    run.mkdir(parents=True,exist_ok=True);(run/'.gitignore').write_text('*\n')
    save(run/'execution-authorization.json',auth);save(run/'offline-admission.json',receipt)
    state=dict(passed=False,board=board,usb_serial=profile['usb_serial'],phase='fresh-source-check',
               board_access=not escrow.get('synthetic_model_fixture',False),
               application_RAM_restore_pending=False,physical_reset_pending=False,flash_written=False,
               plan_sha256=r.sha((folder/'plan.json').read_bytes()),manifest_sha256=info['package_sha256'],
               owner_authorization_sha256=r.sha((run/'execution-authorization.json').read_bytes()),
               offline_admission_sha256=r.sha((run/'offline-admission.json').read_bytes()))
    def checkpoint(phase=None):
        if phase:state['phase']=phase
        save(run/'flash-report.json',state)
        marker.update(state='installer-'+state['phase'],installer_worker_active=not state.get('closed',False),
                      installer_plan_sha256=state['plan_sha256'],installer_run=str(run.resolve()),
                      application_RAM_restore_pending=state['application_RAM_restore_pending'],physical_reset_pending=state['physical_reset_pending'])
        if state.get('closed') and borrowed and not state['passed']:marker['block_snapshot']=True
        if marker_path:save(marker_path,marker)
    borrowed=False;available=True
    try:
        checkpoint();state['version_before']=identity(link,profile)
        state['active_monitor_before']=link.dump(0x7D30,0x7D30).hex()
        r.require(flash(link)==banks, 'Fresh full flash differs from escrow')
        r.require(int.from_bytes(link.dump(0x7D0A,0x7D0B),'little')==0x200+len(original_ram)-1, 'Fresh RAM limit differs')
        r.require(read_range(link,0x200,0x200+len(original_ram)-1)==original_ram, 'Fresh original RAM differs')
        plan.verify(root,folder)
        if info['transaction'] is None:
            state.update(checks_passed=True,no_write=True,all_four_banks_verified=True)
        else:
            borrowed=True;available=False
            state.update(application_RAM_restore_pending=True,physical_reset_pending=True,flash_may_have_changed=True)
            checkpoint('installing')
            def progress(n,op):
                state.update(transfers_sent=n,last_destination=f"B{op['bank']}:{op['address']:04X}");checkpoint()
            state.update(transport.execute(link,folder,host_readback=True,progress=progress))
            state['flash_written']=True;checkpoint('awaiting-physical-reset')
            message=(f'SIMULATED RESET: {board} in-memory transaction verified.' if escrow.get('synthetic_model_fixture',False)
                     else f'RESET REQUIRED: {board} transaction verified; press physical RESET.')
            print(message,flush=True)
            boot=link.until(b'\r\nB3> ',1800);(run/'boot-after-installer.txt').write_bytes(boot)
            r.require(b'STR8-N 2.0rc1' in boot, 'Incomplete reset boot')
            available=True;state['physical_reset_pending']=False;checkpoint('verifying-target')
            state['version_after']=identity(link,profile)
            expected=[(folder/f'expected-b{n}.bin').read_bytes() for n in range(4)]
            actual=flash(link);r.require(actual==expected, 'Full target readback differs')
            r.require(plan.identify(root,package.validate(root),actual)==info['target_profile'], 'Target identity differs')
            r.require(r.clean_journal(actual)[2][8:24]==r.clean_journal(banks)[2][8:24], 'Owner settings changed')
            r.require(actual[3][0x1000:0x2000]==banks[3][0x1000:0x2000], 'RTC/TZ sector changed')
            r.require(link.dump(0x7D30,0x7D30).hex()==state['active_monitor_before'], 'Active monitor preference changed')
            state.update(all_four_banks_verified=True,settings_preserved=True,RTC_TZ_sector_preserved=True,
                         installed_applications=link.command('APPS').decode('ascii'),active_monitor=state['active_monitor_before'],
                         final_flash_sha256=r.hashes(actual),checks_passed=True)
    except BaseException:
        state['failure']=traceback.format_exc()
        raise
    finally:
        if borrowed and available:
            try:
                restore_ram(link,folder/'capture')
                state.update(application_RAM_restore_pending=False,RAM_restored=True,full_RAM_rereads=2)
            except BaseException:state['restoration_failure']=traceback.format_exc()
        state['passed']=bool(state.get('checks_passed')) and not any(k in state for k in ('failure','restoration_failure')) and not (
            state['application_RAM_restore_pending'] or state['physical_reset_pending'])
        state.update(closed=True,finished_utc=datetime.now(timezone.utc).isoformat())
        checkpoint('completed' if state['passed'] else 'inspection-required')
    r.require(state['passed'], 'Keep escrow; inspect report/pending flags')
    return state


def recover_ram(root, folder, run, link, board, marker, auth, *, marker_path=None):
    root,folder,run=map(Path,(root,folder,run))
    recovery_ready(marker,board,folder,run)
    profile=authorization(auth,board,'recover',root=root,folder=folder)
    r.require(not (run/'RAM-recovery.json').exists(), 'Fresh recovery receipt required')
    info=plan.verify(root,folder);r.require(info['board']==board and marker.get('application_RAM_restore_pending'), 'No matching pending RAM escrow')
    identity(link,profile);actual=flash(link);hashes=r.hashes(actual)
    tx=info['transaction'];r.require(tx is not None, 'No-write plan has no borrowed RAM')
    known=[info['source_sha256'],info['expected_sha256']]+[x['after_sha256'] for x in tx['operations']]
    r.require(hashes in known, 'Unknown interrupted flash state; retain escrow for inspection')
    save(run/'recovery-authorization.json',auth)
    restore_ram(link,folder/'capture')
    complete=hashes==info['expected_sha256']
    result=dict(passed=True,board=board,usb_serial=profile['usb_serial'],plan_sha256=r.sha((folder/'plan.json').read_bytes()),
                authorization_sha256=r.sha((run/'recovery-authorization.json').read_bytes()),
                flash_sha256=hashes,RAM_restored=True,full_RAM_rereads=2,physical_reset_pending=False,
                application_RAM_restore_pending=False,full_target_verified=complete,inspection_required=not complete)
    save(run/'RAM-recovery.json',result)
    marker.update(application_RAM_restore_pending=False,physical_reset_pending=False,installer_worker_active=False,block_snapshot=not complete)
    if marker_path:save(marker_path,marker)
    return result
