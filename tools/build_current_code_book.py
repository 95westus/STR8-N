"""Build the current-source reference book; never invokes firmware or board tools.

Run from the repository: python tools/build_current_code_book.py
Requires reportlab, markdown, and py65. Optional pypdfium2 renders review samples.
Local document-only dependencies may be installed in output/book-deps.
Editorial chapters live in docs/book/STR8N_CURRENT_CODE_BOOK.md.
"""
from __future__ import annotations

import hashlib
import html
import json
from pathlib import Path
import re
import sys
import textwrap
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'output/book-deps'))
import markdown
from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.utils import simpleSplit
from reportlab.platypus import (
    BaseDocTemplate, Frame, PageTemplate, Paragraph, Spacer, PageBreak,
    Preformatted, LongTable, TableStyle, KeepTogether,
)
from reportlab.platypus.tableofcontents import TableOfContents
from reportlab.graphics import renderSVG

sys.path.insert(0, str(ROOT / 'docs/book'))
from code_diagrams import CHARTS, Chart, atlas_text
from worker_reference import worker_charts, worker_text, ROUTINES as WORKER_ROUTINES
CHARTS.update(worker_charts(Chart))

OUT = ROOT / 'output/book'
PDFOUT = ROOT / 'output/pdf'
STEM = 'STR8N-1.35-Current-Code-Book'
EDITORIAL = ROOT / 'docs/book/STR8N_CURRENT_CODE_BOOK.md'
RELEASE = ROOT / 'BUILD/v1.35'

# These defaults are audited against the Makefile on every generation.
RELEASE_FLAGS = {
    'STR8_V1_LAYOUT', 'STR8_V1_INSTALLER_DRY', 'STR8_V1_INSTALLER_TXN',
    'STR8_IN65_COLD_BOOT', 'STR8_IN65_VERSION_135', 'STR8_IN65_EDU_QUIET_START',
}
KNOWN_FLAGS = RELEASE_FLAGS | {
    'STR8_RAM_PROOF', 'STR8_IN65_VERSION_133', 'STR8_BANK_MAINT_TOP',
    'STR8_DIRECTORY_REFRESH', 'STR8_IN65_BANK_MAINT', 'STR8_TOP_EMBED',
    'STR8_IN65_TOP_IMAGE', 'W2I_RESTORE_STOCK', 'W2I_STR8_IN65_IMAGE',
}
CURRENT_ASSEMBLY = {
    'bank-maint/str8n-v1.23-bank-maint-2000.asm',
    'bank-maint/str8n-v1.23-bank-maint-menu-2000.asm',
    'bank-maint/str8n-v1.23-bank-maint-rename.inc',
    'bank-maint/str8n-v1.28-str8-in65-bank-maint-flags.inc',
    'console-abi-test/str8n-v1.23-console-abi-test-2000.asm',
    'interrupt-test/str8n-v1.35-irq-test-2000.asm',
    'led-status-test/str8n-v1.35-led-worker-test-2000.asm',
    'str8-in65/str8n-v1.35-str8-in65-bank-maint-2000.asm',
    'top-update/str8n-v1.23-top-update-2000.asm',
    'wdcmonv2/wdcmonv2str8n-archive-2000.asm',
    'wdcmonv2/wdcmonv2str8n-install-2000.asm',
}

