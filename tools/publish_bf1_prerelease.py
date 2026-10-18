"""Publish only the owner-authorized scoped bf1 prerelease after fresh gate checks."""
import argparse,json,hashlib,subprocess,sys
from pathlib import Path
from datetime import datetime,timezone
from zoneinfo import ZoneInfo
from check_bf1_acceptance import required_rtc_fresh
ROOT=Path(__file__).resolve().parents[1];Q=ROOT/'output/qualification';OUT=ROOT/'output/releases/bf1-github-prerelease-2026-10-17'
read=lambda p:json.loads(p.read_text(encoding='utf-8'))
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
def gh(*args):
    r=subprocess.run(['gh',*args],capture_output=True,text=True)
    if r.returncode:raise RuntimeError(r.stderr)
    return r.stdout

def completed_migration_scope(body):
    """Describe the admitted source profiles without advertising a generic launcher."""
    return body.replace(
        'Only the exact separately admitted 2604/2609 migration lineages are covered.',
        'Migration testing covers the exact separately admitted 2604/2609 lineages,\n'
        'plus the exact staged 2512 WDCMONV2 diagnostic/monitor profile and published\n'
        'v2.0b4 generation-13 MON A profile. Both 2512 routes passed separate offline,\n'
        'hardware, historical-source and original-payload restoration checks, with\n'
        'retained storage and application RAM preserved. This does not qualify\n'
        'arbitrary vendor WDC images or provide a generic preserving legacy installer.')
def readiness(report,now,expires):
    pilot=report['soaks']['2609'];main=report['soaks']['2604']
    migrations=report.get('migration_routes',{})
    required={'2512-wdcmonv2-to-bf1','2512-v2.0b4-to-bf1'}
    return (now<expires and report['prerelease_ready'] and not report['errors']
            and report.get('distribution_qualification',{}).get('status')=='passed'
            and required.issubset(migrations) and all(migrations[k]['status']=='passed' and migrations[k]['board']=='2512' for k in required)
            and pilot['status']=='passed' and pilot['application_RAM_restored']
            and pilot['monitored_hours']>=4 and pilot['complete_cycles']>=1
            and not pilot['coverage_review_required']
            and main['state'] in ('running','yielding-to-drift')
            and not main['coverage_review_required']
            and required_rtc_fresh(report))
