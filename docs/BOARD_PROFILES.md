# Optional local board labels

The terminal has no embedded board inventory. It lists available serial ports
without opening them. Without a profile, USB identity is shown as unknown.
F10 still opens the selected port; selecting a profile never connects or probes.

Create a private JSON file outside the source or kit directory. Its object maps
each adapter serial to [board label, CPU label]. For example, using synthetic
identifiers only:

```json
{"EXAMPLE_ADAPTER_A": ["Lab A", "65C02"], "EXAMPLE_ADAPTER_B": ["Lab B", "65C816 emulation"]}
```

```powershell
python tools/nf_console.py --board-profiles path/to/local-profiles.json
# In a built kit:
python str8n-terminal.py --board-profiles path/to/local-profiles.json
```

Profile labels describe an adapter assignment; they do not detect the connected
CPU. --board sets a manual label. A matching profile label can supply its CPU
description; any other manual label has no inferred CPU. A live connection keeps
its active port identity until disconnect even when the selector changes.

Do not include local profile files in a release, source export or support bundle.
The supplied tests use synthetic identities and a fake worker and open no ports.