# Purpose and review considerations supplement each complete listing.
CARDS = {
    'Makefile': ('Build graph and release selection', 'Selects current production flags, tool variants, image generators, validators, and package prerequisites. Read dependencies as well as recipes: a target may trigger other builds. External WDC tools and the configured paths must exist.'),
    'str8.asm': ('Resident supervisor, services, and policy', 'Owns boot, IVI, console, command dispatch, I/L policy, directory validation, and relocation. Shared scratch and compact message placement are intentional constraints. This listing selects the production release profile; public entry contracts are distinct from private labels.'),
    'str8-worker.asm': ('Relocated flash and handoff engine', 'Executes from RAM when the flash window changes. Dispatches private modes, bounds polling, checks transitions, verifies sectors, and restores Bank 3 on returning paths. Successful guest launch never returns.'),
    'himon-image-eq.inc': ('External HIMON recognition contract', 'Defines fixed entry and image identification constants. Recognition enables the C/W compatibility path; it does not incorporate HIMON implementation or authenticate a payload.'),
    'str8-config-eq.inc': ('Protected configuration pocket', 'Defines locator and discovery policy defaults. Candidate defaults do not prove live board contents. Role and policy consumers must validate encodings.'),
    'str8-console-eq.inc': ('Fixed raw-console ABI', 'Publishes entry addresses, preservation rules, version, and capability bits. Bank 3 must be visible and the console must have the expected VIA configuration.'),
    'str8-directory-eq.inc': ('Directory layout and validator statuses', 'Defines field offsets, journal pair encodings, and record/write statuses. Pair ordering and one-way transitions matter as well as individual bit values.'),
    'str8-jump-eq.inc': ('Bank selection and handoff contract', 'Publishes the RAM selector entry, latch mask, patterns, and jump statuses. The current F010 implementation copies only the selector prefix; a complete worker is used for I/J.'),
    'str8-led-eq.inc': ('LED ownership and status encoding', 'Names PIA output bits and composite states. Raw public console calls do not update these LEDs; private wrappers and mutation/handoff paths own changes.'),
    'str8-ram-abi.inc': ('Shared RAM addresses and ownership', 'Defines overlay, reset signature, recovery fields, and assembler limit. Some locations have phase-dependent aliases; allocation does not imply permanent contents.'),
    'str8-record-eq.inc': ('Parser request/result ABI', 'Defines service signature, input card, decoded buffer, kinds, status codes, and private directory-worker mode. Public parsing is not a flash-application service.'),
    'str8-version.inc': ('Compact product identity', 'Supplies the banner selected by version flags. Product identity must not be confused with the independently versioned callable ABIs.'),
    'str8-worker-eq.inc': ('Worker linked/storage extents', 'Freezes selector size, worker size, run address, and storage address. The layout checker must agree with the real worker map before an image is accepted.'),
    'str8n-v1.23-bank-maint-2000.asm': ('Shared Bank Maintenance implementation', 'Contains inspection, copy/enrollment, adoption, erase, AP put, reclamation, and the private worker. Exact confirmations and role exclusions are operation-specific. Supported standalone/menu/iN65 branches are shown together.'),
    'str8n-v1.23-bank-maint-menu-2000.asm': ('Combined maintenance/updater wrapper', 'Defines embedded-top options and includes the maintained body. AP staging moves to $7000 because the top candidate occupies $4000.'),
    'str8n-v1.23-bank-maint-rename.inc': ('Guarded description rename and AP helpers', 'Reuses validated scratch and top-rewrite machinery. Rename preserves all directory bytes outside the selected description; no ordinary in-place flash overwrite is implied.'),
    'str8n-v1.28-str8-in65-bank-maint-flags.inc': ('iN65 discovery policy editor', 'Validates FF or A0-A7, defaults an empty selection to A6, detects no change, and delegates guarded top rewrite. Does not allocate WORK or backup roles.'),
    'str8n-v1.35-str8-in65-bank-maint-2000.asm': ('Current iN65 maintenance wrapper', 'Selects the production iN65 maintenance branch and version. Shared implementation remains in the maintained Bank Maintenance body.'),
    'str8n-v1.23-top-update-2000.asm': ('Top-sector updater and directory refresh', 'Runs independently of resident code after erase. Preserves directory for ordinary update, clears it for refresh, and installs candidate configuration. Backup/retry/restore and pre-erase cancellation have different control paths.'),
    'str8n-v1.23-console-abi-test-2000.asm': ('Board console ABI probe', 'Exercises published console/discovery contracts from RAM. Hardware execution is separate from assembling or inspecting this source.'),
    'str8n-v1.35-irq-test-2000.asm': ('Board interrupt probe', 'Exercises the current interrupt front doors and signature/vector behavior. Requires the intended board setup; host model checks are not physical interrupt qualification.'),
    'str8n-v1.35-led-worker-test-2000.asm': ('Board LED and production-worker probe', 'Tests status ownership and guarded worker operation. Review scratch and mutation guards before running; this is executable board-test code, not only a visual legend.'),
    'wdcmonv2str8n-archive-2000.asm': ('Stock-environment bank archive program', 'Exports complete bank contents and an integrity receipt. A verified host extraction is required to establish a usable backup; serial text alone is not enough.'),
    'wdcmonv2str8n-install-2000.asm': ('Stock migration and restore RAM engine', 'Preserves original Bank 3 using a narrowly accepted Bank 0 state, verifies candidate input, and changes the top sector only after safeguards. The source also supports selected restore/iN65 build profiles. Power loss remains a protected-top recovery risk.'),
    'board_serial.py': ('Direct serial session utility', 'Provides host serial interaction. Port selection and supplied commands determine board effects; reading the utility is safe, executing arbitrary commands may mutate board state.'),
    'board_capture.py': ('Board serial capture', 'Captures received data into a log for a bounded session. A transcript is observation evidence, not an independent byte-for-byte image verifier.'),
    'check_board_top.py': ('Captured board-top comparison', 'Checks board top-sector evidence against expected content. Inspect accepted input format and comparison bounds; it does not itself prove all banks or every hardware behavior.'),
    'build_directory_refresh_image.ps1': ('Host directory-refresh candidate', 'Builds a protected-top candidate with refreshed metadata. It creates an image; the guarded RAM driver performs board mutation.'),
    'build_ryors_full_bank_s19.ps1': ('External payload full-bank composition', 'Combines supplied R-YORS-related inputs into a bank image/stream. External payload implementation is outside STR8-N; verify input paths, extent, and entry assumptions.'),
    'build_str8n_top_bin.ps1': ('Canonical protected-sector composition', 'Imports resident and relocated worker records into a fixed sector, validates placement, and emits the programmer BIN. Map/address disagreement must fail instead of silently clipping bytes.'),
    'check_bank_maint_s19.ps1': ('Maintenance S19 structural checker', 'Checks records, RAM bounds, entry, and private-worker presence. Structural acceptance is not proof of runtime safety for every menu operation.'),
    'check_ram_abi_sources.ps1': ('Cross-source RAM contract check', 'Checks shared allocation assumptions across the selected sources. Static checks complement, but do not replace, runtime collision and phase analysis.'),
    'check_str8n_layout.ps1': ('Resident/worker linked layout checker', 'Verifies public locations, worker extents, storage, and growth margin against maps/includes. It prevents overlap but does not establish electrical flash behavior.'),
    'check_top_update_s19.ps1': ('Updater image checker', 'Validates RAM update image structure and embedded candidate expectations. Read the parameters for variant and artifact assumptions.'),
    'compose_str8n_install_s19.ps1': ('Install-stream validation and normalization', 'Validates selected bank/range and S9 policy and emits a payload-only stream with integrity reports. Metadata and worker bytes are not prepended as executable RAM records.'),
    'convert_guest_bin_to_s19.ps1': ('Dense binary-to-S19 converter', 'Maps binary offset zero to a selected base, emits dense records, and chooses/checks S9. Full-bank and partial/Bank-3 entry rules differ.'),
    'make_bank_maint_menu_a.ps1': ('Application carrier generator', 'Produces a generated .a carrier from the maintenance S19. Its encoded bytes are an output representation, not a second maintained implementation.'),
    'make_release_package.ps1': ('Standalone release packager', 'Builds an allowlisted archive and associated identity files. Packaging includes dependencies and documents but does not broaden their qualification.'),
    'make_top_update_image_inc.ps1': ('Embedded candidate include generator', 'Converts the canonical top BIN into assembler input and verification constants for RAM tools. The candidate must match the intended release image.'),
    'move_link_sidecars.ps1': ('Linker sidecar organization', 'Moves link-generated map/symbol sidecars into designated release locations. This is a build-file mutation utility, not a firmware transformation.'),
    'prepare_release_docs.ps1': ('Manual packaging and link preparation', 'Prepares documentation and local link checks for packaged layouts. Text rewriting can leave semantic drift even when links are valid.'),
    'verify_release_package.ps1': ('Release archive verifier', 'Checks allowlisted files, hashes, candidate identity, generated carrier, and nested package expectations. Integrity checks do not imply that all manual assertions are current.'),
    'write_str8n_manifest.ps1': ('Artifact and contract manifest', 'Records version, layout, hashes, and qualification metadata. Repository state and existing artifact state can differ; the manifest describes its supplied inputs.'),
    'write_str8n_public_contract.ps1': ('External ABI include generator', 'Publishes supported callable interfaces and request/result constants. External users should consume this contract instead of private symbol addresses.'),
    'test_s19_range_matrix.ps1': ('Install range policy matrix', 'Exercises accepted/rejected image extent and entry cases using host tools. Boundary coverage addresses policy, not real flash endurance or interruption behavior.'),
    'test_ram_load_contract.ps1': ('L span and error-policy checks', 'Checks RAM data/entry bounds and loader-related expectations. A host policy model is not the whole board transport path.'),
    'test_conservative_resident.py': ('Resident actual-opcode model tests', 'Executes parser, directory, loader, journal, and staging scenarios against controlled memory. Requires py65 and fixtures; modeled peripherals limit conclusions.'),
    'test_size_optimization.py': ('Resident behavior and placement tests', 'Exercises messages, copy verification, readiness, lines, startup, installer, and interrupt behavior through linked instructions. Assertions identify the implemented test scope.'),
    'test_worker_optimization.py': ('Banked-flash model and worker tests', 'Models bank switching, delayed flash completion, and injected failures while running linked 65C02 code. Some timeout cases shorten counters after checking production initialization; this is not electrical testing.'),
    'test_resident_reclaim.py': ('Resident layout/content regression check', 'Checks current resident output against retained expected constraints and fixture data. Fixture comparison is test machinery, not a chapter of product history.'),
    'test_bank_maint_roles.py': ('Maintenance startup and role guards', 'Runs current tool variants with stale modes, entry-bank states, and role configurations. Protects against unintended worker dispatch and role handling regressions.'),
    'test_top_backup_roles.py': ('Protected backup role tests', 'Exercises current updater/maintenance expectations for role configuration. Modeled state cannot prove a particular physical backup actually exists.'),
    'test_led_worker_probe.py': ('LED/worker probe host checks', 'Runs/checks current probe behavior in the host model. Board timing, physical switches, and indicators still require their own observation.'),
    'test_irq_probe.py': ('Interrupt probe host checks', 'Checks current IRQ probe execution and expected vector paths using the host test environment. It does not inject real electrical interrupts.'),
    'check_str8_in65_promotion.ps1': ('Production/candidate consistency check', 'Checks selected iN65 artifacts against production expectations. Matching bytes do not by themselves qualify all migration workflows.'),
    'check_stock_restore_s19.ps1': ('Stock-restore stream checker', 'Validates a restore image against the intended RAM and payload contract. Owner-local stock data remains external input.'),
    'build_str8_in65_test_image.ps1': ('iN65 test image composition', 'Builds the selected candidate image from specified inputs. Generated images are evidence inputs, not automatically safe board deployment instructions.'),
    'MIGRATE-WDC-TO-STR8N.py': ('Python migration orchestrator', 'Coordinates host migration workflow and its tools. Review arguments, confirmation policy, serial ownership, and backup paths before executing on hardware.'),
    'MIGRATE-WDC-TO-STR8N.ps1': ('PowerShell migration orchestrator', 'Coordinates the Windows-facing migration workflow. External monitor transport, archive evidence, and final verification are separate stages.'),
    'start_wdcmonv2_ram.py': ('Python stock-monitor RAM launcher', 'Loads/starts RAM utilities through the stock monitor and manages transfer state. Defaults and protocol behavior are visible in the listing; it can initiate board-side operations.'),
    'start_wdcmonv2_ram.ps1': ('PowerShell stock-monitor RAM launcher', 'Implements stock-monitor transport and launch handling. Port lifecycle and successful transfer do not replace flash readback verification.'),
    'capture_wdc_serial_reconnect.ps1': ('Reconnect capture helper', 'Captures stock-monitor serial/reconnect behavior for inspection. Retained bytes and timing are host observations, not a complete hardware proof.'),
    'extract_wdcmonv2_archive.ps1': ('Archive extraction and validation', 'Converts captured bank records into checked backup material. This is the host-side proof that an archive exists, beyond an operator acknowledgement.'),
    'make_wdcmonv2_install_image_inc.ps1': ('Migration candidate constants', 'Produces assembler input describing the selected top image for the migration installer. Candidate size/checksum identity must stay synchronized with supplied binary data.'),
    'make_wdcmonv2_migration_package.ps1': ('Migration kit packager', 'Assembles an explicit project-written tool/document kit. External WDC firmware and owner archives are not distributed as project source.'),
    'verify_wdcmonv2_migration_kit.ps1': ('Migration archive verifier', 'Checks kit contents and identities. Verifies packaging constraints rather than performing migration.'),
    'check_wdcmonv2_migration_package.ps1': ('Migration package consistency checker', 'Checks the generated kit against expected artifacts and policies. Run against the intended package, not an assumed matching directory name.'),
    'check_wdcmonv2_install.ps1': ('Migration installer structure checker', 'Validates installer S19 and embedded/supplied candidate expectations. Structural checks do not remove protected-top interruption risks.'),
    'check_wdcmonv2_archive.ps1': ('Archive RAM image checker', 'Validates the project archive program image and its contract. Archive utility validity and validity of a particular captured archive are separate checks.'),
    'requirements-test.txt': ('Optional opcode-test dependency', 'Pins py65 for actual-opcode host tests. Basic host checks and physical-board qualification are separate dependencies and processes.'),
    'str8n-public.inc': ('Generated current public integration contract', 'Current existing generated include, included as a contract cross-check. It must be regenerated alongside changed ABI inputs; generated output is not an independent source of truth.'),
}


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def anchor(path):
    return 'file-' + re.sub(r'[^a-z0-9]+', '-', str(path).lower()).strip('-')


