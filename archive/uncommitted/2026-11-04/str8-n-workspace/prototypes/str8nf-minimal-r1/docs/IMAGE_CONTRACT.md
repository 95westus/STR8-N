# Opaque image contract

An opaque image supplies its own code, data and interface. F selects its
physical bank and jumps to the saved entry. It does not interpret BASIC,
Forth, filesystem metadata or an application's internal directory.

The image manifest should state CPU/mode, physical bank and allocated sectors,
load/entry address, length, SHA-256, required devices/services, borrowed RAM and
return behavior. Banks are 0-3. Entries are 8000-E000 in 1000 steps;
B3:C000/D000 are excluded, and F000 is not a user entry.

Code must account for bank overlays. A jump does not relocate absolute addresses
or supply an ABI. The supported 816 path is emulation mode, PBR/DBR/D zero.
The matching public source includes define F's RAM facade and reserved memory.
Applications must respect those areas when using F services.

Use saved default S during initial trials. Reset through F uses the saved
default again, possibly launching the same application. The FLASH example
implements a deliberate validated MON return. A BIN alone does not imply a
particular return contract.

Install and verify all image sectors before enabling the entry. CONFIG does
not inspect code, know its span or validate device requirements. One saved
entry exists per bank; multiple applications need their own launcher.

B0/B1/B2 remain user-owned in the N/F profile. Optional B3 services and owner
backups still require inventory before target selection. Untagged bytes are
not necessarily reclaimable; erased bytes do not cancel an owner's reservation.

Existing g0034/full-system images assume their own bank/service layouts.
An opaque personality needs a port and an explicit memory/entry/return contract.
This release does not supply that port.
