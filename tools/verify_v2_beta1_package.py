"""Offline verification of the extracted beta kit and its flashing warnings."""
import hashlib
import argparse
import os
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ARCHIVE = ROOT / 'output/release/str8n-v2-b1.zip'
WARNING = 'WARNING - power failure during flashing can be dangerous.'

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--pdf-python', default=sys.executable,
                        help='Python interpreter with pypdf installed')
    args = parser.parse_args()
    stage = Path(tempfile.mkdtemp(prefix='beta1-kit-', dir=ROOT / 'tmp'))
    with zipfile.ZipFile(ARCHIVE) as archive:
        assert archive.testzip() is None and len(archive.namelist()) == 23
        for name in archive.namelist():
            target = (stage / name).resolve()
            assert target.is_relative_to(stage.resolve()), name
        archive.extractall(stage)
    for name in ('QUICKSTART', 'OPERATORS-MANUAL', 'TECHNICAL-GUIDE',
                 'CONFIGURATION', 'INSTALLER-GUIDE', 'BANK-MAINTENANCE', 'BETA1-RELEASE-NOTES'):
        assert WARNING in (stage / f'docs/{name}.md').read_text(encoding='utf-8'), name
    for name in ('QUICKSTART', 'OPERATORS-MANUAL'):
        text = subprocess.check_output([args.pdf_python, '-c',
            'import sys; from pypdf import PdfReader; print(" ".join(p.extract_text() for p in PdfReader(sys.argv[1]).pages))',
            str(stage / f'docs/{name}.pdf')], text=True)
        assert WARNING in ' '.join(text.split()), name
    for name, source in (
        ('str8n-v2-a24c1-f000-ffff.bin', 'BUILD/v2-a24c1-wdcmon-ram/str8n-v2-a24c1-f000-ffff.bin'),
        ('str8n-v2-a24c1-wdcmonv2-install-2000.s19', 'BUILD/v2-a24c1-wdcmon-ram/str8n-v2-a24c1-wdcmonv2-install-2000.s19'),
        ('str8n-bank-maint-2000.s19', 'BUILD/bank-maint-v2/str8n-bank-maint-2000.s19'),
        ('INSTALL-A24C1.ps1', 'INSTALL-A24C1.ps1'),
    ):
        assert (stage / name).read_bytes() == (ROOT / source).read_bytes(), name
    windows_env = os.environ.copy()
    # Let Windows PowerShell discover its own modules when launched from pwsh.
    for key in list(windows_env):
        if key.upper() == 'PSMODULEPATH':
            del windows_env[key]
    subprocess.run(['powershell.exe', '-NoProfile', '-ExecutionPolicy', 'Bypass',
                    '-File', str(stage / 'INSTALL-A24C1.ps1'), '-ValidateOnly'],
                   check=True, cwd=stage, env=windows_env)
    subprocess.run([sys.executable, str(stage / 'install_a24c1_linux.py'), '--validate-only'], check=True, cwd=stage)
    digest = hashlib.sha256(ARCHIVE.read_bytes()).hexdigest()
    assert ARCHIVE.with_suffix('.sha256').read_text().split()[0] == digest
    print('PASS: extracted launchers, exact images, seven Markdown warnings, two PDF warnings and ZIP checksum')
    print('QA directory:', stage)

if __name__ == '__main__':
    main()