def profiles(path):
    base = {k: int(k in RELEASE_FLAGS) for k in KNOWN_FLAGS}
    def p(name, **values):
        return name, dict(base, **values)
    if path.name == 'str8n-v1.23-bank-maint-2000.asm':
        return [p('standalone'), p('menu', STR8_BANK_MAINT_TOP=1, STR8_TOP_EMBED=1), p('iN65', STR8_IN65_BANK_MAINT=1)]
    if path.name == 'str8n-v1.23-bank-maint-rename.inc':
        return [p('standalone'), p('menu', STR8_BANK_MAINT_TOP=1), p('iN65', STR8_IN65_BANK_MAINT=1)]
    if path.name == 'str8n-v1.23-top-update-2000.asm':
        return [p('ordinary'), p('refresh', STR8_DIRECTORY_REFRESH=1), p('embedded', STR8_TOP_EMBED=1), p('iN65', STR8_IN65_TOP_IMAGE=1)]
    if path.name == 'wdcmonv2str8n-install-2000.asm':
        return [p('migration'), p('iN65', W2I_STR8_IN65_IMAGE=1), p('stock restore', W2I_RESTORE_STOCK=1)]
    return [p('production')]


def select_lines(path):
    lines = path.read_text(encoding='utf-8-sig').splitlines()
    if path.suffix not in {'.asm', '.inc'}:
        return list(enumerate(lines, 1)), [], ['current file']
    included = set()
    directives = set()
    for _, flags in profiles(path):
        stack = []
        active = True
        for n, line in enumerate(lines, 1):
            code = line.split(';', 1)[0].strip()
            cond = re.fullmatch(r'IF\s+(\w+)', code, re.I)
            if cond:
                name = cond.group(1)
                if name not in flags:
                    raise ValueError(f'Unknown build condition {path}:{n}: {name}')
                directives.add(n)
                stack.append((active, bool(flags[name])))
                active = active and bool(flags[name])
            elif code.upper() == 'ELSE':
                directives.add(n)
                parent, decision = stack[-1]
                active = parent and not decision
            elif code.upper() == 'ENDIF':
                directives.add(n)
                active, _ = stack.pop()
            elif active:
                included.add(n)
                equ = re.fullmatch(r'(\w+)\s+EQU\s+([01])', code, re.I)
                if equ and equ.group(1) in flags:
                    flags[equ.group(1)] = int(equ.group(2))
        if stack:
            raise ValueError(f'Unclosed conditional in {path}')
    # Preserve directives as context even when branch bodies are omitted.
    included |= directives
    omitted = []
    selected = []
    for n, line in enumerate(lines, 1):
        if re.match(r'^\s*;\s*20\d\d-\d\d-\d\d', line):
            omitted.append({'line': n, 'reason': 'dated change-log comment'})
        elif n not in included:
            omitted.append({'line': n, 'reason': 'outside selected current profiles'})
        else:
            selected.append((n, line))
    return selected, omitted, [name for name, _ in profiles(path)]


