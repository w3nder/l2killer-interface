// C4 L2Killer: append the equipment actually present in the selected User cache.
namespace targetEquipment {
Paint nativePaint=nullptr;
bool attempted=false;
void *owner=nullptr;
unsigned targetId=0;
constexpr int count=11,top=78,iconSize=14,pitch=18;
int extraHeight=76;
constexpr unsigned offsets[count]={0x94,0xac,0xb0,0xb4,0xb8,0xbc,0xc0,0xc4,0xc8,0xcc,0xd4};
unsigned ids[count]={};
void *textures[count]={};
float originalHeight=0;
bool enlarged=false;
using Target=void *(__thiscall *)(void *);
using Lookup=void *(__thiscall *)(void *,unsigned);
using Name=const wchar_t *(__thiscall *)(void *);
using ItemName=const wchar_t *(__thiscall *)(void *,unsigned);
using Load=void *(__thiscall *)(void *,const wchar_t *,int);
using Position=void (__thiscall *)(void *,int,int,int,int,int,int,int);

void resize(void *self,int height) {
    auto fn=reinterpret_cast<Position>(field<uintptr_t>(field<void *>(self,0),0xa0));
    fn(self,field<int>(self,0x44),field<int>(self,0x48),
       static_cast<int>(field<float>(self,0x4c)),height,0,0,3);
}
void reset(void *self) {
    if(enlarged&&owner==self&&field<float>(self,0x50)==originalHeight+extraHeight)
        resize(self,static_cast<int>(originalHeight));
    enlarged=false;targetId=0;
    for(int i=0;i<count;++i){ids[i]=0;textures[i]=nullptr;}
}
unsigned itemClass(void *console,void *user,unsigned offset) {
    const unsigned value=field<unsigned>(user,offset);
    if(!value)return 0;
    if(!field<unsigned>(user,0x90))return value; // Remote CharInfo stores class IDs.
    void *engine=field<void *>(console,0x54);
    void *network=engine?field<void *>(engine,0x64):nullptr;
    if(!network)return 0;
    auto lookup=reinterpret_cast<Lookup>(field<uintptr_t>(field<void *>(network,0),0x9c));
    void *item=lookup(network,value); // Local UserInfo stores object IDs.
    return item?field<unsigned>(item,4):0;
}
// CharInfo has one weapon-effect enchant value, not per-armor enchant data.
__attribute__((noinline,regparm(0))) int weaponEnchant(void *console,void *user,unsigned id,void *entry) {
    if(!id||!entry||field<int>(entry,4)!=0)return -1; // Weapon item-data type.
    if(id!=itemClass(console,user,0xb0)&&id!=itemClass(console,user,0xcc))return -1;
    const int value=field<int>(user,0x234);
    return value>=0&&value<=127?value:-1; // Native decoder sign-extends a byte.
}
__attribute__((noinline,regparm(0))) void enchantLabel(wchar_t *out,const wchar_t *name,int value) {
    int n=0;
    while(name[n]&&n<247){out[n]=name[n];++n;}
    if(value>=0&&value<=127){
        out[n++]=L' ';out[n++]=L'(';out[n++]=L'+';
        if(value>=100)out[n++]=L'0'+value/100;
        if(value>=10)out[n++]=L'0'+(value/10)%10;
        out[n++]=L'0'+value%10;out[n++]=L')';
    }
    out[n]=0;
}
int __fastcall paint(void *self,void *,void *canvas) {
    const int result=nativePaint(self,canvas);
    void *console=field<void *>(potion::moduleBase,0x2c6ad4);
    if(owner!=self){owner=self;enlarged=false;targetId=0;}
    if(!console||!field<int>(self,0x374)||!(field<unsigned>(self,0x68)&2)) {
        reset(self);return result;
    }
    void *user=reinterpret_cast<Target>(potion::moduleBase+0x73f80)(console);
    if(!user||field<int>(user,8)!=0){reset(self);return result;} // Players only.
    const unsigned selected=field<unsigned>(user,0x18);
    if(selected!=targetId){reset(self);targetId=selected;}
    const int width=static_cast<int>(field<float>(self,0x4c));
    if(width<84){reset(self);return result;}
    int columns=(width-28)/pitch;
    if(columns>count)columns=count;
    void *data=field<void *>(potion::moduleBase,0x19e494);
    auto itemData=field<Lookup>(potion::moduleBase,0x19e4e0);
    auto name=field<Name>(potion::moduleBase,0x19e4ec);
    auto itemName=field<ItemName>(potion::moduleBase,0x19e508);
    if(!data||!itemData||!name||!itemName)return result;
    int used=0;
    unsigned current[count]={};
    for(unsigned offset:offsets) {
        unsigned id=itemClass(console,user,offset);
        if(!id||id>10000000)continue;
        bool duplicate=false;
        for(int j=0;j<used;++j)if(current[j]==id)duplicate=true;
        if(!duplicate)current[used++]=id;
    }
    const int needed=(((used?used:1)+columns-1)/columns)*pitch+20;
    if(enlarged&&needed!=extraHeight){reset(self);targetId=selected;}
    if(!enlarged){
        extraHeight=needed;
        originalHeight=field<float>(self,0x50);
        if(originalHeight<70||originalHeight>100)return result;
        resize(self,static_cast<int>(originalHeight)+extraHeight);enlarged=true;
    }
    for(int i=0;i<count;++i)if(ids[i]!=current[i]) {
        ids[i]=current[i];textures[i]=nullptr;
        void *entry=ids[i]?itemData(data,ids[i]):nullptr;
        if(entry) {
            const wchar_t *icon=name(static_cast<unsigned char *>(entry)+0x3c);
            if(icon&&*icon)textures[i]=reinterpret_cast<Load>(potion::moduleBase+0x2b490)(self,icon,1);
        }
    }
    const int oldX=field<int>(canvas,0x38),oldY=field<int>(canvas,0x3c);
    const int x=field<int>(self,0x44),y=field<int>(self,0x48);
    field<int>(canvas,0x38)=x;field<int>(canvas,0x3c)=y;
    pushClip(canvas,x,y+top,width,extraHeight);
    void *back=field<void *>(self,0x380);
    if(back)potion::tile(canvas,12,top,width-24,extraHeight,0,0,16,46,back,255,1);
    POINT cursor{};
    HWND hwnd=field<HWND>(potion::moduleBase,0x2c6ad0);
    const bool hover=hwnd&&GetForegroundWindow()==hwnd&&GetCursorPos(&cursor)&&ScreenToClient(hwnd,&cursor);
    int hovered=-1;
    for(int i=0;i<used;++i) {
        const int sx=16+(i%columns)*pitch,sy=top+4+(i/columns)*pitch;
        if(textures[i])potion::tile(canvas,sx,sy,iconSize,iconSize,0,0,32,32,textures[i],255,1);
        if(hover&&cursor.x>=x+sx&&cursor.x<x+sx+iconSize&&cursor.y>=y+sy&&cursor.y<y+sy+iconSize)hovered=i;
    }
    if(!used)potion::text(canvas,16,top+8,L"No equipment data",0xffa3a3a3);
    if(hovered>=0){
        const wchar_t *label=itemName(data,ids[hovered]);
        if(label){
            wchar_t display[256];
            const int enchant=weaponEnchant(console,user,ids[hovered],itemData(data,ids[hovered]));
            enchantLabel(display,label,enchant);
            potion::text(canvas,16,top+extraHeight-16,display,0xffdfbf78);
        }
    }
    popClip(canvas);field<int>(canvas,0x38)=oldX;field<int>(canvas,0x3c)=oldY;
    return result;
}
void install() {
    if(attempted)return;
    attempted=true;
    auto *slot=reinterpret_cast<uintptr_t *>(potion::moduleBase+0x1ceeb8);
    if(*slot!=reinterpret_cast<uintptr_t>(potion::moduleBase+0x113d40))return;
    if(!GetPrivateProfileIntA("C4Bars","TargetEquipment",1,iniPath))return;
    DWORD old;
    if(!VirtualProtect(slot,4,PAGE_READWRITE,&old))return;
    nativePaint=reinterpret_cast<Paint>(*slot);*slot=reinterpret_cast<uintptr_t>(&paint);
    DWORD ignored;VirtualProtect(slot,4,old,&ignored);
    log("target equipment: native target paint installed\r\n");
}
}
