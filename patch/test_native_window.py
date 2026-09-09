"""Execute the compiled native-window bridge with a simulated C4 manager.

Checks allocation/registration ABI and lifecycle; visual/input integration still
requires an in-game test. Native APIs are deliberately not a renderer substitute.
"""
from test_binary import *

dll=PE((PACKAGE/'bin/C4Bars.dll').read_bytes())
original=PE(SOURCE_PATH.read_bytes())
for base in (dll.u32(dll.opt+28),0x25000000):
    uc=emulator();uc.mem_map(0,4096);map_pe(uc,dll,base);map_pe(uc,original,0x10000000)
    syms=symbols(dll,base)
    def sym(part):
        found=[v for k,v in syms.items() if part in k and '.part.' not in k]
        assert len(found)==1,(part,found)
        return found[0]
    obj,frame,node=SELF+0x6000,SELF+0x7000,SELF+0x8000
    w32(uc,sym('potionL10moduleBaseE'),0x10000000)
    uc.mem_write(sym('potionL9collapsedE'),b'\x00')
    w32(uc,0x102c6ad4,CONSOLE);w32(uc,CONSOLE+0x3bf4,GAME)
    w32(uc,GAME+0x15c,SELF)
    w32(uc,GAME+0x74,node+0x40)
    w32(uc,0x102c9ca4,0x102c9ca8)
    w32(uc,0x1019e2d8,0x70000100);w32(uc,0x1019e2e0,0x70000110)
    w32(uc,0x1019e2b4,SELF+0x9000);w32(uc,SELF+0x9000,0x12345678)
    w32(uc,SELF+0x268,12);w32(uc,SELF+0x26c,10);w32(uc,SELF+0x274,32)
    w32(uc,SELF+0x200,SELF+0x9000);w32(uc,SELF+0x1fc,SELF+0xa000)
    w32(uc,sym('originalBounds'),0x70000130)
    w32(uc,SELF+0x44,1148);w32(uc,SELF+0x48,900)
    w32(uc,0x102c6ad0,123)
    w32(uc,sym('__imp__GetClientRect@8'),0x70000120)
    w32(uc,sym('__imp__CallWindowProcW@20'),0x70000140)
    w32(uc,sym('potionL15previousWndProcE'),1234)
    for name,address in [('__imp__SetCapture@4',0x70000150),('__imp__GetCapture@0',0x70000160),('__imp__ReleaseCapture@0',0x70000170)]:
        w32(uc,sym(name),address)
    calls=[]
    capture=[0]
    positions=[[585,263],[1170,527],[970,427]]
    def hook(uc,address,size,user):
        sp=uc.reg_read(UC_X86_REG_ESP);this=uc.reg_read(UC_X86_REG_ECX)
        def arg(i):return r32(uc,sp+i*4)
        if address==0x70000110:
            calls.append('package');return_from_stub(uc,0,0x12340000)
        elif address==0x70000100:
            assert [arg(i) for i in range(1,9)]==[0x102c9ca8,0x12340000,0,0,0,0x12345678,0,0]
            calls.append('allocate');return_from_stub(uc,0,obj)
        elif address==0x70000120:
            assert arg(1)==123
            for i,value in enumerate((0,0,1470,797)):w32(uc,arg(2)+i*4,value)
            return_from_stub(uc,2)
        elif address==0x70000130:
            return_from_stub(uc,2,0)
        elif address==0x70000140:
            if arg(3)==0x82:
                return_from_stub(uc,5,19);return
            raise AssertionError('Owned frame clicks must not reach the game WndProc')
        elif address==0x70000150:
            capture[0]=arg(1);return_from_stub(uc,1)
        elif address==0x70000160:
            return_from_stub(uc,0,capture[0])
        elif address==0x70000170:
            capture[0]=0;return_from_stub(uc,0)
        elif address==0x10036d00:
            assert this==obj;w32(uc,obj,0x1019f8b8)
            calls.append('constructor');return_from_stub(uc,0,obj)
        elif address==0x10035c40:
            assert this==obj and [arg(i) for i in range(3,8)]==[300,270,0,0,3]
            assert [arg(1),arg(2)]==positions.pop(0), 'center, clamp, then drag'
            w32(uc,obj+0x44,arg(1));w32(uc,obj+0x48,arg(2))
            calls.append('position');return_from_stub(uc,7)
        elif address==0x10035820:
            assert this==GAME and arg(1)==obj and arg(2)==0x401082
            w32(uc,obj+0x68,arg(2));calls.append('register');return_from_stub(uc,2,node)
        elif address==0x10034380:
            if arg(1)==3:
                assert this==obj and arg(3)==20*65536+20
                calls.append('move');return_from_stub(uc,3);return
            assert this==obj and [arg(i) for i in range(1,4)]==[1,0,0]
            assert r32(uc,obj+0x74)==node
            w32(uc,obj+0x7c,frame);w32(uc,frame,0x101a2b40)
            calls.append('create');return_from_stub(uc,3)
        elif address==0x10011940:
            assert this==frame
            assert bytes(uc.mem_read(arg(1),42)).decode('utf-16le').rstrip('\0')=='Auto Potion Settings'
            calls.append('title');return_from_stub(uc,1)
        elif address==0x1002b490:
            assert this==obj and arg(2)==0
            assert bytes(uc.mem_read(arg(1),56)).decode('utf-16le').rstrip('\0')=='L2UI_ch3.dialog.system_back'
            calls.append('backdrop');return_from_stub(uc,2,SELF+0xb000)
        elif address==0x10012340:
            assert this==frame and r32(uc,frame+0x264)==1
            calls.append('controls');return_from_stub(uc,0)
        elif address==0x10034590:
            assert this==obj;w32(uc,obj+0x68,r32(uc,obj+0x68)|2)
            calls.append('show');return_from_stub(uc,0)
        elif address==0x10035a90:
            assert this==obj;w32(uc,obj+0x68,r32(uc,obj+0x68)&~2)
            calls.append('hide');return_from_stub(uc,0)
        elif address==0x10035af0:
            assert this==obj;calls.append('focus');return_from_stub(uc,0)
        elif address in (0x1002b5c0,0x1002b5d0):
            calls.append('capture' if address==0x1002b5c0 else 'release')
            return_from_stub(uc,0)
        elif address==0x10036140:
            assert this==obj;calls.append('destroy');return_from_stub(uc,0)
    uc.hook_add(UC_HOOK_CODE,hook)
    # GCC's private local-call convention passes self in EAX (checked in objdump).
    uc.reg_write(UC_X86_REG_EAX,SELF)
    invoke(uc,sym('syncNativeWindow'),[],cdecl=True)
    assert calls==['package','allocate','constructor','position','register','create','backdrop','title','controls','focus'],calls
    assert r32(uc,sym('potionL12configWindowE'))==obj
    # The shortcut window must not claim the expanded native panel's clicks.
    assert invoke(uc,sym('boundsHook'),[600,300],ecx=SELF)==0
    uc.mem_write(sym('potionL9collapsedE'),b'\x01')
    assert invoke(uc,sym('boundsHook'),[600,300],ecx=SELF)==1
    uc.mem_write(sym('potionL9collapsedE'),b'\x00')
    # Native mouse callback reaches the percentage + control and takes focus.
    packed=(263+42)*65536+585+255
    before=r32(uc,sym('potionL16draftPercentagesE'))
    invoke(uc,r32(uc,r32(uc,obj)+0x110),[0,packed],ecx=obj)
    assert r32(uc,sym('potionL16draftPercentagesE'))==before+1
    assert calls[-1]=='focus'
    # Execute original C4 down/move/up code: title presses must engage native
    # capture and forward a move event; releasing must clear the drag state.
    title=253*65536+600
    invoke(uc,r32(uc,r32(uc,obj)+0x110),[0,title],ecx=obj)
    assert r32(uc,obj+0x6c)==1 and calls[-1]=='capture'
    invoke(uc,r32(uc,r32(uc,obj)+0x10c),[1,273*65536+620],ecx=obj)
    assert calls[-1]=='move'
    invoke(uc,r32(uc,r32(uc,obj)+0x114),[0,273*65536+620],ecx=obj)
    assert r32(uc,obj+0x6c)==0 and calls[-1]=='release'
    # A resize or previously off-screen position must be corrected without
    # allocating a second window or losing the existing native frame.
    w32(uc,obj+0x44,1652);w32(uc,obj+0x48,900)
    uc.reg_write(UC_X86_REG_EAX,SELF)
    invoke(uc,sym('syncNativeWindow'),[],cdecl=True)
    assert calls.count('allocate')==1 and calls[-1]=='position'
    for _ in range(2):
        uc.mem_write(sym('potionL9collapsedE'),b'\x00')
        uc.reg_write(UC_X86_REG_EAX,SELF)
        invoke(uc,sym('syncNativeWindow'),[],cdecl=True)
        uc.mem_write(sym('worldClickOwned'),b'\x01')
        packed=520*65536+1460  # Native close button, outside the draggable title.
        invoke(uc,sym('windowProc'),[123,0x201,0,packed])
        assert uc.mem_read(sym('potionL9collapsedE'),1)==b'\x01'
        assert not r32(uc,obj+0x68)&2
        invoke(uc,sym('windowProc'),[123,0x202,0,packed])
        assert uc.mem_read(sym('nativeClickSequence'),1)==b'\x00'
        assert uc.mem_read(sym('worldClickOwned'),1)==b'\x01'
        # The viewport and engine deliver separate mouse events. Closing must
        # consume the engine press/release too, even after the viewport release.
        assert invoke(uc,sym('consoleHook'),[0x100,1,0],ecx=CONSOLE)==1
        assert invoke(uc,sym('consoleHook'),[0x101,1,0],ecx=CONSOLE)==1
        assert uc.mem_read(sym('worldClickOwned'),1)==b'\x00'
    uc.mem_write(sym('potionL9collapsedE'),b'\x00')
    invoke(uc,sym('windowProc'),[123,0x201,0,520*65536+1200])
    assert capture[0]==123
    invoke(uc,sym('windowProc'),[123,0x200,1,420*65536+1000])
    assert [r32(uc,obj+0x44),r32(uc,obj+0x48)]==[970,427]
    invoke(uc,sym('windowProc'),[123,0x202,0,420*65536+1000])
    assert capture[0]==0 and r32(uc,obj+0x6c)==0 and positions==[]
    # Close via the native frame callback, then destroy via native manager event.
    invoke(uc,r32(uc,r32(uc,frame)+0x130),[],ecx=frame)
    assert uc.mem_read(sym('potionL9collapsedE'),1)==b'\x01'
    invoke(uc,r32(uc,r32(uc,obj)+0x98),[],ecx=obj)
    assert r32(uc,sym('potionL12configWindowE'))==0
    assert calls[-2:]==['hide','destroy']
    assert r32(uc,sym('dialogBackdrop'))==0
    w32(uc,sym('inputWindow'),123)
    assert invoke(uc,sym('windowProc'),[123,0x82,0,0])==19
    assert r32(uc,sym('inputWindow'))==0
    assert r32(uc,sym('potionL15previousWndProcE'))==0
print('Native window bridge: allocation, registration, integer dimensions, title, close and teardown passed at 2 DLL bases; native APIs simulated')