def symbols(path, lines):
    found = []
    for n, line in lines:
        name = None
        if path.suffix in {'.asm', '.inc'}:
            # Nonindented global labels/constants, with or without a colon.
            m = re.match(r'^([A-Za-z_][\w]*)(?=[:\s]|$)', line)
            if m and m.group(1).upper() not in {'IF', 'ELSE', 'ENDIF', 'INCLUDE', 'END'}:
                name = m.group(1)
        elif path.suffix == '.py':
            m = re.match(r'^(?:async )?(?:def|class)\s+(\w+)', line)
            if m:
                name = m.group(1)
        elif path.suffix == '.ps1':
            m = re.match(r'^function\s+([\w-]+)', line, re.I)
            if m:
                name = m.group(1)
        elif path.name == 'Makefile':
            m = re.match(r'^([a-z][a-z0-9_-]*):', line)
            if m:
                name = m.group(1)
        if name:
            found.append((name, n))
    return found


def file_set():
    selected = [ROOT / 'Makefile'] + sorted((ROOT / 'src').glob('*'))
    excluded = []
    for path in sorted((ROOT / 'tools').rglob('*')):
        if not path.is_file() or '__pycache__' in path.parts:
            continue
        rel = path.relative_to(ROOT / 'tools').as_posix()
        if path.name == Path(__file__).name:
            continue  # Book tooling is editorial machinery, not STR8-N product code.
        if path.suffix in {'.ps1', '.py'} or rel in CURRENT_ASSEMBLY or path.name == 'requirements-test.txt':
            selected.append(path)
        elif path.suffix in {'.asm', '.inc', '.a', '.json'}:
            reason = 'superseded wrapper/probe source outside current Makefile selection'
            if path.suffix == '.a':
                reason = 'generated encoded image carrier; maintained generator and ASM listed'
            if path.suffix == '.json':
                reason = 'current regression fixture dependency; encoded reference data inventoried only'
            excluded.append({'path': path.relative_to(ROOT).as_posix(), 'sha256': digest(path), 'reason': reason})
    contract = RELEASE / 'include/str8n-public.inc'
    if contract.exists():
        selected.append(contract)
    return selected, excluded


