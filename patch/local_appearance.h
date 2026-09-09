// Client-only appearance commands. Never grants server-side hero status.
namespace appearance {
using Say=void (__thiscall *)(void *,void *);
Say originalSay=nullptr;
bool attempted=false;
unsigned character=0;
int hero=-1;
bool colored=false;
unsigned color=0xffffffff;
void *localUser(){
    void *console=field<void *>(potion::moduleBase,0x2c6ad4);
    return console&&potion::getUser?potion::getUser(console):nullptr;
}
void apply(){
    void *user=localUser();
    unsigned id=user?field<unsigned>(user,0x18):0;
    if(id!=character){character=id;hero=-1;colored=false;}
    if(!id)return;
    if(colored)field<unsigned>(user,0x244)=color;
    void *actor=field<void *>(user,0x158);
    if(actor&&hero>=0){
        unsigned &flags=field<unsigned>(actor,0x1710);
        flags=(flags&~1u)|static_cast<unsigned>(hero);
    }
}
bool same(const wchar_t *a,const wchar_t *b){while(*a&&*a==*b){++a;++b;}return *a==*b;}
// Return 0 for regular chat, 1/2 for hero, 3 for color, -1 for invalid local command.
__attribute__((noinline,regparm(0))) int parse(const wchar_t *s,unsigned channel,unsigned *rgb){
    if(!s)return 0;
    if(*s==L'!'||*s==L'_')++s;
    else if(channel!=1)return 0; // Shout parser removes '!'.
    if(same(s,L"hero_on"))return 1;
    if(same(s,L"hero_off"))return 2;
    const wchar_t *prefix=L"color_name";
    const wchar_t *p=s;
    while(*prefix&&*p==*prefix){++p;++prefix;}
    if(*prefix||(*p&&*p!=L' '))return 0;
    if(*p!=L' ')return -1;
    while(*p==L' ')++p;
    if(*p==L'#')++p;
    else if(p[0]==L'0'&&(p[1]==L'x'||p[1]==L'X'))p+=2;
    unsigned value=0;
    for(int i=0;i<6;++i){
        unsigned d;
        if(*p>=L'0'&&*p<=L'9')d=*p-L'0';
        else if(*p>=L'a'&&*p<=L'f')d=*p-L'a'+10;
        else if(*p>=L'A'&&*p<=L'F')d=*p-L'A'+10;
        else return -1;
        value=(value<<4)|d;++p;
    }
    while(*p==L' ')++p;
    if(*p)return -1;
    *rgb=0xff000000|value;return 3;
}
void __fastcall say(void *self,void *,void *stack){
    int index=field<int>(stack,8),length=field<int>(stack,12);
    unsigned *values=field<unsigned *>(stack,0);
    if(values&&index>=0&&index<=length&&length-index>=3){
        unsigned rgb=0;
        int command=parse(reinterpret_cast<const wchar_t *>(values[index+1]),values[index],&rgb);
        if(command){
            field<int>(stack,8)=index+3; // Match Say2's three consumed parameters.
            apply();
            if(character){
                if(command==1)hero=1;
                if(command==2)hero=0;
                if(command==3){colored=true;color=rgb;}
                apply();
            }
            return; // Recognized local commands never reach network chat.
        }
    }
    originalSay(self,stack);
}
void install(){
    if(attempted)return;
    auto *engine=reinterpret_cast<unsigned char *>(GetModuleHandleA("engine.dll"));
    if(!engine)return;
    attempted=true;
    auto *entry=engine+0xf8750;
    const unsigned char expected[]={0x53,0x55,0x56,0x57,0x8b,0x7c,0x24,0x14};
    if(!equalBytes(entry,expected,8))return;
    auto *bridge=static_cast<unsigned char *>(VirtualAlloc(nullptr,16,MEM_COMMIT|MEM_RESERVE,PAGE_EXECUTE_READWRITE));
    if(!bridge)return;
    copyBytes(bridge,entry,8);putJump(bridge+8,entry+8);
    DWORD old;
    if(!VirtualProtect(entry,8,PAGE_EXECUTE_READWRITE,&old)){VirtualFree(bridge,0,MEM_RELEASE);return;}
    originalSay=reinterpret_cast<Say>(bridge);
    putJump(entry,reinterpret_cast<void *>(&say));
    DWORD ignored;VirtualProtect(entry,8,old,&ignored);
    FlushInstructionCache(GetCurrentProcess(),entry,8);
    log("local appearance: chat commands installed\r\n");
}
}
