# Target equipment — first develop implementation

Pending in-game validation. No release/ZIP produced.

NWindow vtable cell RVA 0x1ceeb8 is OnPaint for NCTargetStatusWnd (original RVA 0x113d40). Expanded flag +0x374; native clan and ally lines are at y=0x2b and y=0x3b. Appended icon area starts at y=78. Native dimensions are restored on collapse/lost/non-player target. Columns adapt to panel width.

NConsoleWnd target getter RVA 0x73f80 returns selected User. User +8 distinguishes non-player data. Paperdoll entries +0xac..0xcc and +0xd4 are read from the current User, without storing a User pointer across frames. User +0x90 distinguishes remote class IDs from local object IDs; local entries resolve through the existing network GetItem virtual +0x9c, Item +4 class ID. This matches engine User::GetItemClassID / SetItemSlotByItemClassID. Duplicate class IDs are displayed once (e.g. shared hand/body render slots).

Native game data lookup IAT RVA 0x19e4e0; GL2GameData IAT 0x19e494; item icon L2FName +0x3c converted with IAT 0x19e4ec; load via existing NWindow RVA 0x2b490. Native GetItemName IAT 0x19e508. Texture lookups happen on changed displayed IDs, not every paint. Textures remain client-owned; no new item heap object is created.

Limitations: display only client-provided visual equipment. Jewelry, enchant values and hidden server state are not inferred. Native visual inspection still needed for clipping, background, render order and target updates.

Validation: compiled x86 renderer bridge tested at two DLL bases for player-only display, repeated frames, duplicated IDs, equipment changes, empty data, NPC, collapse, lost target, width wrapping and canvas-origin restoration. Full existing regression also passed before the final width-only layout adjustment.

Player validated the first in-game equipment display. Icons are now 24px with 28px spacing; compact layout regression passed at both DLL bases. Custom left/tattoo slots are not yet mapped.