def make_markdown():
    make = (ROOT / 'Makefile').read_text()
    match = re.search(r'^RELEASE_DEFINES\s*:=\s*(.*)$', make, re.M)
    actual = set(re.findall(r'-D(\w+)', match.group(1)))
    if actual != RELEASE_FLAGS or not re.search(r'^VERSION\s*:=\s*v1\.35\s*$', make, re.M):
        raise ValueError('Release selection changed; review chapters and profiles before regenerating.')
    paths, excluded = file_set()
    manifest = {'edition': STEM, 'generated_utc': datetime.now(timezone.utc).isoformat(),
                'basis': 'current local working tree, not git history', 'release_defines': sorted(actual),
                'editorial_sha256': digest(EDITORIAL),
                'atlas_sha256': digest(ROOT / 'docs/book/code_diagrams.py'),
                'worker_reference_sha256': digest(ROOT / 'docs/book/worker_reference.py'),
                'files': [], 'inventory_only': excluded}
    book = EDITORIAL.read_text(encoding='utf-8').rstrip() + '\n\n'
    book += atlas_text()
    workers, worker_report = worker_text(ROOT)
    book += workers
    manifest['private_worker_disassembly'] = worker_report
    book += '## 24. Source catalog and reading profiles\n\n'
    book += 'Each catalog link leads to a listing with original source line numbers. File hashes cover the original complete file bytes, not the filtered display. Listings are grouped by file, not flattened includes. Shared-source conditional branches are the union of supported current profiles; use the Makefile and wrappers to select an executable variant.\n\n'
    book += '| File | Purpose | Lines displayed / original |\n|---|---|---|\n'
    listing = []
    index = [(name, 'private mutation worker', address, 'worker-annotated')
             for address, (name, _) in WORKER_ROUTINES.items()]
    for path in paths:
        rel = path.relative_to(ROOT).as_posix()
        if path.name not in CARDS:
            raise ValueError(f'No editorial coverage for {rel}')
        title, notes = CARDS[path.name]
        selected, omitted, builds = select_lines(path)
        count = len(path.read_text(encoding='utf-8-sig').splitlines())
        aid = anchor(rel)
        manifest['files'].append({'path': rel, 'sha256': digest(path), 'original_lines': count,
                                  'displayed_lines': len(selected), 'profiles': builds, 'omissions': omitted})
        book += f'| [{rel}](#{aid}) | {title} | {len(selected)} / {count} |\n'
        syms = symbols(path, selected)
        index.extend((s, rel, n, aid) for s, n in syms)
        block = f'\n<a id="{aid}"></a>\n\n## Listing: {rel}\n\n**{title}.** {notes}\n\n'
        block += f'Profiles: {", ".join(builds)}. Original: {count} lines; displayed: {len(selected)}; omitted: {len(omitted)}.\n\n'
        block += f'SHA-256: `{digest(path)}`\n\n'
        if syms:
            block += 'Named entry points, constants, or functions (source line):\n\n'
            block += '; '.join(f'`{s}` {n}' for s, n in syms) + '.\n\n'
        block += '```text\n'
        previous = 0
        for n, line in selected:
            if n > previous + 1:
                block += f'      [... source lines {previous+1}-{n-1} omitted; see coverage manifest ...]\n'
            block += f'{n:5d} | {line.expandtabs(4)}\n'
            previous = n
        if previous < count:
            block += f'      [... source lines {previous+1}-{count} omitted; see coverage manifest ...]\n'
        block += '```\n'
        listing.append(block)
    book += '\n## 25. Coverage, exclusions, and artifact identity\n\n'
    total = sum(f['displayed_lines'] for f in manifest['files'])
    book += f'This edition lists {len(paths)} source/contract files and {total:,} displayed source lines. `coverage-manifest.json` gives original SHA-256 hashes and a reason for each omitted assembly line. The following inventory documents excluded duplicate outputs and retained test data without reproducing their payloads. No source history was queried.\n\n'
    book += '| Inventory-only path | Reason |\n|---|---|\n'
    for item in excluded:
        book += f'| {item["path"]} | {item["reason"]} |\n'
    book += '\nExisting current build artifacts are cross-checks only; they were not rebuilt for this edition. Full hashes are in the manifest. Generated image includes encode candidate bytes and are inventoried rather than duplicating the binary as source commentary.\n\n'
    manifest['artifact_cross_checks'] = []
    artifacts = list((RELEASE / 'bin').glob('str8n-v1.35*.bin'))
    artifacts += list((RELEASE / 'generated').glob('*.inc'))
    artifacts += [RELEASE / 'map/str8n-v1.35-f000.map', RELEASE / 'map/str8n-v1.35-worker-0200.map']
    book += '| Existing artifact | Bytes | SHA-256 prefix (full value in manifest) |\n|---|---:|---|\n'
    for path in sorted(artifacts):
        if not path.exists():
            continue
        item = {'path': path.relative_to(ROOT).as_posix(), 'bytes': path.stat().st_size, 'sha256': digest(path)}
        manifest['artifact_cross_checks'].append(item)
        book += f'| {item["path"]} | {item["bytes"]} | {item["sha256"][:20]} |\n'
    book += '\n## 26. Alphabetical symbol index\n\n'
    book += 'Global assembly labels/constants, top-level Python definitions, PowerShell functions, and simple named Makefile targets. Source line numbers refer to original files. Repeated names are qualified by their file; local question-mark labels are intentionally omitted.\n\n'
    book += 'MW_ names are editorial labels for the derived private-worker disassembly; their locations are RAM execution addresses, not source line numbers.\n\n'
    for name, rel, n, aid in sorted(index, key=lambda v: (v[0].lower(), v[1], v[2])):
        location = f'RAM ${n:04X}' if rel == 'private mutation worker' else f'line {n}'
        book += f'- `{name}` - [{rel}, {location}](#{aid})\n'
    book += '\n## 27. Current source listings\n\n'
    book += 'Listings follow the source catalog order. Comments describe the source author\'s contract; explanatory chapters call out known mismatches. The original files remain unchanged. Dated change-log comment lines and inactive assembly bodies are omitted with explicit line-gap markers. Other technical comments remain verbatim, including incidental compatibility references.\n'
    book += ''.join(listing)
    manifest['summary'] = {'listed_files': len(paths), 'displayed_lines': total, 'symbols': len(index)}
    return book, manifest


