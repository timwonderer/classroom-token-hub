"""Fetch and verify local macOS proof tools; never install system packages."""
import hashlib
import json
from pathlib import Path
import subprocess
import tarfile
from urllib.request import Request, urlopen

HERE = Path(__file__).resolve().parent
CACHE = HERE / '.cache'
TOOLS = CACHE / 'tools'


def main():
    TOOLS.mkdir(parents=True, exist_ok=True)
    for name, entry in json.loads((HERE / 'tools.lock.json').read_text()).items():
        target = TOOLS / name
        if not target.exists():
            with urlopen(Request(entry['url'], headers={'User-Agent': 'CTH-local-docs-proof'}), timeout=60) as response:
                target.write_bytes(response.read())
        digest = hashlib.sha256(target.read_bytes()).hexdigest()
        if digest != entry['sha256']:
            raise SystemExit(f'Checksum mismatch: {name}; refusing to execute or extract')
    if not (TOOLS / 'hugo-extracted').exists():
        subprocess.run(['pkgutil', '--expand-full', str(TOOLS / 'hugo.pkg'), str(TOOLS / 'hugo-extracted')], check=True)
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
