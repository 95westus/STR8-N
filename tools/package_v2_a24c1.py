"""Assemble the agreed minimal a24c1 board-test ZIP; no serial access."""
import hashlib
import argparse
import json
from pathlib import Path, PurePosixPath
import re
import subprocess
import sys
import uuid
import zipfile

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / 'output/release/str8n-v2-a24c1-board-test.zip'
FILES = {
    'INSTALL-A24C1.ps1': 'INSTALL-A24C1.ps1',
    'start_wdcmonv2_ram.ps1': 'tools/wdcmonv2/start_wdcmonv2_ram.ps1',
    'INSTALL-A24C1.sh': 'INSTALL-A24C1.sh',
    'install_a24c1_linux.py': 'install_a24c1_linux.py',
    'str8n-v2-a24c1-wdcmonv2-install-2000.s19': 'BUILD/v2-a24c1-wdcmon-ram/str8n-v2-a24c1-wdcmonv2-install-2000.s19',
    'str8n-v2-a24c1-f000-ffff.bin': 'BUILD/v2-a24c1-wdcmon-ram/str8n-v2-a24c1-f000-ffff.bin',
    'str8n-bank-maint-2000.s19': 'BUILD/bank-maint-v2/str8n-bank-maint-2000.s19',
    'docs/QUICKSTART.pdf': 'output/pdf/STR8N-A24C1-C02-816-Quick-Start.pdf',
    'docs/QUICKSTART.md': 'docs/STR8N_V2_A24C1_QUICK_START.md',
    'docs/TECHNICAL-GUIDE.md': 'docs/STR8N_V2_A24C1_TECHNICAL_GUIDE.md',
    'docs/OPERATORS-MANUAL.pdf': 'output/pdf/STR8N-A24C1-Manual.pdf',
    'docs/OPERATORS-MANUAL.md': 'docs/STR8N_V2_A24C1_MANUAL.md',
    'docs/MAPS.pdf': 'output/pdf/STR8N-A24C1-Maps.pdf',
    'docs/MAPS.md': 'docs/STR8N_V2_A24C1_MAPS.md',
    'docs/CONFIGURATION.md': 'docs/STR8N_V2_FLASH_CONFIG.md',
    'docs/INSTALLER-GUIDE.md': 'docs/STR8N_V2_CONFIG_WDCMON_INSTALL.md',
    'docs/BANK-MAINTENANCE.md': 'docs/STR8N_BANK_MAINT_V2.md',
    'PUBLIC/str8n-v2-public.inc': 'src/v2-config/str8n-v2-public.inc',
}


def sha(data):
    return hashlib.sha256(data).hexdigest()


