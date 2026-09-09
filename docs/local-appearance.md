# Local appearance commands

Use !hero_on, !hero_off (or _hero_off) and !color_name RRGGBB. Color accepts exactly six hex digits, optionally prefixed with # or 0x. Example: !color_name FF0000. State is session-only and clears on character ID change. Commands are case-sensitive. Invalid color commands are swallowed without changing the color. Regular chat is passed through unchanged.

This is a local visual override for the User returned by NWindow GetUser (RVA 0x73f30). Hero modifies only actor +0x1710 bit 0, used by the renderer before GetHeroMesh at engine VA 0x1069c5b5. It does not modify the User hero/status field or grant skills. Name color uses User +0x244, confirmed by GetNameColor (0x10466510) and GetUniqueNameColor (0x10352ff0). Native karma/PvP color precedence remains intact. Other clients do not receive these changes.

The engine Say2 prologue at RVA 0xf8750 is checked against eight exact bytes before installing a trampoline. Its parameter stack contains channel, text and recipient; recognized local commands consume those three values without calling the network function. Shout processing may remove the leading !, so bare command names are recognized only in shout channel 1. No new thread, sleeps or allocations per frame. One 16-byte trampoline allocation stays for process lifetime while the detour is installed; DLL unloading is unsupported.

Compiled x86 tests verify command parsing, invalid input, parameter consumption, normal-chat passthrough, preservation of unrelated actor flags, color packing, and character-change reset at two DLL bases. Existing bars, auto-potion, native window and target equipment regression passed. Live chat/hero/name rendering validation remains pending.
