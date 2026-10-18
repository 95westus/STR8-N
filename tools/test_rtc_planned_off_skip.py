"""Offline: planned-off board skips preserve other acquisition and late guards."""
import contextlib,hashlib,json,sys,tempfile
from pathlib import Path
from unittest.mock import patch
import snapshot_rtc_campaign as m
ROOT=Path(__file__).resolve().parents[1]

def main():
    checks=[]
    for case in ('planned-off-plus-powered','late-operation-guard','only-powered-off'):
        with tempfile.TemporaryDirectory(prefix='rtc-off-skip-',dir=ROOT/'tmp') as tmp:
            root=Path(tmp).resolve();q=root/'output/qualification';(q/'device-operations').mkdir(parents=True)
            index=q/'baseline.json';index.write_text(json.dumps(dict(boards=[dict(board=b,trim_steps=-14,control_register=128) for b in ('2512','2609')])))
            off=['2205'] if case=='late-operation-guard' else ['2205','2609']
            (q/'active-rtc-campaign.json').write_text(json.dumps(dict(baseline_index=str(index),baseline_index_sha256=hashlib.sha256(index.read_bytes()).hexdigest(),powered_off_boards=off)))
            marker=q/'device-operations/2609.json';marker.write_text('{}');actual_read=Path.read_text;marker_reads=[];opens=[];enumerations=[]
            def read(p,*a,**kw):
                if p==marker and case=='late-operation-guard':
                    marker_reads.append(1);return json.dumps(dict(block_snapshot=len(marker_reads)>1,state='checking'))
                return actual_read(p,*a,**kw)
            def link(port,*a,**kw):
                opens.append(port);assert port=='COM2512' and case=='planned-off-plus-powered','Powered-off or guarded port selected'
                raise RuntimeError('Expected powered-on acquisition reached; test stops before hardware')
            def ports():
                enumerations.append(1)
                return [type('P',(),dict(device='COM'+b,serial_number=m.SERIALS[b]))() for b in ('2512','2609')]
            @contextlib.contextmanager
            def lease(*a,**kw):yield
            argv=['snapshot','--board','2512','--board','2609'] if case=='planned-off-plus-powered' else ['snapshot','--board','2609']
            with patch.object(m,'ROOT',root),patch.object(m,'Link',link),patch.object(m,'comports',ports),patch.object(m,'serial_lease',lease),patch.object(m,'read_s19',lambda p:({0x2000:0x60},0x2000)),patch.object(Path,'read_text',read),patch.object(sys,'argv',argv):
                try:m.main()
                except RuntimeError as error:assert case=='planned-off-plus-powered' and 'Expected powered-on' in str(error)
                except AssertionError as error:
                    assert case!='planned-off-plus-powered'
                    assert ('Every selected board was skipped' if case=='late-operation-guard' else 'pending device operation') in str(error)
                else:raise AssertionError('Incomplete fake sample claimed success')
            summaries=list(q.glob('rtc-campaign-snapshot-*/summary.json'))
            if case=='planned-off-plus-powered':
                assert opens==['COM2512'] and len(summaries)==1
                summary=json.loads(summaries[0].read_text());assert not summary['passed'] and summary['skipped_boards'][0]['board']=='2609' and 'powered off' in summary['skipped_boards'][0]['reason']
            elif case=='late-operation-guard':
                assert not opens and len(marker_reads)==2 and len(summaries)==1 and not json.loads(summaries[0].read_text())['passed']
            else:assert not opens and not enumerations and not summaries
            checks.append(dict(case=case,passed=True,real_port_opens=0));print('PASS',case,flush=True)
    out=ROOT/'output/qualification/rtc-planned-off-skip-2026-10-18-r2.json';assert not out.exists()
    out.write_text(json.dumps(dict(passed=True,checks=checks,board_access=False,snapshot_tool_sha256=hashlib.sha256(Path(m.__file__).read_bytes()).hexdigest(),test_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest()),indent=2)+'\n')
if __name__=='__main__':main()
