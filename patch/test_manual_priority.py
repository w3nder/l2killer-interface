"""Validate entry detour/trampoline and inventory callback ABI against C4 bytes."""
from test_binary import *

dll=PE((PACKAGE/'bin/C4Bars.dll').read_bytes())
original=PE(SOURCE_PATH.read_bytes())
for base in (dll.u32(dll.opt+28),0x25000000):
    uc=emulator();map_pe(uc,dll,base);map_pe(uc,original,0x10000000)
    syms=symbols(dll,base)
    def sym(part):
        values=[v for k,v in syms.items() if part in k and '.part.' not in k]
        assert len(values)==1,(part,values)
        return values[0]
    w32(uc,sym('potionL10moduleBaseE'),0x10000000)
    bridge=SELF+0x6000
    for name,at in [('VirtualAlloc@16',0x70000100),('VirtualProtect@16',0x70000110),
                    ('GetCurrentProcess@0',0x70000120),('FlushInstructionCache@12',0x70000130),
                    ('GetTickCount@0',0x70000140)]:
        w32(uc,sym('__imp__'+name),at)
    requests=[];updates=[];allocations=[]
    def hook(uc,address,size,user):
        sp=uc.reg_read(UC_X86_REG_ESP)
        if address==0x70000100:
            allocations.append(1);return_from_stub(uc,4,bridge)
        elif address==0x70000110:
            w32(uc,r32(uc,sp+16),0x20);return_from_stub(uc,4,1)
        elif address==0x70000120:return_from_stub(uc,0,0xffffffff)
        elif address==0x70000130:return_from_stub(uc,3,1)
        elif address==0x70000140:return_from_stub(uc,0,100)
        elif address==0x10066485:
            # Original prologue has run through the trampoline. Mock only the
            # native request body, preserving thiscall args and stack unwind.
            assert uc.reg_read(UC_X86_REG_ECX)==CONSOLE
            bp=uc.reg_read(UC_X86_REG_EBP)
            object_id=r32(uc,bp+8)
            assert uc.mem_read(sym('manualRequestPending'),1)==(b'\x00' if object_id==888 else b'\x01')
            requests.append(object_id)
            uc.reg_write(UC_X86_REG_EBP,r32(uc,bp))
            uc.reg_write(UC_X86_REG_ESP,bp+4)
            return_from_stub(uc,1,1)
        elif address in (0x10066570,0x10066620):
            assert uc.reg_read(UC_X86_REG_ECX)==CONSOLE
            updates.append(address)
            return_from_stub(uc,1 if address==0x10066570 else 0)
    uc.hook_add(UC_HOOK_CODE,hook)
    invoke(uc,sym('installManualItemPriority'),[],cdecl=True)
    assert r32(uc,sym('potionL7useItemE'))==bridge
    assert bytes(uc.mem_read(bridge,5))==b'\x55\x8b\xec\x6a\xff'
    assert bytes(uc.mem_read(0x10066480,1))==b'\xe9'
    # Native inventory and shortcut callers traverse the detour.
    invoke(uc,0x10066480,[777],ecx=CONSOLE)
    assert requests==[777] and uc.mem_read(sym('manualRequestPending'),1)==b'\x00'
    invoke(uc,r32(uc,0x101b354c),[],ecx=CONSOLE)
    assert updates==[0x10066620] and uc.mem_read(sym('manualRequestPending'),1)==b'\x00'
    # Automatic requests bypass only the observer, not the native item routine.
    invoke(uc,bridge,[888],ecx=CONSOLE)
    assert requests==[777,888] and uc.mem_read(sym('manualRequestPending'),1)==b'\x00'
    invoke(uc,0x10066480,[999],ecx=CONSOLE)
    invoke(uc,r32(uc,0x101b3548),[0],ecx=CONSOLE)
    assert updates[-1]==0x10066570 and uc.mem_read(sym('manualRequestPending'),1)==b'\x00'
    invoke(uc,sym('installManualItemPriority'),[],cdecl=True)
    assert len(allocations)==1
print('Native manual priority: entry detour, original trampoline, inventory callbacks and repeat install passed at 2 DLL bases')
