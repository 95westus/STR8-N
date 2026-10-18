# STR8-N 2.0rc1 source build

Build from this directory alone with Python 3.10+, WDC02AS and WDCLN:

```text
python build.py --out C:\tmp\rc1build
```

Use a fresh short output path. This candidate advances the monitor banner to
2.0rc1 and both monitor descriptors to generation 49. All other linked payloads
must match the source-built bf1 baseline, except the package-revision-2 RTC
banner correction: `[power-fail UTC]` identifies the raw event timestamps.
The failure-message wording is four bytes shorter to preserve every helper
address. No clock, RTC policy, trim or event-handling code changes. No board
access is performed.
The release ZIP contains the complete firmware and user tools; this source
directory is for reproducibility. RTC, native 816 apps/tests, ACIA and crypto
are deferred. The startup CPU detector exception is retained.