def make_html(book):
    body = markdown.markdown(book, extensions=['tables', 'fenced_code', 'toc'], output_format='html5')
    for key, chart in CHARTS.items():
        svg = renderSVG.drawToString(chart.draw())
        svg = svg[svg.index('<svg'):]
        for svg_id in set(re.findall(r'\bid="([^"]+)"', svg)):
            svg = svg.replace(f'id="{svg_id}"', f'id="atlas-{key}-{svg_id}"')
            svg = svg.replace(f'url(#{svg_id})', f'url(#atlas-{key}-{svg_id})')
            svg = svg.replace(f'href="#{svg_id}"', f'href="#atlas-{key}-{svg_id}"')
        svg = svg.replace('<svg ', f'<svg role="img" aria-label="{html.escape(key)}" ', 1)
        body = body.replace(f'<p>:::diagram {key}:::</p>', f'<figure class="diagram">{svg}</figure>')
    headings = re.findall(r'<h2 id="([^"]+)">(.*?)</h2>', body)
    nav = ''.join(f'<a href="#{html.escape(i)}">{t}</a>' for i, t in headings)
    css = '''
    :root{color-scheme:light;--ink:#173044;--accent:#087f8c}*{box-sizing:border-box}
    body{margin:0;color:#20313d;background:#f7f8f8;font:17px/1.65 Georgia,serif}
    nav{position:fixed;width:285px;inset:0 auto 0 0;overflow:auto;padding:26px 18px;background:#173044;color:white;font:13px/1.4 system-ui}
    nav a{display:block;color:#e2eff3;margin:11px 0;text-decoration:none;overflow-wrap:anywhere}
    nav strong{font-size:18px}main{margin-left:285px;max-width:1180px;padding:42px 55px 100px;background:white}
    h1,h2,h3{font-family:system-ui;line-height:1.25;color:var(--ink);overflow-wrap:anywhere}
    h1{font-size:42px;border-bottom:6px solid var(--accent);padding-bottom:26px}h2{margin-top:60px;font-size:27px;scroll-margin-top:25px}
    a{color:#066e82}p,li,td{overflow-wrap:anywhere}code{font:13px/1.5 Consolas,monospace;color:#314956}
    pre{padding:20px;background:#f0f4f5;border-left:3px solid var(--accent);overflow:auto;tab-size:4}
    pre code{font-size:12px;white-space:pre}table{border-collapse:collapse;width:100%;font:14px/1.5 system-ui;margin:22px 0}
    th,td{padding:9px 11px;border:1px solid #d7e0e3;vertical-align:top;text-align:left}th{background:#e7eff1}
    .hint{font:14px/1.5 system-ui;color:#526977}button{padding:8px 12px;cursor:pointer}
    .diagram{margin:24px 0;padding:16px;background:#fff;border:1px solid #d7e0e3}
    .diagram svg{display:block;width:100%;height:auto;max-width:850px;margin:auto}
    @media(max-width:800px){nav{position:relative;width:100%;max-height:260px}main{margin:0;padding:25px}}
    @media print{nav,.hint{display:none}main{margin:0;max-width:none;padding:0}pre{white-space:pre-wrap}pre code{white-space:pre-wrap;font-size:8px}h2{break-before:page}a{color:inherit}}
    '''
    return f'<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{STEM}</title><style>{css}</style></head><body><nav><strong>STR8-N 1.35<br>Current Code Reference</strong>{nav}</nav><main><p class="hint">Offline reference. Use Ctrl+F to search all chapters and listings. Source numbers are original file lines.</p>{body}</main></body></html>'


def inline(text):
    text = html.escape(text)
    text = re.sub(r'`([^`]+)`', lambda m: '<font name="Courier" size="8">' + m.group(1) + '</font>', text)
    text = re.sub(r'\*\*([^*]+)\*\*', r'<b>\1</b>', text)
    text = re.sub(r'\[([^\]]+)\]\((#[^)]+)\)', r'<link href="\2" color="#066e82">\1</link>', text)
    text = re.sub(r'\[([^\]]+)\]\(([^)]+)\)', r'\1', text)
    return text


