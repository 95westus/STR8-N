# STR8-N cross-bank RAM ABI test

Build alpha21 with `make v2`, then load
`BUILD/v2-alpha21/str8n-v2-alpha21-ram-abi-test-2000.s19` with `L` and run
`G 2000`. The test changes no flash.

It checks the fixed RAM descriptor, prints through the RAM PUTC entry while
each of B0, B1, B2, and B3 is visible, verifies each PUTC call preserved that
bank, and checks CAPS_QUERY and BOARD_QUERY. Success is:

```text
B0 B1 B2 B3 RAM ABI: PASS
```

The probe then uses the RAM HOLD entry, which restores the resident STR8-N
bank and returns to its prompt.
