"""Run the transport refusal suite with an explicit disabled-gate fixture."""
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def main():
    text=(ROOT/'tools/test_bf1_live_transport.py').read_text(encoding='utf-8')
    old="        refused('Unqualified workflow gate refuses before serial selection/import',lambda:w.gate(a.kit))"
    new="""        import shutil
        disabled=tmp/'disabled-kit';shutil.copytree(a.kit,disabled,ignore=shutil.ignore_patterns('__pycache__'))
        manifest=r.read(disabled/'kit-manifest.json');manifest['live_installation_enabled']=False
        (disabled/'kit-manifest.json').write_text(json.dumps(manifest))
        refused('Explicitly disabled workflow gate refuses before serial selection/import',lambda:w.gate(disabled))"""
    assert old in text;text=text.replace(old,new)
    (ROOT/'tools/test_rc1_live_transport.py').write_text(text,encoding='utf-8')
if __name__=='__main__':main()
