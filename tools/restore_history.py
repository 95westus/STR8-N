#!/usr/bin/env python3
"""Verify or restore frozen source history as data; never run archived programs."""
import argparse
import hashlib
import io
import json
from pathlib import Path, PurePosixPath
import re
import stat
import zipfile

ROOT = Path(__file__).resolve().parents[1]
CONTEXT = ('release', 'docs', 'examples', 'tests/baselines', 'tests/fixtures', 'src/current', 'tools')
EXCLUDED = {'.git', '__pycache__', 'BUILD', 'output', 'backups', 'board-backups', 'qualification'}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def sha(body):
    return hashlib.sha256(body).hexdigest()


def name_parts(name):
    require(isinstance(name, str) and name and '\\' not in name, 'Unsafe archive path')
    path = PurePosixPath(name)
    require(path.parts and not path.is_absolute() and str(path) == name and
            all(part not in ('.', '..') for part in path.parts), 'Unsafe archive path: ' + name)
    for part in path.parts:
        require(not re.search(r'[\x00-\x1f<>:"|?*]', part) and part[-1] not in ' .', 'Unsafe archive path: ' + name)
        require(part.split('.')[0].upper() not in {'CON', 'PRN', 'AUX', 'NUL', 'CLOCK$',
                *('COM'+str(n) for n in range(1,10)), *('LPT'+str(n) for n in range(1,10))},
                'Reserved archive path: ' + name)
    return path.parts


def linked(path):
    return path.is_symlink() or getattr(path, 'is_junction', lambda: False)()


def verify(archive_root):
    requested = Path(archive_root).absolute()
    require(not any(linked(p) for p in (requested, *requested.parents)), 'Archive root crosses a symlink/junction')
    archive_root = requested.resolve()
    manifest_path = archive_root/'manifest.json'
    require(not linked(manifest_path), 'Manifest must be a regular file')
    manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
    require(manifest['schema'] == 1 and isinstance(manifest['files'], dict) and manifest['files'], 'Wrong archive schema')
    archive = manifest['archive']; parts = name_parts(archive['file'])
    require(len(parts) == 1, 'Archive filename must be directly below archive root')
    path = archive_root/archive['file']; require(not linked(path), 'Archive must be a regular file')
    body = path.read_bytes()
    require(len(body) == archive['bytes'] and sha(body) == archive['sha256'], 'Archive size/hash differs')
    names = set(manifest['files']); folded = {name.casefold() for name in names}
    require(len(folded) == len(names), 'Archive names collide on Windows')
    for name, row in manifest['files'].items():
        parts = name_parts(name)
        require(not any('/'.join(parts[:n]).casefold() in folded for n in range(1,len(parts))), 'Conflicting file/directory paths')
        require(type(row['bytes']) is int and row['bytes'] >= 0 and type(row['retired']) is bool and
                isinstance(row['sha256'], str) and re.fullmatch('[0-9a-f]{64}', row['sha256']), 'Invalid member metadata: ' + name)
    members = {}
    with zipfile.ZipFile(io.BytesIO(body)) as source:
        for info in source.infolist():
            name_parts(info.filename)
            require(info.filename not in members, 'Duplicate archive member: ' + info.filename)
            mode = stat.S_IFMT(info.external_attr >> 16)
            require(not info.is_dir() and mode in (0, stat.S_IFREG), 'Nonregular archive member: ' + info.filename)
            require(info.filename in names and not info.flag_bits & 1, 'Unexpected/encrypted archive member: ' + info.filename)
            row = manifest['files'][info.filename]
            require(info.file_size == row['bytes'], 'Member size differs: ' + info.filename)
            member = source.read(info)
            require(len(member) == row['bytes'] and sha(member) == row['sha256'], 'Member bytes/hash differ: ' + info.filename)
            members[info.filename] = member
    require(set(members) == names, 'Archive inventory differs')
    return manifest, members


def output_path(out, archive_root):
    requested = Path(out).absolute()
    require(not any(linked(p) for p in (requested, *requested.parents)), 'Restore output crosses a symlink/junction')
    out = requested.resolve(); root = ROOT.resolve()
    require(not out.exists(), 'Fresh restore directory required')
    require(not root.is_relative_to(out), 'Restore output cannot be the repository or an ancestor')
    protected = [root/name for name in ('archive','src','tools','release','docs','examples','tests',
                                      '.git','.codex','.agents','BUILD','output','backups','board-backups')]
    protected.append(Path(archive_root).resolve())
    require(not any(out.is_relative_to(p) for p in protected), 'Restore output is inside a protected repository path')
    return out


def context_members(originals):
    members = {}; root = ROOT.resolve()
    def excluded(path):
        parts = path.relative_to(root).parts
        return any(part in EXCLUDED for part in parts) or parts[:2] == ('docs','evidence')
    def collect(directory):
        for path in sorted(directory.iterdir()):
            if excluded(path):
                continue
            require(not linked(path), 'Context contains a symlink/junction: ' + path.relative_to(root).as_posix())
            if path.is_dir():
                collect(path)
            else:
                candidates.append(path)
    candidates = [root/name for name in ('LICENSE','README.md') if (root/name).exists()]
    for name in CONTEXT:
        directory = root/name
        if directory.exists():
            require(not any(linked(p) for p in (directory,*directory.parents) if p.is_relative_to(root)),
                    'Context contains a symlink/junction')
            collect(directory)
    original_names = [name.casefold() for name in originals]
    for path in sorted(candidates):
        relative = path.relative_to(root)
        if excluded(path):
            continue
        require(not linked(path), 'Context contains a symlink/junction: ' + relative.as_posix())
        require(path.is_file(), 'Context contains a nonregular file: ' + relative.as_posix())
        name = relative.as_posix(); name_parts(name)
        folded = name.casefold()
        if any(folded == archived or folded.startswith(archived+'/') or archived.startswith(folded+'/') for archived in original_names):
            continue
        members[name] = path.read_bytes()
    return members


def restore(archive_root, out, *, context=False):
    manifest, members = verify(archive_root)
    out = output_path(out, archive_root)
    if context:
        members = {**context_members(members), **members}
    # All archive and context validation finishes before any output is created.
    out.mkdir(parents=True)
    for name, body in sorted(members.items()):
        target = out.joinpath(*name_parts(name))
        target.parent.mkdir(parents=True, exist_ok=True)
        require(not any(linked(p) for p in (target.parent, *target.parent.parents) if p.is_relative_to(out)),
                'Restore output gained a symlink/junction')
        with target.open('xb') as stream:
            stream.write(body)
    return dict(passed=True, board_access=False, files=len(members), archived_files=len(manifest['files']),
                context=context, out=str(out), source_execution=False)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--archive-root', type=Path, default=ROOT/'archive')
    operations = parser.add_subparsers(dest='operation', required=True)
    for operation in ('verify','restore'):
        sub = operations.add_parser(operation)
        sub.add_argument('--archive-root', type=Path, default=argparse.SUPPRESS)
        if operation == 'restore':
            sub.add_argument('--out', type=Path, required=True)
            sub.add_argument('--context', action='store_true')
    args = parser.parse_args(argv)
    try:
        if args.operation == 'verify':
            manifest, _ = verify(args.archive_root)
            result = dict(passed=True, board_access=False, files=len(manifest['files']), source_execution=False)
        else:
            result = restore(args.archive_root, args.out, context=args.context)
    except (ValueError, KeyError, TypeError, OSError, zipfile.BadZipFile, RuntimeError) as error:
        parser.exit(1, 'History archive refused: '+str(error)+'\n')
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
