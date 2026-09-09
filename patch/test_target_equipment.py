"""Execute target equipment rendering with mocked client data and renderer."""
from test_binary import *

dll=PE((PACKAGE/'bin/C4Bars.dll').read_bytes())
native=PE(SOURCE_PATH.read_bytes())
for base in (dll.u32(dll.opt+28),0x25000000):
    uc=emulator();map_pe(uc,dll,base);map_pe(uc,native,0x10000000)
    syms=symbols(dll,base)
    def sym(*parts):
        matches=[v for k,v in syms.items() if all(p in k for p in parts) and '.part.' not in k]
        assert len(matches)==1,(parts,matches)
        return matches[0]
    target,user,table,record=SELF+0x6000,SELF+0x7000,SELF+0x8000,SELF+0x9000
    w32(uc,sym('potionL10moduleBaseE'),0x10000000)
    w32(uc,0x102c6ad4,CONSOLE);w32(uc,target,table)
    w32(uc,target+0x44,100);w32(uc,target+0x48,100)
    uc.mem_write(target+0x4c,struct.pack('<ff',200,76))
    w32(uc,target+0x374,1);w32(uc,target+0x68,2);w32(uc,target+0x380,0x55000000)
    w32(uc,user+0x18,123);w32(uc,user+0xb0,1001);w32(uc,user+0xcc,1001)
    w32(uc,user+0xbc,1002)
    w32(uc,0x1019e494,SELF+0xa000)
    w32(uc,0x1019e4e0,0x70000110);w32(uc,0x1019e4ec,0x70000120)
    w32(uc,0x1019e508,0x70000130);w32(uc,table+0xa0,0x70000140)
    w32(uc,sym('targetEquipment','nativePaint'),0x70000100)
    for name,at in [('potionL4tileE',0x70000150),('pushClip',0x70000160),('popClip',0x70000170),('potionL10normalTextE',0x70000180)]:
        w32(uc,sym(name),at)
    uc.mem_write(SELF+0xb000,'icon.test\0'.encode('utf-16le'))
    loads=[];tiles=[];selected=[user];sizes=[]
    def hook(uc,address,size,user_data):
        sp=uc.reg_read(UC_X86_REG_ESP);this=uc.reg_read(UC_X86_REG_ECX)
        def arg(i):return r32(uc,sp+4*i)
        if address==0x70000100:
            assert this==target;return_from_stub(uc,1,7)
        elif address==0x10073f80:
            assert this==CONSOLE;return_from_stub(uc,0,selected[0])
        elif address==0x70000110:
            loads.append(arg(1));return_from_stub(uc,1,record)
        elif address==0x70000120:
            assert this==record+0x3c;return_from_stub(uc,0,SELF+0xb000)
        elif address==0x1002b490:
            assert this==target and arg(2)==1;return_from_stub(uc,2,0x55000100)
        elif address==0x70000140:
            assert this==target and [arg(5),arg(6),arg(7)]==[0,0,3]
            sizes.append(arg(4));uc.mem_write(target+0x50,struct.pack('<f',arg(4)))
            return_from_stub(uc,7)
        elif address==0x70000150:
            tiles.append([arg(i) for i in range(1,12)]);return_from_stub(uc,11)
        elif address in (0x70000160,0x70000170,0x70000180):
            return_from_stub(uc,{0x70000160:4,0x70000170:0,0x70000180:15}[address])
    uc.hook_add(UC_HOOK_CODE,hook)
    # Only the weapon gets the character's single enchant field.
    enchant=sym('targetEquipment','weaponEnchant')
    w32(uc,user+0x234,20);w32(uc,record+4,0)
    assert invoke(uc,enchant,[CONSOLE,user,1001,record],cdecl=True)==20
    assert invoke(uc,enchant,[CONSOLE,user,1002,record],cdecl=True)==0xffffffff
    w32(uc,record+4,1)
    assert invoke(uc,enchant,[CONSOLE,user,1001,record],cdecl=True)==0xffffffff
    w32(uc,record+4,0);w32(uc,user+0x234,0xffffffff)
    assert invoke(uc,enchant,[CONSOLE,user,1001,record],cdecl=True)==0xffffffff
    formatter=sym('targetEquipment','enchantLabel')
    for value,expected in [(20,'Test (+20)'),(0,'Test (+0)'),(127,'Test (+127)'),(0xffffffff,'Test')]:
        uc.mem_write(SELF+0xb000,'Test\0'.encode('utf-16le'))
        invoke(uc,formatter,[SELF+0xc000,SELF+0xb000,value],cdecl=True)
        actual=bytes(uc.mem_read(SELF+0xc000,512)).decode('utf-16le').split('\0')[0]
        assert actual==expected,(actual,expected)
    paint=sym('targetEquipment','5paint')
    def draw():
        w32(uc,CANVAS+0x38,33);w32(uc,CANVAS+0x3c,44)
        assert invoke(uc,paint,[CANVAS],ecx=target)==7
        assert r32(uc,CANVAS+0x38)==33 and r32(uc,CANVAS+0x3c)==44
    draw();assert loads==[1001,1002] and sizes==[114]
    draw();assert loads==[1001,1002] and sizes==[114], 'no repeated texture load or size growth'
    w32(uc,user+0xbc,1003);draw();assert loads[-1]==1003
    w32(uc,target+0x374,0);draw();assert sizes[-1]==76
    w32(uc,target+0x374,1);w32(uc,user+8,1);draw();assert sizes[-1]==76, 'NPC does not get equipment panel'
    w32(uc,user+8,0);w32(uc,user+0x18,456)
    for offset in (0xb0,0xbc,0xcc):w32(uc,user+offset,0)
    before=len(loads);draw();assert len(loads)==before, 'missing IDs do not resolve textures'
    uc.mem_write(target+0x4c,struct.pack('<f',140))
    for i,offset in enumerate((0x94,0xac,0xb0,0xb4,0xb8,0xbc,0xc0,0xc4,0xc8,0xcc,0xd4)):w32(uc,user+offset,2000+i)
    draw();assert sizes[-1]==132, 'narrow panels wrap all eleven received slots'
    assert 2000 in loads, 'underwear/custom tattoo slot is included'
    selected[0]=0;draw();assert sizes[-1]==76, 'lost target restores native height'
print('Target equipment: player-only expansion, deduplication, item changes, cached textures, missing data, collapse and lost target passed at 2 bases')
