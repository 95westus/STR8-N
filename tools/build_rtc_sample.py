"""Build the read-only STR8-N RTC sampler for MON G 2000."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil

from rebuild_mon_services import assemble
from example_images import s19

ROOT = Path(__file__).resolve().parents[1]


def build(out):
    source=ROOT/'firmware/rtc-sample/sample.asm'
    out.mkdir(parents=True,exist_ok=False)
    stage=out/'build'
    stage.mkdir()
    shutil.copyfile(source,stage/'sample.asm')
    body,symbols=assemble(stage,'sample',0x2000,'SERVICE_END',transform=False)
    if symbols['START']!=0x2000 or len(body)>1024:
        raise ValueError('Unexpected sampler layout')
    name='str8n-util-rtc-sample-0.1.0-ram.bin'
    (out/name).write_bytes(body)
    records=s19(body,0x2000,0x2000)
    record_name=name.removesuffix('.bin')+'.s19'
    (out/record_name).write_bytes(records)
    manifest=dict(file=name,bytes=len(body),load='2000',entry='2000',
                  sha256=hashlib.sha256(body).hexdigest(),
                  source_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),
                  s19_file=record_name,s19_sha256=hashlib.sha256(records).hexdigest(),
                  format='RTC-SAMPLE1',capability='read-only RTC register sampling')
    (out/'rtc-sample.json').write_text(json.dumps(manifest,indent=2)+'\n',encoding='utf-8')
    return manifest


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out',type=Path,required=True)
    print(json.dumps(build(parser.parse_args().out),indent=2))

