"""Boundary checks for the adopted RTC rate/uncertainty acceptance policy."""
import json
from pathlib import Path
from check_bf1_acceptance import rate_gate
ROOT=Path(__file__).resolve().parents[1]
def main():
    limits=dict(target_abs_rate_ppm=5,minimum_powered_segment_hours=168,maximum_rate_uncertainty_halfwidth_ppm=2,maximum_gap_hours=4)
    def points(rate,half,hours=168):
        seconds=hours*3600
        return [dict(time=i*3*3600,low=(rate-half)*i*3*3600/1e6,high=(rate+half)*i*3*3600/1e6) for i in range(int(hours/3)+1)]
    cases=[('no-samples',[],'pending-duration'),('one-sample',[dict(time=0,low=-.5,high=.5)],'pending-duration'),('short-span',points(0,1,72),'pending-duration'),('zero-rate',points(0,1),'passed'),('positive-limit',points(4,1),'passed'),('negative-limit',points(-4,1),'passed'),('precision-insufficient',points(0,3),'pending-precision'),('overlap-positive-target',points(5,1),'inconclusive-collect-longer'),('overlap-negative-target',points(-5,1),'inconclusive-collect-longer'),('outside-positive-target',points(7,1),'clock-performance-review'),('outside-negative-target',points(-7,1),'clock-performance-review')]
    checks=[]
    for name,values,expected in cases:
        result=rate_gate(values,limits);assert result['status']==expected,(name,result)
        checks.append(dict(name=name,passed=True,status=expected))
    values=points(0,1);del values[4:7];assert rate_gate(values,limits)['collection_gap_review_required'];checks.append(dict(name='collection-gap-retained',passed=True))
    out=ROOT/'output/qualification/bf1-acceptance-policy-tests-2026-10-17.json';assert not out.exists();out.write_text(json.dumps(dict(passed=True,cases=len(checks),checks=checks,board_access=False),indent=2)+'\n');print('PASS',len(checks),'RTC acceptance boundary checks')
if __name__=='__main__':main()
