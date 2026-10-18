# Reproduce the rc1 BINs

First build the source-only candidate into a fresh short directory:

```text
python release/candidates/rc1/build.py --out C:\tmp\rc1build
python release/rc1-build/build_release_images.py --payload C:\tmp\rc1build\payload --reference C:\tmp\rc1build\build-report.json --uchess-record release/rc1-migration-r1/applications/uchess-record.bin --out C:\tmp\rc1images
```

The unchanged UCHESS executable/record is supplied with complete credited source
and its original license under `release/rc1-uchess`. It was assembled from
`uchess.a` with the actual ASM 0.5 instructions in both monitor-slot models.
The complete user ZIP includes the same sources, license and ASM/S/T/R walkthrough.
No vendor firmware or device capture is an image-composition input.
