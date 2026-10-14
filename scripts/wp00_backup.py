"""WP-00 local SQLite backup/restore. Standard library only; never imports the app."""
import argparse
import hashlib
import json
import shutil
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

VERSION = '1.1'

def digest(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()

def save(path, value):
    Path(path).write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding='utf-8')

def inspect_db(path):
    with sqlite3.connect(Path(path).resolve().as_uri() + '?mode=ro', uri=True) as db:
        integrity = [r[0] for r in db.execute('PRAGMA integrity_check')]
        tables = {}
        for (name,) in db.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"):
            quoted = '"' + name.replace('"', '""') + '"'
            tables[name] = db.execute('SELECT COUNT(*) FROM ' + quoted).fetchone()[0]
        schema = list(db.execute('SELECT type,name,tbl_name,sql FROM sqlite_master ORDER BY type,name'))
    if integrity != ['ok']:
        raise RuntimeError('SQLite integrity check failed')
    return {'integrity_check': integrity, 'table_rows': tables, 'schema': schema}

def files(root):
    root = Path(root).resolve()
    if not root.is_dir():
        raise FileNotFoundError(root)
    result = []
    for p in sorted(root.rglob('*')):
        if p.is_symlink() or p.is_junction():
            raise RuntimeError('Linked path refused: ' + str(p))
        if p.is_file():
            result.append(p)
    return result

def stable_copy(source, dest):
    dest.parent.mkdir(parents=True, exist_ok=True)
    for attempt in range(1, 4):
        before = digest(source)
        shutil.copyfile(source, dest)
        after = digest(source)
        if before == after == digest(dest):
            return {'sha256': after, 'size': dest.stat().st_size, 'attempts': attempt}
    raise RuntimeError('Source changed during copy; maintenance window required: ' + str(source))

def backup(args):
    source_db = args.database.resolve()
    roots = {'repair_docs': args.documents.resolve(), 'attachments': args.attachments.resolve()}
    if not source_db.is_file():
        raise FileNotFoundError(source_db)
    for root in roots.values():
        files(root)
    dest = args.output.resolve()
    # Prevent any output within source locations; require a fresh destination.
    if dest == source_db.parent or source_db.parent in dest.parents:
        raise ValueError('Backup must be outside business data directory')
    for root in roots.values():
        if dest == root or root in dest.parents:
            raise ValueError('Backup inside source refused')
    dest.mkdir(parents=True, exist_ok=False)
    manifest = {'script_version': VERSION, 'script_sha256': digest(__file__),
                'created_at': datetime.now(timezone.utc).isoformat(), 'status': 'INCOMPLETE',
                'database_source': str(source_db), 'source_directories': {k: str(v) for k,v in roots.items()},
                'files': [], 'consistency': 'SQLite transactional snapshot; files individually stable with end-of-copy inventory/hash check; not a distributed atomic snapshot'}
    save(dest / 'manifest.json', manifest)
    with sqlite3.connect(source_db.as_uri() + '?mode=ro', uri=True) as src:
        with sqlite3.connect(dest / 'diagnostic.db') as target:
            src.backup(target)
    manifest['database_check'] = inspect_db(dest / 'diagnostic.db')
    manifest['files'].append({'relative_path': 'diagnostic.db', 'source': str(source_db), 'source_directory': str(source_db.parent), 'size': (dest/'diagnostic.db').stat().st_size, 'sha256': digest(dest/'diagnostic.db'), 'method': 'sqlite3.Connection.backup'})
    snapshots = {}
    for name, root in roots.items():
        (dest/name).mkdir()
        snapshots[name] = files(root)
        for source in snapshots[name]:
            relative = Path(name) / source.relative_to(root)
            row = stable_copy(source, dest/relative)
            manifest['files'].append({'relative_path': relative.as_posix(), 'source': str(source), 'source_directory': str(root), **row})
    for index, source in enumerate(args.extra_file):
        source = source.resolve()
        if not source.is_file() or source.is_symlink():
            raise ValueError('Invalid extra source file')
        relative = Path('supplemental') / (str(index + 1).zfill(2) + '-' + source.name)
        row = stable_copy(source, dest/relative)
        manifest['files'].append({'relative_path': relative.as_posix(), 'source': str(source), 'source_directory': str(source.parent), **row})
    for name, root in roots.items():
        if files(root) != snapshots[name]:
            raise RuntimeError('Source inventory changed; maintenance window required')
    for row in manifest['files'][1:]:
        if digest(row['source']) != row['sha256']:
            raise RuntimeError('Source changed before backup completion; maintenance window required')
    manifest['status'] = 'COMPLETE'
    save(dest/'manifest.json', manifest)
    print(json.dumps({'backup': str(dest), 'status': manifest['status'], 'files': len(manifest['files']), 'tables': manifest['database_check']['table_rows']}, ensure_ascii=False))

def restore(args):
    source = args.backup.resolve()
    manifest = json.loads((source/'manifest.json').read_text(encoding='utf-8'))
    if manifest['status'] != 'COMPLETE':
        raise ValueError('Incomplete backup refused')
    paths = []
    for row in manifest['files']:
        relative = Path(row['relative_path'])
        path = (source/relative).resolve()
        if relative.is_absolute() or source not in path.parents:
            raise ValueError('Manifest path escape')
        if path.stat().st_size != row['size'] or digest(path) != row['sha256']:
            raise ValueError('Backup hash mismatch')
        paths.append((row, relative, path))
    dest = args.output.resolve()
    if dest == source or source in dest.parents:
        raise ValueError('Restore must be independent')
    dest.mkdir(parents=True, exist_ok=False)
    for name in manifest['source_directories']:
        if name not in ('repair_docs', 'attachments'):
            raise ValueError('Invalid manifest directory')
        (dest/name).mkdir()
    restored = []
    for row, relative, path in paths:
        result = stable_copy(path, dest/relative)
        if result['sha256'] != row['sha256']:
            raise ValueError('Restore mismatch')
        restored.append({'relative_path': relative.as_posix(), **result})
    check = inspect_db(dest/'diagnostic.db')
    expected = manifest['database_check']
    # JSON has normalized tuples to lists.
    if json.loads(json.dumps(check)) != expected:
        raise ValueError('Restored schema/table counts differ')
    result = {'status': 'PASS', 'verified_at': datetime.now(timezone.utc).isoformat(),
              'backup': str(source), 'restore': str(dest), 'database_check': check, 'verified_files': restored,
              'manifest_sha256': digest(source/'manifest.json'), 'script_sha256': digest(__file__)}
    save(dest/'restore-verification.json', result)
    print(json.dumps({'restore': str(dest), 'status': 'PASS', 'verified_files': len(restored), 'tables': check['table_rows']}, ensure_ascii=False))

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    p = sub.add_parser('backup')
    for field in ('database','documents','attachments','output'):
        p.add_argument('--'+field, type=Path, required=True)
    p.add_argument('--extra-file', type=Path, action='append', default=[])
    p.set_defaults(run=backup)
    p = sub.add_parser('restore')
    p.add_argument('--backup', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    p.set_defaults(run=restore)
    args = parser.parse_args()
    args.run(args)

