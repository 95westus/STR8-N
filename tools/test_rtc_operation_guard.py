"""Offline regression: a late board-operation guard prevents snapshot port open."""
import contextlib,hashlib,json,sys,tempfile
from pathlib import Path
from unittest.mock import patch
import snapshot_rtc_campaign as m
ROOT=Path(__file__).resolve().parents[1]
def main():
    with tempfile.TemporaryDirectory(prefix='rtc-guard-',dir=ROOT/'tmp') as tmp:
        root=Path(tmp).resolve();assert root.is_relative_to((ROOT/'tmp').resolve());q=root/'output/qualification';(q/'device-operations').mkdir(parents=True)
        index=q/'baseline.json';index.write_text(json.dumps(dict(boards=[dict(board='2609',trim_steps=-14,control_register=128)])))
        (q/'active-rtc-campaign.json').write_text(json.dumps(dict(baseline_index=str(index),baseline_index_sha256=hashlib.sha256(index.read_bytes()).hexdigest(),powered_off_boards=['2205'])))
        marker=q/'device-operations/2609.json';marker.write_text('{}');real_read=Path.read_text;reads=[];opens=[]
        def read(path,*a,**kw):
            if path==marker:
                reads.append(str(path));return json.dumps(dict(block_snapshot=len(reads)>1,state='checking'))
            return real_read(path,*a,**kw)
        def forbidden(*a,**kw):opens.append(a);raise AssertionError('Protected port opened')
        @contextlib.contextmanager
        def lease(*a,**kw):yield
        port=type('Port',(),dict(device='COM8',serial_number=m.SERIALS['2609']))()
        with patch.object(m,'ROOT',root),patch.object(m,'Link',forbidden),patch.object(m,'comports',lambda:[port]),patch.object(m,'serial_lease',lease),patch.object(m,'read_s19',lambda path:({0x2000:0x60},0x2000)),patch.object(Path,'read_text',read),patch.object(sys,'argv',['snapshot','--board','2609']):
            try:m.main()
            except AssertionError as e:assert 'Every selected board was skipped' in str(e),str(e)
            else:raise AssertionError('Empty snapshot claimed success')
        assert len(reads)==2 and not opens
        summaries=list(q.glob('rtc-campaign-snapshot-*/summary.json'));assert len(summaries)==1
        result=json.loads(summaries[0].read_text());assert not result['passed'] and not result['boards'] and result['skipped_boards'][0]['board']=='2609'
    out=ROOT/'output/qualification/rtc-late-operation-guard-2026-10-18-r2.json';assert not out.exists();out.write_text(json.dumps(dict(passed=True,late_guard_checked_under_lease=True,port_opens=0,empty_snapshot_not_success=True,board_access=False,test_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),snapshot_tool_sha256=hashlib.sha256(Path(m.__file__).read_bytes()).hexdigest()),indent=2)+'\n');print('PASS late operation guard: zero port opens; no false successful sample')
if __name__=='__main__':main()