class BookPDF(BaseDocTemplate):
    def __init__(self, path):
        super().__init__(str(path), pagesize=(612, 792), rightMargin=42, leftMargin=42,
                         topMargin=48, bottomMargin=45, title='STR8-N 1.35 - Current Code Reference',
                         author='STR8-N source reference', allowSplitting=1)
        self.addPageTemplates(PageTemplate(id='book', frames=[Frame(42, 45, 528, 699, leftPadding=0, rightPadding=0, topPadding=0, bottomPadding=0)], onPage=self.decorate))
        self.headings = []

    def beforeDocument(self):
        self.headings = []

    def decorate(self, canv, doc):
        canv.saveState()
        canv.setStrokeColor(colors.HexColor('#bfd0d7'))
        canv.line(42, 758, 570, 758)
        canv.setFont('Helvetica', 8)
        canv.setFillColor(colors.HexColor('#476170'))
        canv.drawString(42, 767, 'STR8-N 1.35  /  CURRENT CODE REFERENCE')
        canv.drawString(42, 27, 'Current working-tree edition - code, contracts, and considerations')
        canv.drawRightString(570, 27, str(doc.page))
        canv.restoreState()

    def afterFlowable(self, flowable):
        if isinstance(flowable, Paragraph) and flowable.style.name == 'BookH2':
            title = flowable.getPlainText()
            key = 'section-' + hashlib.sha256(title.encode()).hexdigest()[:16]
            self.canv.bookmarkPage(key)
            if title.startswith('Listing: '):
                self.canv.bookmarkPage(anchor(title[len('Listing: '):]))
            if title == 'Annotated listing: private mutation worker':
                self.canv.bookmarkPage('worker-annotated')
            self.canv.addOutlineEntry(title, key, 0, False)
            self.notify('TOCEntry', (0, title, self.page, key))
            self.headings.append({'title': title, 'page': self.page})


def make_pdf(book):
    styles = getSampleStyleSheet()
    body = ParagraphStyle('BookBody', fontName='Helvetica', fontSize=9.4, leading=13.5,
                          textColor=colors.HexColor('#253a47'), spaceAfter=9, splitLongWords=True)
    h1 = ParagraphStyle('BookH1', parent=styles['Title'], fontSize=31, leading=38, textColor=colors.HexColor('#173044'), spaceAfter=24)
    h2 = ParagraphStyle('BookH2', fontName='Helvetica-Bold', fontSize=17, leading=22,
                        textColor=colors.HexColor('#173044'), spaceAfter=13, splitLongWords=True)
    mono = ParagraphStyle('Code', fontName='Courier', fontSize=7, leading=9,
                          textColor=colors.HexColor('#243d4b'), spaceAfter=10)
    cell = ParagraphStyle('Cell', parent=body, fontSize=7.3, leading=10, spaceAfter=0)
    tiny = ParagraphStyle('Index', parent=body, fontSize=7.5, leading=10, spaceAfter=3)
    toc = TableOfContents()
    toc.levelStyles = [ParagraphStyle('Contents', fontName='Helvetica', fontSize=9, leading=12, spaceBefore=5, rightIndent=25)]
    story = [Spacer(1, 88), Paragraph('STR8-N 1.35', h1), Paragraph('Current Code Reference', h1),
             Paragraph('Resident firmware, RAM tools, build system, host utilities, interfaces, reasons, exceptions, and limitations.', body),
             Spacer(1, 22), Paragraph('A current-source edition with numbered listings and a coverage manifest. No development chronology.', body),
             Spacer(1, 20), Paragraph('Read the explanatory chapters first. Use the clickable contents and PDF bookmarks to reach a file listing. Use document search for a symbol or source filename.', body),
             PageBreak(), Paragraph('Contents', h1), toc, PageBreak()]
    lines = book.splitlines()
    i = 0
    in_index = False
    while i < len(lines):
        line = lines[i]
        if not line.strip() or line.startswith('<a ') or line.startswith('# '):
            i += 1
            continue
        if line.startswith('## '):
            title = line[3:]
            if story and not isinstance(story[-1], PageBreak):
                story.append(PageBreak())
            story.append(Paragraph(html.escape(title), h2))
            in_index = title.startswith('26.')
            i += 1
            continue
        if line.startswith(':::diagram '):
            key = line[len(':::diagram '):-3]
            story.extend([CHARTS[key].draw(), Spacer(1, 12)])
            i += 1
            continue
        if line.startswith('```'):
            raw = []
            i += 1
            while i < len(lines) and not lines[i].startswith('```'):
                # Visible continuation indentation keeps original source numbers unambiguous.
                wrapped = textwrap.wrap(lines[i], width=122, subsequent_indent='        > ',
                                        replace_whitespace=False, drop_whitespace=False, break_long_words=True, break_on_hyphens=False) or ['']
                raw.extend(wrapped)
                i += 1
            story.append(Preformatted('\n'.join(raw), mono))
            i += 1
            continue
        if line.startswith('|'):
            rows = []
            while i < len(lines) and lines[i].startswith('|'):
                values = lines[i].strip().strip('|').split('|')
                if not all(re.fullmatch(r'\s*:?-+:?\s*', x) for x in values):
                    rows.append([Paragraph(inline(x.strip()), cell) for x in values])
                i += 1
            cols = len(rows[0])
            widths = [528 / cols] * cols
            if cols == 3:
                widths = [210, 230, 88] if 'File' in rows[0][0].getPlainText() else [200, 105, 223]
            table = LongTable(rows, colWidths=widths, repeatRows=1, hAlign='LEFT')
            table.setStyle(TableStyle([
                ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#e4eef1')),
                ('GRID', (0,0), (-1,-1), .3, colors.HexColor('#b8ccd3')),
                ('VALIGN', (0,0), (-1,-1), 'TOP'),
                ('LEFTPADDING', (0,0), (-1,-1), 6), ('RIGHTPADDING', (0,0), (-1,-1), 6),
                ('TOPPADDING', (0,0), (-1,-1), 5), ('BOTTOMPADDING', (0,0), (-1,-1), 5),
            ]))
            story.extend([table, Spacer(1, 12)])
            continue
        if line.startswith('- '):
            story.append(Paragraph(inline(line[2:]), tiny if in_index else body, bulletText='-'))
            i += 1
            continue
        para = [line]
        i += 1
        while i < len(lines) and lines[i].strip() and not lines[i].startswith(('## ', '```', '|', '- ', '<a ')):
            para.append(lines[i])
            i += 1
        text = ' '.join(para)
        # Long symbol lists are broken into paragraphs to permit page splitting.
        if len(text) > 2500 and '; ' in text:
            chunks = text.split('; ')
            for start in range(0, len(chunks), 16):
                story.append(Paragraph(inline('; '.join(chunks[start:start+16])), tiny))
        else:
            story.append(Paragraph(inline(text), body))
    doc = BookPDF(PDFOUT / f'{STEM}.pdf')
    doc.multiBuild(story)
    return doc.headings


