# Independent potion dispatch investigation

Reported: CP appears to be consumed before HP begins. The original loop already
called every due channel, but always CP first and evaluated each binding between
native requests. A server limit is not established; the user reports concurrent
potion use is supported.

The revised loop snapshots eligible object IDs for all channels before sending
any request. All due channels still dispatch in the same game update. Starting
order rotates; there is no one-item-per-frame cap, added timer, shared cooldown,
or dependency on CP reaching its threshold before HP runs. Manual input retains
priority. Each channel keeps its own configured interval and state.

Executable x86 regression at two bases covers four simultaneously low channels,
every channel dispatched in every update, rotating first position, disabled CP,
and yielding to manual input. Existing bars, binding, persistence and interval
regression passed. Root cause and resolution still require live reproduction;
no public release or ZIP has been updated.
