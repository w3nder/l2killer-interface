"""Execute local command parsing and chat interception in x86."""
from test_binary import *
dll=PE((PACKAGE/'bin/C4Bars.dll').read_bytes())
for base in (dll.u32(dll.opt+28),0x25000000):
    uc=emulator();map_pe(uc,dll,base);uc.mem_map(0x10000000,0x300000)
    syms=symbols(dll,base)
    def sym(*parts):
        matches=[v for k,v in syms.items() if all(p in k for p in parts) and '.part.' not in k]
        assert len(matches)==1,(parts,matches)
        return matches[0]
    user,actor,stack,values,string,out=SELF+0x5000,SELF+0x6000,SELF+0x7000,SELF+0x7100,SELF+0x8000,SELF+0x9000
    parse=sym('appearance','5parse')
    cases=[('!hero_on',0,1),('hero_on',1,1),('_hero_off',0,2),('!hero_off',0,2),
           ('hero_on',0,0),('hello',1,0),('!color_name FF0000',0,3),
           ('color_name #12abEF',1,3),('!color_name 0x00ff00',0,3),
           ('!color_name 123',0,0xffffffff),('!color_name 1234567',0,0xffffffff),
           ('!color_name 12345z',0,0xffffffff),('!hero_on extra',0,0)]
    for text,channel,expected in cases:
        uc.mem_write(string,(text+'\0').encode('utf-16le'))
        assert invoke(uc,parse,[string,channel,out],cdecl=True)==expected,text
    w32(uc,sym('potionL10moduleBaseE'),0x10000000)
    w32(uc,0x102c6ad4,CONSOLE);w32(uc,sym('potionL7getUserE'),0x70000100)
    w32(uc,sym('appearance','originalSay'),0x70000110)
    w32(uc,user+0x18,123);w32(uc,user+0x158,actor);w32(uc,actor+0x1710,0xa4)
    w32(uc,user+0x244,0xffffffff);w32(uc,stack,values);w32(uc,stack+12,3)
    sent=[]
    def hook(uc,address,size,unused):
        if address==0x70000100:return_from_stub(uc,0,user)
        elif address==0x70000110:
            sent.append(r32(uc,stack+8));return_from_stub(uc,1)
    uc.hook_add(UC_HOOK_CODE,hook)
    say=sym('appearance','3say')
    def command(text,channel=1):
        uc.mem_write(string,(text+'\0').encode('utf-16le'))
        w32(uc,values,channel);w32(uc,values+4,string);w32(uc,values+8,0);w32(uc,stack+8,0)
        invoke(uc,say,[stack],ecx=SELF)
    command('hero_on');assert r32(uc,actor+0x1710)==0xa5 and not sent
    assert r32(uc,stack+8)==3 and r32(uc,user+0x240)==0,'visual flag only'
    command('hero_off');assert r32(uc,actor+0x1710)==0xa4
    command('color_name FF0000');assert r32(uc,user+0x244)==0xffff0000
    command('color_name garbage');assert r32(uc,user+0x244)==0xffff0000 and not sent
    command('ordinary chat');assert sent==[0], 'normal chat forwarded without consuming parameters'
    w32(uc,user+0x18,456);w32(uc,user+0x244,0xff123456);w32(uc,actor+0x1710,0xa4)
    command('hero_off');assert r32(uc,user+0x244)==0xff123456,'new character clears color override'
print('Local appearance: parser, chat consumption, passthrough, visual hero flags, color and character reset passed at 2 bases')
