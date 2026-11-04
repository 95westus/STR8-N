# Mona: optional monitor direction

Mona is the chosen name for a future BASE1-compatible monitor or launcher.
It is separate from STR8N-F, and no Mona binary is included in 0.3.0.

STR8N-F stays the frozen 4096-byte bootstrap/recovery foundation. Mona may
show richer board/service status, offer application and subsystem menus,
hand over to an application, or deliberately return to recovery. Missing
optional hardware must be reported as unavailable. Mona owns its own name,
version and generation; these do not change F's identity or journal sequence.

MON A and MON B can provide different personalities. The current A/B boot
path requires the existing monitor image header, CRC and PR05 contract;
the labels do not make an arbitrary opaque image monitor-compatible.
Ordinary opaque images boot through a configured bank entry. The retained
g0034 monitor's ABI and provider dependencies still need review before it
can be used under BASE1.

Trees such as Applications / Hardware / Maintenance belong in Mona or another
optional image. LED, buzzer, SPI workspace/message services and additional
service discovery remain proposed extensions, not additions to the 0.3.0
F ABI. Implementations must be qualified separately.
