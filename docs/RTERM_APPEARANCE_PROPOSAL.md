# RTERM font and appearance proposal

Status: proposed 2026-09-25. Documentation only; no renderer, configuration,
font assets, or protocol changes are implemented here.

RTERM should accommodate IBM 3270-style, line-printer-style, and other
monospaced appearances as local user preferences. Appearance is independent
of target firmware, bank support, and the optional target status API.

## Current ncurses renderer

RTERM currently renders its internal screen through `libncursesw`. The outer
terminal supplies the font. Users can select an installed font in a dedicated
terminal profile; RTERM does not currently load or select fonts itself.
For Windows Terminal, font selection is a per-profile appearance setting:
[Microsoft profile appearance documentation](https://learn.microsoft.com/en-us/windows/terminal/customize-settings/profile-appearance).

Document this route first, including checking monospaced cell alignment and
line-drawing coverage. A terminal profile can combine a font with suitable
foreground, background, and cursor settings. Available controls depend on the
hosting terminal; do not promise portable font switching through ncurses.

## Proposed graphical renderer

For font selection within RTERM, add an optional graphical renderer alongside
the existing ncurses renderer. Reuse the screen model, terminal parser, field
handling, serial connection, and protocol services. Keep renderer-specific
font loading and drawing separate from target communication.

Proposed local appearance controls:

- Monospaced font family or local font file, size, and supported weight.
- Cell and line spacing that preserve a fixed terminal grid.
- Foreground/background palette and cursor shape or blink preference.
- Named presets with user overrides and a readable default fallback.

Candidate presets are `3270 green`, `amber terminal`, and `line printer`.
They describe appearance, not terminal identities or protocol capabilities.
The line-printer preset could use dark text on a light background with a
printer-style monospaced face. Exact fonts and defaults remain to be chosen;
bundle a font only after verifying its redistribution license.

Keep font choice and preset selection under local user control. The target
status API supplies bounded text only and does not select fonts or styling.
Existing terminal attributes still pass through the selected renderer. A
3270-style font does not implement IBM 3270 protocol behavior, and a
line-printer appearance does not implement a printer or spool service.

## Implementation and validation

- Document host-terminal font setup for the existing ncurses path.
- Define a renderer boundary before selecting a graphical toolkit or adding
  renderer-specific configuration. Preserve the ncurses launch path.
- Check 80- and 132-column layouts, resize behavior, cursor placement,
  protected/input fields, and the separate DEC status line and RTERM OIA.
- Verify line-drawing joins, supported character coverage, attribute rendering,
  and fallback behavior when a font or glyph is unavailable.
- Confirm appearance changes leave screen contents, input semantics, terminal
  personality, and protocol negotiation unchanged.

Related: [target status API proposal](RTERM_TARGET_STATUS_PROPOSAL.md),
[RTERM architecture](../../RTERM/DESIGN.md), and
[terminal coverage](../../RTERM/TERMINAL.md).