def validate_and_render(book, manifest, headings):
    # Every displayed source line must be present with its original number and text.
    for item in manifest['files']:
        path = ROOT / item['path']
        assert digest(path) == item['sha256'], f'Source changed during generation: {path}'
        selected, _, _ = select_lines(path)
        for n, text in selected:
            assert f'{n:5d} | {text.expandtabs(4)}\n' in book
    output_html = (OUT / f'{STEM}.html').read_text(encoding='utf-8')
    ids = re.findall(r'\bid="([^"]+)"', output_html)
    assert len(ids) == len(set(ids)), 'Duplicate HTML anchors'
    for target in re.findall(r'href="#([^"]+)"', output_html):
        assert target in ids, f'Broken internal link: {target}'
    assert output_html.count('<svg ') == len(CHARTS)
    assert ':::diagram' not in output_html
    report = {'source_hashes': 'pass', 'displayed_source_lines': 'pass', 'html_internal_links': 'pass',
              'firmware_rebuilt': False, 'hardware_contacted': False,
              'vector_diagrams': len(CHARTS), 'html_inline_svg': 'pass'}
    report['private_worker_disassembly'] = manifest['private_worker_disassembly']
    try:
        import pypdfium2 as pdfium
    except ImportError:
        report['pdf_render'] = 'unavailable: install pypdfium2 for visual review'
        return report
    pdf = pdfium.PdfDocument(str(PDFOUT / f'{STEM}.pdf'))
    report['pdf_pages'] = len(pdf)
    atlas_headings = [h for h in headings if h['title'].startswith('Atlas ')]
    assert len(atlas_headings) == len(CHARTS)
    for heading, chart in zip(atlas_headings, CHARTS.values()):
        page = pdf[heading['page']-1]
        textpage = page.get_textpage()
        extracted = re.sub(r'\s+', '', textpage.get_text_range())
        for node in chart.nodes.values():
            expected = re.sub(r'\s+', '', node.text)
            assert expected in extracted, f'PDF diagram text missing: {heading["title"]}: {node.key}'
        textpage.close()
        page.close()
    report['pdf_diagram_text_search'] = 'pass'
    worker_heading = next(h for h in headings if h['title'] == 'Annotated listing: private mutation worker')
    following_page = next(h['page'] for h in headings if h['page'] > worker_heading['page'])
    worker_pdf_text = ''
    for n in range(worker_heading['page']-1, following_page-1):
        page = pdf[n]
        textpage = page.get_textpage()
        worker_pdf_text += textpage.get_text_range()
        textpage.close()
        page.close()
    rows = re.findall(r'(?m)^([0-9A-F]{4}) \| ([0-9A-F]{4}) \| ([0-9A-F ]+?) \|', book)
    assert len(rows) == manifest['private_worker_disassembly']['decoded_instructions'] + 2
    for ram, stored, data in rows:
        prefix = re.sub(r'\s+', '', f'{ram} | {stored} | {data} |')
        assert prefix in re.sub(r'\s+', '', worker_pdf_text), f'PDF disassembly row missing: {ram}'
    report['pdf_disassembly_rows'] = 'pass: all instruction and data rows searchable'
    # Extract each page to confirm readable content, and sample key content categories.
    empty = []
    for n in range(len(pdf)):
        page = pdf[n]
        textpage = page.get_textpage()
        if len(textpage.get_text_range().strip()) < 40:
            empty.append(n+1)
        textpage.close()
        page.close()
    assert not empty, f'Unexpected empty PDF pages: {empty}'
    review = ROOT / 'tmp/pdfs/current-code-book'
    review.mkdir(parents=True, exist_ok=True)
    wanted = [1, 2]
    for heading in headings:
        if heading['title'].startswith('Atlas '):
            wanted.append(heading['page'])
        if heading['title'] == 'Annotated listing: private mutation worker':
            wanted.extend([heading['page'], heading['page']+2, heading['page']+4])
    for phrase in ('1. Scope', '3. Flash', '24. Source', '26. Alphabetical', 'Listing: src/str8.asm', 'Listing: tools/bank-maint/str8n-v1.23-bank-maint-2000.asm', 'Listing: tools/verify_release_package.ps1'):
        match = next((h for h in headings if h['title'].startswith(phrase)), None)
        if match:
            wanted.append(match['page'])
            if phrase.startswith('Listing:'):
                wanted.append(min(match['page']+2, len(pdf)))
    wanted.append(len(pdf))
    samples = []
    for n in sorted(set(wanted)):
        page = pdf[n-1]
        bitmap = page.render(scale=1.35)
        image_path = review / f'page-{n:04}.png'
        bitmap.to_pil().save(image_path)
        bitmap.close()
        page.close()
        samples.append(str(image_path.relative_to(ROOT)))
    pdf.close()
    report['rendered_samples'] = samples
    report['pdf_text_pages'] = 'pass'
    return report


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    PDFOUT.mkdir(parents=True, exist_ok=True)
    book, manifest = make_markdown()
    (OUT / f'{STEM}.html').write_text(make_html(book), encoding='utf-8')
    (OUT / 'coverage-manifest.json').write_text(json.dumps(manifest, indent=2), encoding='utf-8')
    headings = make_pdf(book)
    (OUT / 'pdf-sections.json').write_text(json.dumps(headings, indent=2), encoding='utf-8')
    report = validate_and_render(book, manifest, headings)
    (OUT / 'validation.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    print(json.dumps({'coverage': manifest['summary'], 'validation': report}, indent=2))


if __name__ == '__main__':
    main()
