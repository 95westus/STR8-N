"""Package the public source and existing payloads; no firmware build or simulation."""
import argparse,hashlib,json,zipfile
from pathlib import Path
from verify import ROOT,read,sha,verify


def package(out,files=None):
    files=verify() if files is None else files;release=read(ROOT/'release.json');out=Path(out).resolve()
    if out.exists():raise ValueError('Use a new output directory')
    out.mkdir(parents=True);name=release['project']+'-'+release['tag']+'-source';path=out/(name+'.zip')
    manifest=json.dumps(dict(project=release['project'],version=release['version'],prerelease=release['prerelease'],
        files={p.relative_to(ROOT).as_posix():sha(p) for p in files}),indent=2).encode()+b'\n'
    with zipfile.ZipFile(path,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=9) as archive:
        for rel,data in [(p.relative_to(ROOT).as_posix(),p.read_bytes()) for p in files]+[('PACKAGE-MANIFEST.json',manifest)]:
            entry=zipfile.ZipInfo(name+'/'+rel,date_time=(1980,1,1,0,0,0));entry.compress_type=zipfile.ZIP_DEFLATED
            entry.create_system=3;entry.external_attr=0o100644<<16;archive.writestr(entry,data,compress_type=zipfile.ZIP_DEFLATED,compresslevel=9)
    digest=sha(path);checksum=out/(path.name+'.sha256');checksum.write_text(digest+'  '+path.name+'\n',encoding='ascii')
    (out/'PACKAGE-MANIFEST.json').write_bytes(manifest)
    print('PASS package',path,'SHA256',digest,flush=True)
    return path


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--out',type=Path,default=ROOT/'dist')
    args=parser.parse_args();package(args.out)
