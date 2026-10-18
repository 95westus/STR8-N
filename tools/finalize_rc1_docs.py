"""Finalize version-correct public manuals and a short repository README."""
import re,shutil
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def main():
    archive=ROOT/'output/qualification/rc1-original-main-README.md';assert not archive.exists();shutil.copyfile(ROOT/'README.md',archive)
    (ROOT/'README.md').write_text('''# STR8-N

STR8-N is a monitor, assembler and utility system for WDC SXB boards, using
one firmware set for **65C02 and 65C816 emulation-mode runtime**.

**[Download v2.0rc1 — one complete release ZIP](https://github.com/95westus/STR8-N/releases/download/v2.0rc1/str8n-v2.0rc1-release.zip)**

Includes the full-system BIN, B3 boot/core BIN, MON A/B/F components, all apps
and S/R/T, Windows/Linux migration and recovery tools, manuals/quick starts,
public ABIs/diagrams, and credited uChess source with an ASM/S/T/R example.

- [Quick start](docs/rc1/QUICK_START.md) · [Migration/recovery](docs/rc1/QUICK_START_MIGRATION.md) · [All manuals](docs/rc1/README.md)
- [Firmware layouts](docs/rc1/RELEASE_PATHS.md) · [Reproducible rc1 source build](release/candidates/rc1/README.md)
- [Published beta4 archive and instructions](https://github.com/95westus/STR8-N/releases/tag/v2.0b4) · [Previous bf1](https://github.com/95westus/STR8-N/releases/tag/v2.0bf1)

Scripted migration admits the exact supported WDCMONV2 or published beta4
source in B3 with erased B0/B1/B2; read the guide before installing. No vendor
firmware or private board data is distributed. Raw BINs are provisioning images.

rc1 is source-built and verified offline, retaining bf1 hardware-engine evidence.
RTC qualification/known continuity issue, native 816 apps/tests, ACIA and crypto
are deferred. Soaks and RTC sampling remain stopped; recorded soak results are
accepted as recorded, without claiming full endurance qualification.
''',encoding='utf-8')
    docs=ROOT/'docs/rc1'
    for p in docs.glob('*.md'):
        s=p.read_text(encoding='utf-8').replace('release/candidates/batchfix-r1/','release/candidates/rc1/')
        s=re.sub(r"Current acceptance policy and tonight's prerelease scope:.*\n",'Release scope and limitations: [rc1 qualification](README.md#rc1-qualification).\n',s)
        s=s.replace('One generation-49 STR8-N','One generation-49 STR8-N')
        s=s.replace('The separate documentation ZIP provides installed-board and migration quick\nstarts','This complete release ZIP provides installed-board and migration quick\nstarts').replace('from the matching Windows\nor Linux migration package','from this ZIP using the Windows\nor Linux launchers')
        s=s.replace('Matching Windows or Linux migration package','Windows/Linux launchers in this ZIP')
        s=s.replace('The complete full-system empty-bank\nmigrations were tested on physical 65C02 and 65C816 boards.','The prior bf1 full-system empty-bank\nmigrations were tested on physical 65C02 and 65C816 boards; rc1 is verified offline.')
        s=s.replace('22 transfers, rc1 boot and UCHESS/BATCH checks.','22 transfers, bf1 boot and UCHESS/BATCH checks. rc1 targets are tested offline.')
        if p.name=='TECHNICAL_MANUAL.md':
            start=s.index('The proven 2604 source route');end=s.index('## RTC, outages and measurement limits')
            s=s[:start]+'''The inherited bf1 engine has physical shared-CPU and exact-source empty-bank
migration evidence. The rc1 target changes only the monitor identity,
generation and dependent CRCs. Fresh CPU/flash execution covers both full
22-transfer routes, late factory forward recovery, interrupted beta4 forward
recovery and restoration of the captured beta4 payload while retaining newer
wear history. The same common transport is exercised on Windows and Linux
with simulated endpoints; these are software tests, not new hardware installs.

Recovery requires the exact original kit, backup and replayable mutation
lineage. It preserves newer sequences/counts and refuses unknown partial
programming. Complete clean targets produce a no-write receipt. A late failure
does not imply rollback. Early WDC cuts lacking a valid STR8-N fallback/journal
can require an external programmer and the original private source backup.

'''+s[end:]
            start=s.index('The qualified evidence is tied');end=s.index('The same firmware supports',start)
            s=s[:start]+'''rc1 is a scoped release candidate with source-build, CPU/flash model,
manual/ABI and extracted-platform software verification. Prior bf1 hardware
proofs are retained by version; no new rc1 hardware installation is claimed.
Live migration admits only the exact supported SXB6 WDC source or published
beta4 with erased B0/B1/B2. Native 816 applications/tests, ACIA and crypto are
deferred. RTC qualification and the known continuity issue are deferred.
Soaks and RTC sampling remain stopped; the owner accepted recorded results
without claiming the longer endurance or seven-day RTC gates passed.

Source contracts are in `release/candidates/rc1/source/assembler/str8n-v2-public.inc`,
`core/service-eq.inc` and `core/str8n-v2-eq.inc`; build with the candidate's
`build.py`. See [ABI tables](ABI_REFERENCE.md), [migration/recovery](MIGRATION_RECOVERY.md)
and [image maps](RELEASE_PATHS.md).

'''+s[end:]
        if p.name=='README.md':s=s.replace('## Tested candidate scope','## Inherited bf1 hardware scope')
        if p.name=='OPERATOR_GUIDE.md':s=s.replace('## Run a preserving campaign','## Run a preserving campaign\n\nThe current owner-stopped soaks and RTC sampling remain stopped. The following\nis a procedure for a separately authorized future campaign, not a restart instruction.')
        p.write_text(s,encoding='utf-8')
    print('Finalized short main README and rc1 manuals with accurate stopped/deferred and hardware/model scope')
if __name__=='__main__':main()
