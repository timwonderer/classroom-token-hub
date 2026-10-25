"""Fetch and verify the pinned docs build tools (macOS or Linux); never install system packages."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tarfile
from urllib.request import Request, urlopen

HERE = Path(__file__).resolve().parent
CACHE = HERE / '.cache'
TOOLS = CACHE / 'tools'
HUGO = TOOLS / 'bin/hugo'


def main():
    TOOLS.mkdir(parents=True, exist_ok=True)
    for name, entry in json.loads((HERE / 'tools.lock.json').read_text()).items():
        if entry.get('platform', sys.platform) != sys.platform:
            continue
        target = TOOLS / name
        # A corrupt or partial cached file is discarded, never trusted or left to fail every run.
        if target.exists() and hashlib.sha256(target.read_bytes()).hexdigest() != entry['sha256']:
            target.unlink()
        if not target.exists():
            partial = target.with_name(f'{name}.part')
            with urlopen(Request(entry['url'], headers={'User-Agent': 'CTH-local-docs-proof'}), timeout=60) as response:
                partial.write_bytes(response.read())
            if hashlib.sha256(partial.read_bytes()).hexdigest() != entry['sha256']:
                partial.unlink()
                raise SystemExit(f'Checksum mismatch: {name}; refusing to execute or extract')
            partial.replace(target)
    if not HUGO.exists():
        HUGO.parent.mkdir(exist_ok=True)
        if sys.platform == 'darwin':
            subprocess.run(['pkgutil', '--expand-full', str(TOOLS / 'hugo-darwin.pkg'), str(TOOLS / 'hugo-extracted')], check=True)
            (TOOLS / 'hugo-extracted/Payload/hugo').replace(HUGO)
        elif sys.platform == 'linux':
            with tarfile.open(TOOLS / 'hugo-linux.tar.gz') as archive:
                archive.extract('hugo', HUGO.parent, filter='data')
            HUGO.chmod(0o755)
        else:
            raise SystemExit(f'No pinned Hugo build for {sys.platform}')
    if not (CACHE / 'hextra').exists():
        with tarfile.open(TOOLS / 'hextra.tar.gz') as archive:
            archive.extractall(CACHE / 'theme-extract', filter='data')
        children = list((CACHE / 'theme-extract').iterdir())
        assert len(children) == 1 and children[0].is_dir()
        children[0].rename(CACHE / 'hextra')
        (CACHE / 'theme-extract').rmdir()
    print('Verified Hugo 0.168.0, Hextra 0.13.0 and FlexSearch 0.8.143')


if __name__ == '__main__':
    main()