def package_markdown(text):
    # Documentation has shorter package names; retain source references as text.
    def link(match):
        label, target = match.groups()
        if '://' in target or target.startswith('#'):
            return match.group()
        path, separator, anchor = target.partition('#')
        source = str(PurePosixPath('docs') / path)
        # Collapse ../ references using POSIX path semantics without filesystem access.
        parts = []
        for part in PurePosixPath(source).parts:
            if part == '..':
                if parts:
                    parts.pop()
            elif part != '.':
                parts.append(part)
        source = '/'.join(parts)
        for destination, original in FILES.items():
            if source == original:
                local = '../' + destination if not destination.startswith('docs/') else destination[5:]
                return f'[{label}]({local}{separator}{anchor})'
        return f'{label} (source-checkout reference: `{path}`; not included in this kit)'

    text = re.sub(r'\[([^\]]+)\]\(([^)]+)\)', link, text)
    for destination, original in FILES.items():
        if original.endswith('.md'):
            text = text.replace(Path(original).name, Path(destination).name)
    return text.encode('utf-8')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--beta1', action='store_true', help='Package beta 1 with the exact qualified a24c1 firmware')
    args = parser.parse_args()
    output_path = OUTPUT
    title = 'STR8-N a24c1'
    if args.beta1:
        output_path = ROOT / 'output/release/str8n-v2-b1.zip'
        title = 'STR8-N beta 1 (a24c1 firmware)'
        FILES.update({
            'docs/BETA1-RELEASE-NOTES.md': 'docs/STR8N_V2_BETA1_RELEASE_NOTES.md',
            'docs/MIGRATION-RESET-ACCEPTANCE.md': 'docs/STR8N_V2_A24C1_TWO_BOARD_ACCEPTANCE_2026-10-03.md',
            'docs/COLD-CONFIG-ACCEPTANCE.md': 'docs/STR8N_V2_A24C1_COLD_CONFIG_ACCEPTANCE_2026-10-03.md',
            'docs/REGRESSION-ACCEPTANCE.md': 'docs/STR8N_V2_A24C1_REGRESSION_ACCEPTANCE_2026-10-03.md',
            'docs/BACKUP-RECOVERY-ACCEPTANCE.md': 'docs/STR8N_V2_A24C1_BACKUP_RECOVERY_ACCEPTANCE_2026-10-03.md',
        })
    # Refresh print copies before collecting the allowlist.
    for script in ('build_v2_quick_start_pdf.py', 'build_v2_a24c1_manuals_pdf.py'):
        subprocess.run([sys.executable, str(ROOT / 'tools' / script)], check=True)
    payload = {}
    for destination, source in FILES.items():
        data = (ROOT / source).read_bytes()
        if source.endswith('.md'):
            data = package_markdown(data.decode('utf-8'))
        elif source.endswith(('.sh', '.py')):
            data = data.replace(b'\r\n', b'\n')
        payload[destination] = data
    # Print from the packaged Markdown too, so abbreviated guide filenames agree.
    import build_v2_quick_start_pdf as renderer
    from reportlab.platypus import SimpleDocTemplate, Paragraph
    from reportlab.lib.pagesizes import A4
    print_stage = ROOT / 'tmp' / f'a24c1-package-print-{uuid.uuid4().hex[:8]}'
    print_stage.mkdir(parents=True)
    for stem, subtitle in (
        ('QUICKSTART', 'Quick start | C02 / 816'),
        ('OPERATORS-MANUAL', 'Operator and technical manual | C02 / 816'),
        ('MAPS', 'Maps diagrams and charts | C02 / 816'),
    ):
        source = print_stage / f'{stem}.md'
        source.write_bytes(payload[f'docs/{stem}.md'])
        renderer.SOURCE = source
        story = renderer.contents()
        story[1] = Paragraph(subtitle, renderer.HEADING)
        output = print_stage / f'{stem}.pdf'
        document = SimpleDocTemplate(str(output), pagesize=A4,
                                     leftMargin=42, rightMargin=42,
                                     topMargin=32, bottomMargin=46,
                                     title=f'{title} {subtitle}', author='STR8-N')
        document.build(story, onFirstPage=renderer.typography.footer,
                       onLaterPages=renderer.typography.footer)
        payload[f'docs/{stem}.pdf'] = output.read_bytes()
    manifest = json.loads((ROOT / 'BUILD/v2-a24c1-wdcmon-ram/manifest.json').read_text())
    maintenance = json.loads((ROOT / 'BUILD/bank-maint-v2/manifest.json').read_text())
    for name, expected in (
        ('str8n-v2-a24c1-f000-ffff.bin', manifest['candidate_f_sha256']),
        ('str8n-v2-a24c1-wdcmonv2-install-2000.s19', manifest['installer_s19_sha256']),
        ('str8n-bank-maint-2000.s19', maintenance['s19_sha256']),
    ):
        if sha(payload[name]) != expected:
            raise ValueError(f'Build hash mismatch: {name}')
    if maintenance['version'] != '1.0' or manifest['version'] != '2.0a24c1':
        raise ValueError('Unexpected component version')
    for name, data in payload.items():
        if not name.endswith('.md'):
            continue
        for target in re.findall(r'\[[^\]]+\]\(([^)]+)\)', data.decode('utf-8')):
            if '://' in target or target.startswith('#'):
                continue
            parts = list(PurePosixPath(name).parent.parts)
            for part in PurePosixPath(target.split('#')[0]).parts:
                if part == '..':
                    parts.pop()
                elif part != '.':
                    parts.append(part)
            if '/'.join(parts) not in payload:
                raise ValueError(f'Broken packaged link: {name} -> {target}')
    output_path.parent.mkdir(parents=True, exist_ok=True)
    # Atomic replacement prevents an incomplete archive being mistaken for a kit.
    temporary = output_path.with_suffix('.zip.tmp')
    with zipfile.ZipFile(temporary, 'w', zipfile.ZIP_DEFLATED) as archive:
        for name, data in payload.items():
            info = zipfile.ZipInfo(name, (2026, 10, 3, 12, 0, 0))
            info.create_system = 3
            mode = 0o755 if name == 'INSTALL-A24C1.sh' else 0o644
            info.external_attr = (0o100000 | mode) << 16
            info.compress_type = zipfile.ZIP_DEFLATED
            archive.writestr(info, data)
    with zipfile.ZipFile(temporary) as archive:
        if archive.testzip() is not None or set(archive.namelist()) != set(FILES):
            raise ValueError('Archive verification failed')
        for name, data in payload.items():
            if archive.read(name) != data:
                raise ValueError(f'Archive readback differs: {name}')
    temporary.replace(output_path)
    print(f'PASS: {len(payload)} allowlisted files; image hashes, document links and ZIP readback')
    digest = sha(output_path.read_bytes())
    if args.beta1:
        output_path.with_suffix('.sha256').write_text(f'{digest}  {output_path.name}\n', encoding='ascii')
    print(f'{output_path}\nSHA256 {digest}')


if __name__ == '__main__':
    main()
