"""Package the Windows EXE with dependency notices for distribution."""
from importlib import metadata
from pathlib import Path
import shutil
import sys
import zipfile

ROOT = Path(__file__).resolve().parents[1]
PACKAGES = ('customtkinter', 'darkdetect', 'packaging', 'requests', 'certifi',
            'charset-normalizer', 'idna', 'urllib3', 'shapely', 'pyproj', 'numpy')


def main():
    output = ROOT / 'release-files'
    output.mkdir(exist_ok=True)
    binary = ROOT / 'dist' / 'BriefingMeteorologico.exe'
    if not binary.is_file():
        # Prepared local publication copy already has the verified EXE here.
        binary = output / 'BriefingMeteorologico.exe'
    if not binary.is_file():
        raise SystemExit('Compile o EXE antes de empacotar.')
    if binary.resolve() != (output / 'BriefingMeteorologico.exe').resolve():
        shutil.copyfile(binary, output / 'BriefingMeteorologico.exe')
    notices = output / 'third-party-licenses'
    notices.mkdir(exist_ok=True)
    index = ['DEPENDENCIAS REDISTRIBUIDAS', '',
             'Estas bibliotecas mantem suas proprias licencas; a licenca do projeto nao as substitui.',
             'Os arquivos anexos preservam textos e avisos disponibilizados pelas distribuicoes instaladas.', '']
    for name in PACKAGES:
        distribution = metadata.distribution(name)
        index.append(f'{name} {distribution.version}')
        destination = notices / name
        destination.mkdir(exist_ok=True)
        copied = 0
        for file in distribution.files or []:
            path = Path(str(file))
            if any(part == '..' for part in path.parts):
                continue
            lower = str(path).lower()
            if ('license' in lower or 'licence' in lower or 'copying' in lower or 'notice' in lower) and '.py' not in path.suffix:
                source = Path(distribution.locate_file(file))
                if source.is_file():
                    target = destination / path
                    target.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copyfile(source, target)
                    copied += 1
        if not copied:
            license_value = distribution.metadata.get('License-Expression') or distribution.metadata.get('License') or 'Consulte a documentacao oficial do pacote.'
            (destination / 'LICENSE-METADATA.txt').write_text(license_value, encoding='utf-8')
    python_license = Path(sys.base_prefix) / 'LICENSE.txt'
    if python_license.is_file():
        shutil.copyfile(python_license, notices / 'PYTHON-LICENSE.txt')
    (output / 'THIRD_PARTY_NOTICES.txt').write_text('\n'.join(index), encoding='utf-8')
    archive = output / 'BriefingMeteorologico-Windows-x64.zip'
    with zipfile.ZipFile(archive, 'w', zipfile.ZIP_DEFLATED) as bundle:
        bundle.write(binary, 'BriefingMeteorologico.exe')
        for name in ('README.md', 'LICENSE', 'RELEASE_NOTES.md'):
            path = ROOT / name
            if path.is_file():
                bundle.write(path, name)
        bundle.write(output / 'THIRD_PARTY_NOTICES.txt', 'THIRD_PARTY_NOTICES.txt')
        for path in notices.rglob('*'):
            if path.is_file():
                bundle.write(path, str(path.relative_to(output)))
    print(archive)


if __name__ == '__main__':
    main()
