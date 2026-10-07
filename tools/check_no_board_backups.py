"""Reject board backup paths in Git's index, history and release ZIP members.

Generated firmware and test images are permitted; raw qualification/readback
artifacts belong in ignored local directories. This checker reads Git only.
"""
import argparse,io,re,subprocess,zipfile

PATH=re.compile(r'(?i)(?:^|/)(?:backups?|board-backups|qualification|evidence)(?:/|$)|(?:^|/)(?:prior|final|baseline|expected|installed|before|after)[-_]b[0-3](?:-repeat)?\.(?:bin|s19|a)$|(?:^|/)(?:b[0-3](?:-repeat)?|all-banks|full-flash)\.(?:bin|s19|a)$|(?:^|/)[^/]*(?:-backup|-readback)\.(?:bin|s19|a)$')

def git(*args):return subprocess.check_output(['git',*args])

def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--history',action='store_true');args=parser.parse_args()
    tracked=git('ls-files','-z').decode().split('\0');violations=[('tracked',p) for p in tracked if p and PATH.search(p)]
    rows=git('rev-list','--objects','--all').decode().splitlines() if args.history else git('ls-tree','-r','HEAD').decode().splitlines()
    objects={}
    for row in rows:
        if args.history:
            if ' ' not in row:continue
            oid,path=row.split(' ',1)
        else:
            metadata,path=row.split('\t',1);oid=metadata.split()[2]
        if PATH.search(path):violations.append(('history' if args.history else 'HEAD',path))
        if path.lower().endswith('.zip'):objects[oid]=path
    for oid,path in objects.items():
        archive=zipfile.ZipFile(io.BytesIO(git('cat-file','blob',oid)))
        for name in archive.namelist():
            if PATH.search(name):violations.append((path,name))
    if violations:
        for location,path in violations:print('FAIL',location,path)
        raise SystemExit(1)
    print('PASS no board backup/readback paths in tracked files,', 'reachable Git history' if args.history else 'HEAD', 'or',len(objects),'release ZIP blobs')
if __name__=='__main__':main()
