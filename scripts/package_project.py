"""Create an uploadable source archive without local environments or private .env."""
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    destination = ROOT / 'dist' / 'yimo-fastapi.zip'
    destination.parent.mkdir(exist_ok=True)
    files = []
    for directory in ('app', 'data', 'deploy', 'scripts', 'tests'):
        files.extend(p for p in (ROOT / directory).rglob('*') if p.is_file() and '__pycache__' not in p.parts and p.suffix != '.pyc')
    files.extend(ROOT / name for name in (
        'README.md', 'requirements.txt', 'requirements-dev.txt', 'requirements.lock.txt',
        'pyproject.toml', 'Dockerfile', 'compose.yml', 'compose.production.yml',
        '.env.example', '.dockerignore', '.gitignore',
    ))
    with ZipFile(destination, 'w', ZIP_DEFLATED) as archive:
        for path in sorted(files):
            archive.write(path, path.relative_to(ROOT).as_posix())
    with ZipFile(destination) as archive:
        assert archive.testzip() is None
    print(f'{destination} ({destination.stat().st_size:,} bytes, {len(files)} files)')


if __name__ == '__main__':
    main()
