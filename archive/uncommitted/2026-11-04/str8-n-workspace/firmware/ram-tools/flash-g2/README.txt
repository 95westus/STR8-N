FLASH g2 loadable RAM tool for N-F 0.3.0 BASE1/PR05.
Load FLASH.bin as raw binary at $0200 using recovery L; it starts automatically.
Alternatively load at $0200 through a compatible MON loader and run R.
Includes its dense S19 library; requires no stored FLASH or MAINT copy.
Q restarts F using the saved boot policy. Borrowed application RAM is not restored.
RAM code/library: $0200-$4544; tool state and flash buffer also borrow high RAM.
FLASH supports writes/erases; inspect target bank/range and confirmation.
MAINT-RO.bin is the separate read-only $0200 maintenance tool.
Only the F hash in manifest.json is admitted by this package.