def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--publish',action='store_true');a=ap.parse_args()
    policy_ptr=read(Q/'bf1-acceptance-policy-current.json');policy_path=Path(policy_ptr['policy']);assert sha(policy_path)==policy_ptr['sha256'];policy=read(policy_path)
    assert policy['owner_accepted'] and policy['prerelease']['owner_authorized_GitHub_prerelease']
    draft=read(OUT/'draft.json');assert draft['repo']=='95westus/STR8-N' and draft['tag']=='v2.0bf1' and draft['draft'] and draft['prerelease']
    assert sha(OUT/'preparation.json')==draft['preparation_sha256']
    for info in draft['assets'].values():assert sha(Path(info['path']))==info['sha256']
    outcome=subprocess.run([sys.executable,str(ROOT/'tools/check_bf1_acceptance.py')],capture_output=True,text=True)
    ptr=read(Q/'bf1-acceptance-current.json');report_path=Path(ptr['report']);assert sha(report_path)==ptr['sha256'];report=read(report_path)
    assert (datetime.now(timezone.utc)-datetime.fromisoformat(report['observed_utc'])).total_seconds()<120
    now=datetime.now(timezone.utc);expires=datetime(2026,10,18,5,0,tzinfo=timezone.utc)
    ready=outcome.returncode==0 and readiness(report,now,expires)
    status=dict(checked_utc=now.isoformat(),ready=ready,assessment=str(report_path),assessment_sha256=sha(report_path),expired=now>=expires,publication_requested=a.publish,full_release_qualified=False,board_access=False)
    path=OUT/('publication-readiness-'+now.strftime('%Y-%m-%d-%H%M%SZ')+'.json');assert not path.exists();path.write_text(json.dumps(status,indent=2)+'\n')
    if not ready or not a.publish:print(json.dumps(status,indent=2));return
    assert report['soaks']['2609']['status']=='passed' and report['soaks']['2609']['application_RAM_restored']
    assert report['soaks']['2604']['state'] in ('running','yielding-to-drift') and not report['errors']
    assert required_rtc_fresh(report)
    base=f"repos/{draft['repo']}";release=json.loads(gh('api',f"{base}/releases/{draft['release_id']}"))
    assert release['tag_name']==draft['tag'] and release['prerelease'] and release['target_commitish']==draft['source_commit']
    assert {x['name'] for x in release['assets']}==set(draft['assets'])
    for asset in release['assets']:
        expected=draft['assets'][asset['name']];assert asset['size']==expected['bytes'] and asset['digest']=='sha256:'+expected['sha256']
    original=(OUT/'release-notes.md').read_text(encoding='utf-8');pilot=report['soaks']['2609'];soak=report['soaks']['2604']
    body=original.replace('six-hour','four-hour')
    body=body.replace('Publication waits for the four-hour 2609 preserving soak\nand verified original application RAM restoration.', 'The owner-amended four-hour 2609 preserving soak passed, with original application RAM\nrestoration verified.')
    held='**Draft held: both 2512 migration routes are mandatory.**\nPublication is held until BOTH 2512 migration routes pass separate offline and\nhardware qualification: WDCMONV2-to-bf1 and published v2.0b4-to-bf1.\nNeither route is qualified yet. The publication automation is paused.'
    body=body.replace(held,'Both 2512 migration routes passed separate offline and hardware qualification:\nWDCMONV2-to-bf1 and published v2.0b4-to-bf1.')
    body=body.replace('Publication also waits for the four-hour 2609 preserving soak\nand verified original application RAM restoration.', 'The owner-amended four-hour 2609 preserving soak passed, with original application RAM\nrestoration verified.')
    body=completed_migration_scope(body)
    body+=f"\n\nPublication checkpoint: {now.astimezone(ZoneInfo('America/Chicago')).isoformat()}.\n2609: {pilot['monitored_hours']:.3f} monitored hours, {pilot['actual_passed_units']} passed units, {pilot['complete_cycles']} complete 34-unit cycles; RAM restored.\n2604 remains running: {soak['monitored_hours']:.3f} monitored hours, {soak['actual_passed_units']} passed units, {soak['complete_cycles']} complete cycles.\nAll three RTC streams are fresh. Longer endurance and RTC gates remain pending.\n"
    body=body.replace('All three RTC streams are fresh.','Required powered-on RTC streams ('+', '.join(report.get('required_rtc_boards',report['RTC']))+') are fresh. Owner-reported powered-off streams are suspended; their historical samples are retained and are not marked fresh.')
    if '2512' in report.get('powered_off_collection_suspended',{}):body+='\n2512 completed both migration routes and final bf1 verification before owner-reported power-off; 2205 also remains off. RTC collection continues on 2604/2609 with the original baseline.\n'
    notes=OUT/'published-release-notes.md';notes.write_text(body,encoding='utf-8')
    request=OUT/'publish.request.json';request.write_text(json.dumps(dict(draft=False,prerelease=True,make_latest='false',body=body)))
    if release['draft']:
        intent=OUT/'publication-intent.json'
        if not intent.exists():intent.write_text(json.dumps(dict(assessment=str(report_path),assessment_sha256=sha(report_path),release_id=release['id'],assets_verified=True,requested_utc=now.isoformat()),indent=2)+'\n')
        updated=json.loads(gh('api','--method','PATCH',f"{base}/releases/{draft['release_id']}",'--input',str(request)))
    else:updated=release
    assert not updated['draft'] and updated['prerelease'] and updated['tag_name']==draft['tag']
    tag=json.loads(gh('api',f"{base}/git/ref/tags/{draft['tag']}"));assert tag['object']['type']=='commit' and tag['object']['sha']==draft['source_commit']
    receipt=dict(published=True,repo=draft['repo'],tag=draft['tag'],url=updated['html_url'],source_commit=draft['source_commit'],release_id=updated['id'],published_at=updated['published_at'],assessment_sha256=sha(report_path),assets=draft['assets'],full_release_qualified=False,generic_installation_permitted=False,pending_gates=['2604 72-hour/300-cycle soak','Seven-day RTC performance acceptance','Broader electrical coverage and full release acceptance'],board_access=False)
    (OUT/'publication.json').write_text(json.dumps(receipt,indent=2)+'\n');(Q/'bf1-github-publication-current.json').write_text(json.dumps(dict(receipt=str((OUT/'publication.json').resolve()),sha256=sha(OUT/'publication.json')),indent=2)+'\n');print(json.dumps(receipt,indent=2))
if __name__=='__main__':main()
