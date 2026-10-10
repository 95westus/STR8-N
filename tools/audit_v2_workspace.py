"""Bind phase-5 qualification to the paired libraries, client and resident image."""
import hashlib,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'BUILD/v2-spi-resident';W=OUT/'workspace'
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
read=lambda p:json.loads(p.read_text())
def main():
    meta=read(W/'build.json');test=read(W/'test-results.json');integration=read(W/'integration-test-results.json')
    resident=read(OUT/'build.json');qualified=read(OUT/'candidate-check.json');store=read(OUT/'store/candidate-check.json')
    assert qualified['passed'] and qualified['artifacts']==resident['artifacts'] and store['passed']
    assert store['store_sha256']==sha(OUT/'store/sram.bin')
    assert meta['sha256']==sha(W/'workspace.bin') and meta['source_sha256']==sha(ROOT/'tools/v2-spi/workspace.asm')
    guards=read(W/'guard-test-results.json')
    formatting=read(W/'format-test-results.json')
    console=read(W/'console-test-results.json')
    for report in (test,integration,guards,formatting,console):
        assert report['passed'] and report['workspace_sha256']==meta['sha256'] and report['resident_artifacts']==resident['artifacts']
    assert len(test['resize_write_cuts'])==133 and len(test['claim_write_cuts'])==100
    example=read(W/'example/build.json');assert integration['example_sha256']==example['sha256']==sha(W/'example/example.bin')
    assert example['source_sha256']==sha(ROOT/'tools/v2-spi/workspace-example.asm')
    assert (OUT/'split/gateway.bin').read_bytes()[0x1AF]==0
    result=dict(passed=True,workspace_sha256=meta['sha256'],store_sha256=store['store_sha256'],resident_artifacts=resident['artifacts'],
        workspace_bytes=meta['bytes'],workspace_state_bytes=meta['end']-meta['symbols']['REQ'],
        example_bytes=example['bytes'],cache_bytes=16,request_bytes=32,max_stack_bytes=max(test['max_stack_bytes'],integration['max_stack_bytes']),
        board_access=False,boards_flashed=False,permanent_service_ram_added=0)
    (W/'candidate-check.json').write_text(json.dumps(result,indent=2)+'\n')
    print('PASS paired adjustable SRAM/workspace candidate, client, interruption models and actual SPI integration; no board access')
if __name__=='__main__':main()
