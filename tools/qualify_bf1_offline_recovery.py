"""Fresh offline bf1 A/restore cut, recovery and transport-refusal checks."""
import argparse,json,traceback
from pathlib import Path
from datetime import datetime,timezone
import bf1_offline_recovery_model as q
p=q.p;c=q.c;route=q.route
def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--out',type=Path,required=True);ap.add_argument('--mode',choices=['cuts','transport','refusals'],required=True);ap.add_argument('--phases',nargs='+',choices=list(q.PHASES),default=list(q.PHASES));a=ap.parse_args();a.out.mkdir(parents=True,exist_ok=False)
    backup=p.ROOT/'output/qualification/2604-return-backup-2026-10-17-1724Z';driver=q.Driver(a.out,backup,p.ROOT/'tmp/bfr2');contexts={phase:q.context(phase) for phase in a.phases};sources={str(q.PRIOR/'report.json'):p.sha((q.PRIOR/'report.json').read_bytes())};cuts=0
    def record_refusal(name,call):
        try:call()
        except (ValueError,AssertionError) as e:driver.record(name,refused=True,reason=str(e));return
        raise AssertionError('Unsafe input admitted: '+name)
    try:
      for phase,ctx in contexts.items():
        driver.record(phase+'-complete-input-proof-reused',reused_from=str(ctx['folder']),prior_report_sha256=ctx['prior_report_sha256'],meaning='Prior passed full CPU execution and exact mutation trace; not a fresh full execution')
        if a.mode=='cuts':
          points=q.schedule(ctx);(a.out/(phase+'-cut-schedule.json')).write_text(json.dumps(points)+'\n')
          for n in points:
            name=f'{phase}-cut-{n}';m,info=driver.execute(name,ctx['source'],ctx['tx'],ctx['data'],ctx['expected'],cut=n);current=list(map(bytes,m.banks));cuts+=1
            assert list(map(list,m.events))==ctx['events'][:n],'Fresh CPU prefix differs from attested prior full run'
            driver.boot(name+'-boot',current)
            tx,data,expected=q.recovery(current,ctx,m.events);recovered,ri=driver.execute(name+'-recovered',current,tx,data,expected)
            final=current if recovered is None else list(map(bytes,recovered.banks));driver.boot(name+'-recovered-boot',final)
            # Every recovered payload is exact; newer C/D sequences/counts are
            # deliberately retained rather than copied from the old backup.
            assert all(final[b]==ctx['expected'][b] for b in (0,1,2)) and final[3][:0x4000]==ctx['expected'][3][:0x4000] and final[3][0x6000:]==ctx['expected'][3][0x6000:]
            before=c.latest(current)[2];after=c.latest(final)[2];assert all(int.from_bytes(after[24+i*3:27+i*3],'little')>=int.from_bytes(before[24+i*3:27+i*3],'little') for i in range(32))
          tx,data,expected=q.recovery(ctx['expected'],ctx,ctx['events']);assert tx['no_change'];driver.execute(phase+'-completed-recovery-no-op',ctx['expected'],tx,data,expected)
        elif a.mode=='transport':
          for bank in range(4):driver.execute(f'{phase}-stale-bank-{bank}',ctx['source'],ctx['tx'],ctx['data'],ctx['expected'],stale=bank)
          for n in range(len(ctx['info']['steps'])):
            for failure in ('corrupt','partial'):
              driver.execute(f'{phase}-{failure}-row-{n}',ctx['source'],ctx['tx'],ctx['data'],ctx['expected'],**{failure:n})
        else:
          current=ctx['expected'];events=ctx['events'];info=ctx['info'];source=ctx['source'];certificate=p.bank_hashes(current)
          changed=list(map(bytearray,current));changed[0][0]^=1
          wrong=list(map(bytearray,source));wrong[0][0]^=1
          record_refusal(phase+'-changed-preimage',lambda:route.attest_recovery(changed,source,events=events,info=info,certificate=certificate))
          record_refusal(phase+'-wrong-backup',lambda:route.attest_recovery(current,wrong,events=events,info=info,certificate=certificate))
          record_refusal(phase+'-truncated-trace',lambda:route.attest_recovery(current,source,events=events[:-1],info=info,certificate=certificate))
          record_refusal(phase+'-out-of-scope-write',lambda:route.attest_recovery(current,source,events=events+[['program',0,0x8000,0]],info=info,certificate=certificate))
          cfg=c.latest(ctx['expected'])[2][8:24]
          record_refusal(phase+'-invalid-fallback',lambda:route.transaction(source,ctx['expected'],fallback_page=0x90,target_config=cfg,label='Refusal only'))
          target=list(map(bytearray,ctx['expected']));fo=(ctx['tx']['fallback_page']-0x80)*256;target[3][fo+100]^=1
          record_refusal(phase+'-fallback-overwrite',lambda:route.transaction(source,target,fallback_page=ctx['tx']['fallback_page'],target_config=cfg,label='Refusal only'))
          config=bytearray(cfg);config[5]^=1;config[14:]=p.config_checksum(config)
          record_refusal(phase+'-startup-change',lambda:route.transaction(source,ctx['expected'],fallback_page=ctx['tx']['fallback_page'],target_config=bytes(config),label='Refusal only'))
          # Explicit synthetic journal limits derived from the same source;
          # never claim these are observed hardware states.
          for kind in ('sequence','counter'):
            synthetic=list(map(bytearray,source));seq,off,row,valid=c.latest(synthetic);modified=bytearray(row)
            if kind=='sequence':modified[4:8]=(0xfffffffe).to_bytes(4,'little')
            else:
                bank,sector=ctx['tx']['planned_erase_order'][0];start=24+(bank*8+sector-8)*3;modified[start:start+3]=b'\xff'*3
            modified[120:122]=p.crc(modified[:120]).to_bytes(2,'little');synthetic[3][off:off+128]=modified
            record_refusal(phase+'-synthetic-'+kind+'-exhaustion',lambda:route.transaction(synthetic,ctx['expected'],fallback_page=ctx['tx']['fallback_page'],target_config=cfg,label='Synthetic refusal only'))
        (a.out/(phase+'-checkpoint.json')).write_text(json.dumps(dict(passed=True,phase=phase,mode=a.mode,cumulative_checks=len(driver.checks),source_context=str(ctx['folder']),prior_complete_trace_reused=True,board_access=False),indent=2)+'\n')
      for f in [Path(__file__),Path(q.__file__),Path(route.__file__),Path(c.__file__)]:sources[str(f.resolve())]=p.sha(f.read_bytes())
      report=dict(passed=True,candidate_id='batchfix-r1',mode=a.mode,phases=a.phases,finished_utc=datetime.now(timezone.utc).isoformat(),checks=driver.checks,cases=len(driver.checks),fresh_CPU_transactions=driver.fresh_transactions,fresh_CPU_boots=driver.fresh_boots,reused_boot_checks=driver.reused,cut_cases=cuts,prior_full_trace_proofs_reused=len(contexts),sources=sources,serial_disabled=True,board_access=False,clock_trim_changes=False,installation_permitted=False,release_qualified=False,physical_interruption_qualified=False,physical_restoration_qualified=False,scope='All modeled reservation/erase/commit boundaries and immediate predecessors in the selected pinned phase traces, not every program byte or electrical timing; exact replay-attested completion with monotonic wear counts and write-free completed no-op. Transport/refusal modes are separate.')
      (a.out/'report.json').write_text(json.dumps(report,indent=2)+'\n');print('PASS',len(driver.checks),'bf1 offline',a.mode,'checks',flush=True)
    except BaseException:
      (a.out/'failure.json').write_text(json.dumps(dict(passed=False,checks=driver.checks,error=traceback.format_exc()),indent=2)+'\n');raise
if __name__=='__main__':main()
