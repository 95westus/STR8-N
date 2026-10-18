"""rc1 user tools: exact-source empty-bank migration and bounded recovery."""
import argparse
import json
import sys
from pathlib import Path
import migrate
import recover
import runtime as r


def main(argv=None):
    if sys.version_info < (3,10):
        raise ValueError('Python 3.10 or newer required')
    p=argparse.ArgumentParser(description=__doc__)
    sub=p.add_subparsers(dest='command',required=True)
    for name in ('verify','status'):sub.add_parser(name)
    verify_plan=sub.add_parser('verify-plan',help='Re-derive an offline beta4 or direct-WDC plan and all installer inputs')
    verify_plan.add_argument('--plan',type=Path,required=True)
    beta=sub.add_parser('beta4',help='Prepare a bound beta4-to-rc1 plan from a verified local capture')
    beta.add_argument('--capture',type=Path);beta.add_argument('--out',type=Path,required=True)
    beta.add_argument('--metadata-escrow',type=Path)
    wdc=sub.add_parser('wdcmonv2',help='Direct exact-source WDC conversion; live scope is enforced by kit qualification')
    wdc.add_argument('--capture',type=Path)
    wdc.add_argument('--out',type=Path);wdc.add_argument('--history',type=Path);wdc.add_argument('--metadata-escrow',type=Path)
    wdc.add_argument('--accept-unknown-wear-history',action='store_true')
    for parser in (beta,wdc):
        parser.add_argument('--port');parser.add_argument('--usb-serial');parser.add_argument('--board')
        parser.add_argument('--empty-banks',action='store_true',help='Require erased B0/B1/B2; RAM preflight refuses occupied banks')
        parser.add_argument('--no-host-readback',action='store_true',help='Skip additional RAM readbacks; retain source acquisition and on-device preflight/verification')
    recovery=sub.add_parser('recover',help='Prepare bounded forward recovery or historical beta4 restoration')
    recovery.add_argument('operation',choices=('forward','restore-beta4'))
    recovery.add_argument('--capture',type=Path,required=True);recovery.add_argument('--plan',type=Path,required=True);recovery.add_argument('--out',type=Path,required=True)
    recovery.add_argument('--port');recovery.add_argument('--usb-serial');recovery.add_argument('--board');recovery.add_argument('--no-host-readback',action='store_true')
    for name in ('capture','install'):
        live=sub.add_parser(name,help='Capture a qualified monitor; installation uses the route-specific launcher')
        live.add_argument('--port',required=True);live.add_argument('--board',required=True)
        live.add_argument('--usb-serial');live.add_argument('--out',type=Path)
    a=p.parse_args(argv)
    kit=Path(__file__).resolve().parent;manifest=migrate.verify_kit(kit)
    if a.command=='verify':
        print('PASS rc1 kit hashes; no serial port opened; live installation '+('enabled for admitted empty-bank routes' if manifest['live_installation_enabled'] else 'remains disabled'))
        return 0
    if a.command=='verify-plan':
        plan=r.read(a.plan/'plan.json')
        if plan['route']=='direct-wdcmonv2-to-rc1':
            import factory_wdc
            factory_wdc.validate_plan(a.plan,kit)
        else:migrate.validate_beta4_plan(a.plan,kit)
        print('PASS bound offline plan; no serial port opened; execution requires separate live admission')
        return 0
    if a.command=='status':
        print(json.dumps(dict(version=manifest['version'],generation=manifest['generation'],
            review_only=not manifest['live_installation_enabled'],live_installation_enabled=manifest['live_installation_enabled'],
            distribution_qualified=manifest['distribution_qualified'],
            available=['verify','verify-plan','exact beta4/direct-WDC planning','bounded forward/recovery planning']+
                (['explicit-port empty-bank migration','monitor capture','bounded live recovery'] if manifest['live_installation_enabled'] else []),
            pending=['full release acceptance','generic occupied-bank upgrades','Linux physical serial migration acceptance','original-route RTC preservation closure']),indent=2))
        return 0
    if a.command in ('capture','install'):
        # No serial import or port enumeration occurs before this refusal.
        if not manifest['live_installation_enabled']:raise ValueError('This review kit is not qualified for board capture/install. No port was opened.')
        r.require(a.command=='capture','Use the route-specific wdcmonv2/beta4 launcher to install a bound complete plan')
        r.require(a.out,'A fresh --out capture directory is required')
        import workflow
        workflow.capture_monitor(kit,a.port,a.usb_serial,a.board,a.out);return 0
    if a.command=='beta4':
        if a.port:
            import workflow
            workflow.install('beta4',kit,a.port,a.usb_serial,a.board,a.out,empty_banks=a.empty_banks,host_readback=not a.no_host_readback)
            return 0
        r.require(a.capture,'--capture or an admitted live --port workflow is required')
        info=migrate.prepare_beta4(a.capture,kit,a.out,a.metadata_escrow)
    elif a.command=='recover':
        if a.port:
            import workflow
            workflow.recovery_live(a.operation,kit,a.plan,a.capture,a.out,a.port,a.usb_serial,a.board,host_readback=not a.no_host_readback)
            return 0
        info=recover.prepare_recovery('prepare-'+a.operation,kit,a.plan,a.capture,a.out)
    else:
        if a.port:
            import workflow
            r.require(a.out,'A fresh private --out is required')
            workflow.install('wdcmonv2',kit,a.port,a.usb_serial,a.board,a.out,empty_banks=a.empty_banks,
                unknown_wear=a.accept_unknown_wear_history,host_readback=not a.no_host_readback)
            return 0
        r.require(a.capture,'--capture or an admitted live --port workflow is required')
        if a.out:
            import factory_wdc
            info=factory_wdc.prepare(a.capture,kit,a.out,a.history,a.metadata_escrow,a.accept_unknown_wear_history)
            print(json.dumps(info,indent=2));return 0
        info=migrate.inspect_wdc(a.capture,kit)
        print(json.dumps(info,indent=2))
        print('REFUSED: Direct factory-WDC conversion is not qualified; inspection only.',file=sys.stderr)
        return 3
    print(json.dumps(info,indent=2));return 0


if __name__=='__main__':
    try:raise SystemExit(main())
    except (ValueError,OSError,KeyError) as error:raise SystemExit('REFUSED: '+str(error))
