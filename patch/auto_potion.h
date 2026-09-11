// Local L2Killer prototype. Included inside the patch's anonymous namespace.
namespace potion {
using Tile = void (__thiscall *)(void *, int,int,int,int,int,int,int,int,void *,unsigned,int);
using GetUser = void *(__thiscall *)(void *);
using UseItem = unsigned (__thiscall *)(void *, unsigned);
using NormalText = unsigned (__thiscall *)(void *,int,int,unsigned,const wchar_t *,
    int,int,int,int,int,int,int,int,int,int,int);
NormalText normalText;
Tile tile;
GetUser getUser;
UseItem useItem;
unsigned char *moduleBase;
autopotion::Settings settings[4] = {{0,1,false},{0,1,false},{0,1,false},{0,1,false}};
autopotion::State states[4];
int slots[4] = {-1,-1,-1,-1};
unsigned itemIds[4] = {};
unsigned savedTypes[4]={};
bool savedEnabled[4]={},restorePending[4]={};
const char *typeKeys[4]={"CPItemType","HPItemType","MPItemType","QuickHPItemType"};
const char *enabledKeys[4]={"CPEnabled","HPEnabled","MPEnabled","QuickHPEnabled"};
const wchar_t *names[4] = {L"CP",L"HP",L"MANA",L"QUICK HP"};
const wchar_t *labels[4] = {L"CP",L"HP",L"MANA",L"QUICK HP"};
const int displayOrder[4]={0,1,2,3};
int percentages[4]={90,90,50,90},draftPercentages[4]={90,90,50,90};
bool draftEnabled[4]={};
int editing=-1;
unsigned editValue=0;
bool replaceDigits=false;
const char *intervalKeys[4] = {"CPIntervalMs","HPIntervalMs","MPIntervalMs","QuickHPIntervalMs"};
const char *percentKeys[4] = {"CPPercent","HPPercent","MPPercent","QuickHPPercent"};
int panelX=20, panelY=120, binding=-1;
bool collapsed=true, advanced=false;
void *configWindow=nullptr;
bool nativePainting=false;
void syncNativeWindow(void *self);
void hideNativeWindow();
bool nativeDragInput(HWND window,UINT message,WPARAM wparam,LPARAM lparam);
void *dialogBackdrop=nullptr;
unsigned draftIntervals[4]={0,0,0,0};
int modes[4]={},draftModes[4]={};
const char *modeKeys[4]={"CPMode","HPMode","MPMode","QuickHPMode"};
const wchar_t *modeNames[3]={L"Percent",L"Interval",L"% + interval"};
unsigned lastCharacterId=0;
WNDPROC previousWndProc=nullptr;
HWND inputWindow=nullptr;
bool ownedClick=false;
bool worldClickOwned=false;
bool nativeClickSequence=false;
Mouse originalBagUp=nullptr, originalShortcutUp=nullptr;
constexpr int width=300, height=270, compactWidth=154, compactHeight=34;
int panelWidth() {return collapsed?compactWidth:width;}
int panelHeight() {return collapsed?compactHeight:height+(advanced?140:0);}
void anchor(void *self) {
    if(!collapsed&&configWindow) {
        panelX=field<int>(configWindow,0x44);
        panelY=field<int>(configWindow,0x48);
        return;
    }
    const auto g=layout(self);
    int right=g.x+(g.horizontal?504:46);
    for(int i=1;i<g.bars;++i) {
        const int edge=g.x+g.dx(i)+(g.horizontal?504:46);
        if(edge>right)right=edge;
    }
    int top=g.y;
    for(int i=1;i<g.bars;++i)if(g.y+g.dy(i)<top)top=g.y+g.dy(i);
    panelX=collapsed?right-compactWidth:right;
    panelY=collapsed?top-compactHeight:g.y+46-panelHeight();
    if(panelY<0)panelY=0;
}

void decimal(wchar_t *out, unsigned value) {
    wchar_t tmp[16]; unsigned n=0;
    do {tmp[n++]=L'0'+value%10;value/=10;}while(value);
    for(unsigned i=0;i<n;++i)out[i]=tmp[n-i-1];
    out[n]=0;
}
void saveBinding(int i) {
    char text[16];wchar_t wide[16];decimal(wide,savedTypes[i]);unsigned j=0;
    do{text[j]=static_cast<char>(wide[j]);}while(wide[j++]);
    WritePrivateProfileStringA("AutoPotion",typeKeys[i],text,iniPath);
    WritePrivateProfileStringA("AutoPotion",enabledKeys[i],savedEnabled[i]?"1":"0",iniPath);
}
void releaseDragCursor() {
    // Exact operation performed by NConsoleWnd's native cursor unlock (0x6a460).
    field<unsigned>(moduleBase,0x2d57b4)=0;
}
void save() {
    WritePrivateProfileStringA("AutoPotion","TimingVersion","2",iniPath);
    for(int i=0;i<4;++i) {
        char text[16]; wchar_t wide[16];
        decimal(wide,settings[i].intervalMs);unsigned j=0;
        do{text[j]=static_cast<char>(wide[j]);}while(wide[j++]);
        WritePrivateProfileStringA("AutoPotion",intervalKeys[i],text,iniPath);
        decimal(wide,percentages[i]);j=0;
        do{text[j]=static_cast<char>(wide[j]);}while(wide[j++]);
        WritePrivateProfileStringA("AutoPotion",percentKeys[i],text,iniPath);
        char modeText[2]={static_cast<char>('0'+modes[i]),0};
        WritePrivateProfileStringA("AutoPotion",modeKeys[i],modeText,iniPath);
        savedEnabled[i]=draftEnabled[i];saveBinding(i);
    }
}
bool inside(int x,int y) {return x>=panelX&&x<panelX+panelWidth()&&y>=panelY&&y<panelY+panelHeight();}
void *item(void *self,int slot) {
    if(slot<0||slot>=120)return nullptr;
    if(!self)return nullptr;
    auto *entries=static_cast<unsigned char *>(field<void *>(self,0x200));
    if(!entries)return nullptr;
    auto *p=entries+slot*0x1cc0;
    if(field<int>(p,0x1b18)!=1||field<int>(p,0x1c98)!=1||!field<int>(p,0x1ca0))return nullptr;
    return p;
}
void *bag() {
    void *console=field<void *>(moduleBase,0x2c6ad4);
    void *game=console?field<void *>(console,0x3bf4):nullptr;
    void *inventory=game?field<void *>(game,0x120):nullptr;
    return inventory?field<void *>(inventory,0x10c):nullptr;
}
void *bagItem(void *grid,int index) {
    if(!grid || index<0 || index>=field<int>(grid,0x130) || index>=4096)return nullptr;
    void **items=field<void **>(grid,0x12c);
    return items?items[index]:nullptr;
}
void *boundItem(void *self,int channel) {
    if(slots[channel]!=-2)return item(self,slots[channel]);
    void *grid=bag();if(!grid)return nullptr;
    const int count=field<int>(grid,0x130);
    if(count<0||count>4096)return nullptr;
    for(int j=0;j<count;++j) {
        void *p=bagItem(grid,j);
        if(p&&field<unsigned>(p,0x1b1c)==itemIds[channel])return p;
    }
    return nullptr;
}
int dropRow(int x,int y) {
    if(!inside(x,y))return -1;
    x-=panelX;y-=panelY;
    if(collapsed)return x>=4&&x<124&&y>=4&&y<30?displayOrder[(x-4)/30]:-1;
    if(x<8||x>=42||y<34)return -1;
    const int row=(y-32)/48,local=(y-32)%48;
    return row<4&&local>=2&&local<36?displayOrder[row]:-1;
}
void rememberBinding(void *p,int row) {
    savedTypes[row]=field<unsigned>(p,0x1b20);
    savedEnabled[row]=false;restorePending[row]=false;saveBinding(row);
}
void bindBag(void *p,int row) {
    if(!p||row<0||row>=4)return;
    rememberBinding(p,row);
    slots[row]=-2;itemIds[row]=field<unsigned>(p,0x1b1c);
    settings[row].enabled=false;draftEnabled[row]=false;states[row]={};binding=-1;

    log("autopotion inventory bind: channel=");number(row);log("\r\n");
}
int __fastcall bagUp(void *grid,void *,unsigned flags,unsigned packed) {
    const int row=dropRow(packed&0xffff,packed>>16);
    if(row>=0) {
        if(field<int>(grid,0x138)&&!field<int>(grid,0x168)) {
            void *p=bagItem(grid,field<int>(grid,0x160));
            if(p&&field<unsigned>(p,0x1b1c)&&field<void *>(p,0))bindBag(p,row);
        }
        // A rejected panel drop must never fall through to the ground/drop path.
        field<int>(grid,0x160)=field<int>(grid,0x164)=-1;
        field<int>(grid,0x138)=field<int>(grid,0x168)=0;
        releaseDragCursor();
        return 1;
    }
    return originalBagUp(grid,flags,packed);
}
void bind(void *self,int slot) {
    void *p=item(self,slot);
    if(!p)return;
    const int i=binding;
    if(i<0||i>=4)return;
    rememberBinding(p,i);
    slots[i]=slot;itemIds[i]=field<unsigned>(p,0x1b1c);
    settings[i].enabled=false;draftEnabled[i]=false;states[i]={};binding=-1;

    log("autopotion bind: channel=");number(i);log(" slot=");number(slot);log("\r\n");
}
void finishEditing() {
    if(editing<0)return;
    if(editing>=8){editing=-1;return;}
    if(editing>=4){if(editValue<=600000)draftIntervals[editing-4]=editValue;}
    else if(editValue>=1&&editValue<=99)draftPercentages[editing]=static_cast<int>(editValue);
    editing=-1;
}
void beginSettings() {
    for(int i=0;i<4;++i){draftPercentages[i]=percentages[i];draftEnabled[i]=restorePending[i]?savedEnabled[i]:settings[i].enabled;draftIntervals[i]=settings[i].intervalMs;draftModes[i]=modes[i];}
    editing=-1;
}
bool editKey(UINT message,WPARAM key) {
    if(editing<0)return false;
    if(message==WM_CHAR) {
        if(key>=L'0'&&key<=L'9') {
            if(replaceDigits){editValue=0;replaceDigits=false;}
            const unsigned next=editValue*10+static_cast<unsigned>(key-L'0');
            if(next<=(editing>=4?600000u:99u))editValue=next;
        }else if(key==VK_BACK){editValue/=10;replaceDigits=false;}
        else if(key==VK_RETURN)finishEditing();
        else if(key==VK_ESCAPE)editing=-1;
        return true;
    }
    return (message==WM_KEYDOWN||message==WM_KEYUP)&&
        ((key>='0'&&key<='9')||(key>=VK_NUMPAD0&&key<=VK_NUMPAD9)||
         key==VK_BACK||key==VK_RETURN||key==VK_ESCAPE);
}
bool anyEnabled() {
    for(int i=0;i<4;++i)if(savedTypes[i]&&(settings[i].enabled||savedEnabled[i]))return true;
    return false;
}
void toggleAll(void *self) {
    const bool enable=!anyEnabled();
    for(int i=0;i<4;++i) {
        const bool configured=savedTypes[i]!=0;
        savedEnabled[i]=draftEnabled[i]=enable&&configured;
        settings[i].enabled=enable&&configured&&boundItem(self,i)&&(modes[i]==0||settings[i].intervalMs>0);
        if(enable&&configured&&!boundItem(self,i))restorePending[i]=true;
        saveBinding(i);
    }
    log(enable?"autopotion: quick enable saved\r\n":"autopotion: quick disable saved\r\n");
}
bool click(void *self,int x,int y) {
    if(inside(x,y)) {
        x-=panelX;y-=panelY;
        if(collapsed){if(x>=126){toggleAll(self);return true;}beginSettings();collapsed=false;binding=-1;anchor(self);return true;}
        if(y<28){if(!configWindow){editing=-1;collapsed=true;binding=-1;anchor(self);}return true;}
        finishEditing();
        if(y>=228&&y<254&&x>=106&&x<194) {
            for(int i=0;i<4;++i) {
                percentages[i]=draftPercentages[i];
                settings[i].intervalMs=draftIntervals[i];
                modes[i]=draftModes[i];
                settings[i].enabled=draftEnabled[i]&&boundItem(self,i)&&(modes[i]==0||settings[i].intervalMs>0);
                if(!boundItem(self,i)&&savedTypes[i])restorePending[i]=true;
            }
            save();
            log("autopotion: percentage settings applied\r\n");
            return true;
        }
        if(y>=255&&y<270){advanced=!advanced;anchor(self);return true;}
        if(advanced&&y>=280&&y<392) {
            const int row=displayOrder[(y-280)/28];
            if(x>=65&&x<185)draftModes[row]=(draftModes[row]+1)%3;
            if(x>=190&&x<210&&draftIntervals[row]>=100)draftIntervals[row]-=100;
            if(x>=211&&x<249){editing=row+4;editValue=draftIntervals[row];replaceDigits=true;}
            if(x>=251&&x<271&&draftIntervals[row]<600000)draftIntervals[row]=draftIntervals[row]>599900?600000:draftIntervals[row]+100;
            return true;
        }
        const int visual=(y-32)/48,local=(y-32)%48;
        if(y<32||visual<0||visual>3)return true;
        const int row=displayOrder[visual];
        if(x<44&&local<38){binding=row;return true;}
        if(x>=148&&x<190&&local<34){
            if(boundItem(self,row))draftEnabled[row]=!draftEnabled[row];
            return true;
        }
        if(local<34) {
            if(x>=190&&x<210&&draftPercentages[row]>1)--draftPercentages[row];
            if(x>=251&&x<271&&draftPercentages[row]<99)++draftPercentages[row];
            if(x>=211&&x<249){editing=row;editValue=draftPercentages[row];replaceDigits=true;}
        }
        return true;
    }
    finishEditing();
    if(binding>=0) {
        const int slot=layout(self).hit(x,y);
        if(slot>=0){bind(self,slot);return true;}
    }
    return false;
}
void *shortcut() {
    void *console=field<void *>(moduleBase,0x2c6ad4);
    void *game=console?field<void *>(console,0x3bf4):nullptr;
    void *self=game?field<void *>(game,0x15c):nullptr;
    return supported(self)?self:nullptr;
}
bool consumeWorldMouse(unsigned message,unsigned key) {
    // A registered NCWnd owns dispatch and hit testing while expanded.
    if(nativeClickSequence||(configWindow&&!collapsed))return false;
    const bool down=message==WM_LBUTTONDOWN||message==WM_LBUTTONDBLCLK||
        (message==WM_KEYDOWN&&key==VK_LBUTTON);
    const bool up=message==WM_LBUTTONUP||(message==WM_KEYUP&&key==VK_LBUTTON);
    if(!down&&!up)return false;
    if(!shortcut())return false;
    if(worldClickOwned) {
        if(up)worldClickOwned=false;
        return true;
    }
    POINT point{};
    HWND window=field<HWND>(moduleBase,0x2c6ad0);
    if(!window||!GetCursorPos(&point)||!ScreenToClient(window,&point))return false;
    if(!inside(point.x,point.y))return false;
    if(down)worldClickOwned=true;
    return true;
}
bool shortcutDrop(void *self,int x,int y) {
    if(!self||!field<void *>(self,0x1fc))return false;
    const int row=dropRow(x,y),selected=field<int>(self,0x278);
    if(row<0||!field<int>(self,0x260)||!item(self,selected))return false;
    binding=row;bind(self,selected);
    field<int>(self,0x25c)=field<int>(self,0x260)=0;
    field<int>(self,0x278)=field<int>(self,0x27c)=-1;
    field<int>(field<void *>(self,0x1fc),8+selected*0x14)=0;
    releaseDragCursor();
    log("autopotion: drop from shortcut accepted\r\n");return true;
}
int __fastcall shortcutUp(void *self,void *,unsigned flags,unsigned packed) {
    if(shortcutDrop(self,packed&0xffff,packed>>16))return 1;
    return originalShortcutUp(self,flags,packed);
}
void installDrops() {
    struct Hook {unsigned table,entry;Mouse *original;uintptr_t replacement;};
    const Hook hooks[]={
        {0x1b5358,0x975e0,&originalBagUp,reinterpret_cast<uintptr_t>(&bagUp)},
        {0x1ccdc0,0x1080a0,&originalShortcutUp,reinterpret_cast<uintptr_t>(&shortcutUp)}};
    for(const auto &h:hooks) {
        if(*h.original)continue;
        auto *slot=reinterpret_cast<uintptr_t *>(moduleBase+h.table+0x114);
        if(*slot!=reinterpret_cast<uintptr_t>(moduleBase+h.entry))continue;
        DWORD old=0;if(!VirtualProtect(slot,4,PAGE_READWRITE,&old))continue;
        *h.original=reinterpret_cast<Mouse>(*slot);*slot=h.replacement;
        DWORD ignored=0;VirtualProtect(slot,4,old,&ignored);
        log("autopotion: native drop hook installed\r\n");
    }
}
LRESULT CALLBACK windowProc(HWND window,UINT message,WPARAM wparam,LPARAM lparam) {
    if(message==WM_NCDESTROY) {
        const WNDPROC original=previousWndProc;
        previousWndProc=nullptr;inputWindow=nullptr;
        ownedClick=false;worldClickOwned=false;nativeClickSequence=false;
        return CallWindowProcW(original,window,message,wparam,lparam);
    }
    // A new physical press starts a new ownership sequence. Engine mouse
    // events are polled separately and may never deliver the previous release.
    // Do not let that old latch swallow a later shortcut or world click.
    if(message==WM_LBUTTONDOWN||message==WM_LBUTTONDBLCLK) {
        ownedClick=false;worldClickOwned=false;nativeClickSequence=false;
    }
    if(editKey(message,wparam))return 0;
    if(nativeDragInput(window,message,wparam,lparam))return 0;
    if((message==WM_LBUTTONDOWN||message==WM_LBUTTONDBLCLK)&&configWindow&&!collapsed) {
        const int x=static_cast<short>(LOWORD(lparam)),y=static_cast<short>(HIWORD(lparam));
        const int left=field<int>(configWindow,0x44),top=field<int>(configWindow,0x48);
        nativeClickSequence=x>=left&&x<left+width&&y>=top-20&&y<top+panelHeight();
        // The compact opener's mouse-up may have passed through native dispatch.
        // It must not leave ownership behind for the frame's next close click.
        ownedClick=false;worldClickOwned=false;
    }
    if(message==WM_LBUTTONUP&&nativeClickSequence) {
        const LRESULT result=CallWindowProcW(previousWndProc,window,message,wparam,lparam);
        nativeClickSequence=false;ownedClick=false;worldClickOwned=false;
        return result;
    }
    if((message==WM_LBUTTONDOWN || message==WM_LBUTTONDBLCLK)&&!(configWindow&&!collapsed)) {
        void *self=shortcut();
        // Remember ownership before a close/expand action moves the panel.
        worldClickOwned=self&&inside(static_cast<short>(LOWORD(lparam)),static_cast<short>(HIWORD(lparam)));
        if(self && click(self,static_cast<short>(LOWORD(lparam)),static_cast<short>(HIWORD(lparam)))) {
            ownedClick=true;
            return 0;
        }
    }
    if(message==WM_LBUTTONUP && ownedClick) {
        ownedClick=false;
        return 0;
    }
    if(message==WM_LBUTTONUP) {
        void *self=shortcut();
        const int x=static_cast<short>(LOWORD(lparam)),y=static_cast<short>(HIWORD(lparam));
        if(self && shortcutDrop(self,x,y))return 0;
        void *grid=bag();
        if(grid&&originalBagUp&&dropRow(x,y)>=0&&field<int>(grid,0x138)) {
            bagUp(grid,nullptr,0,static_cast<unsigned>(lparam));return 0;
        }
    }

    if(message==WM_KILLFOCUS || message==WM_CANCELMODE){ownedClick=false;worldClickOwned=false;nativeClickSequence=false;}
    return CallWindowProcW(previousWndProc,window,message,wparam,lparam);
}
void installInput() {
    if(previousWndProc)return;
    HWND window=field<HWND>(moduleBase,0x2c6ad0);
    if(!window)return;
    DWORD process=0;
    GetWindowThreadProcessId(window,&process);
    if(process!=GetCurrentProcessId())return;
    SetLastError(0);
    const LONG_PTR old=SetWindowLongPtrW(window,GWLP_WNDPROC,reinterpret_cast<LONG_PTR>(&windowProc));
    if(old){previousWndProc=reinterpret_cast<WNDPROC>(old);inputWindow=window;log("autopotion: viewport mouse input installed\r\n");}
}
void restoreBindings() {
    bool pending=false;for(bool value:restorePending)pending=pending||value;
    if(!pending)return;
    void *grid=bag();if(!grid)return;
    const int count=field<int>(grid,0x130);
    if(count<0||count>4096)return;
    for(int i=0;i<4;++i)if(restorePending[i]) {
        for(int j=0;j<count;++j) {
            void *p=bagItem(grid,j);
            if(!p||field<unsigned>(p,0x1b20)!=savedTypes[i]||!field<void *>(p,0))continue;
            slots[i]=-2;itemIds[i]=field<unsigned>(p,0x1b1c);
            settings[i].enabled=savedEnabled[i]&&(modes[i]==0||settings[i].intervalMs>0);
            draftEnabled[i]=settings[i].enabled;states[i]={};restorePending[i]=false;
            log("autopotion restored: channel=");number(i);log("\r\n");break;
        }
    }
}
#include "manual_item_priority.h"
bool manualItemInteraction(void *) {
    return manualRequestWaiting();
}
unsigned nextPotionChannel=0;
void tick(void *self) {
    void *console=field<void *>(moduleBase,0x2c6ad4);
    if(!console)return;
    // Validate the pointer chain used by NConsoleWnd::GetPlayer before calling it.
    void *p=field<void *>(console,0x54);if(!p)return;
    p=field<void *>(p,0x58);if(!p)return;
    p=field<void *>(p,0x38);if(!p)return;
    p=field<void *>(p,0);if(!p)return;
    p=field<void *>(p,0x3c);if(!p)return;
    void *actor=field<void *>(p,0x3a8);
    const unsigned characterId=actor?field<unsigned>(actor,0x60):0;
    // The User cache can replace its allocation during a status update.
    // Compare the local actor's object ID, never the cache pointer.
    if(characterId!=lastCharacterId) {
        for(int i=0;i<4;++i){settings[i].enabled=false;draftEnabled[i]=false;restorePending[i]=savedTypes[i]!=0;slots[i]=-1;itemIds[i]=0;}
        manualRequestPending=false;nextPotionChannel=0;
        lastCharacterId=characterId;
        log("autopotion character changed: id=");number(characterId);log("\r\n");
    }
    void *user=characterId?getUser(console):nullptr;
    if(!user)return;
    restoreBindings();
    const autopotion::Vitals values[4]={{field<int>(user,0x218),field<int>(user,0x214)},
        {field<int>(user,0x7c),field<int>(user,0x78)}, {field<int>(user,0x84),field<int>(user,0x80)}, {field<int>(user,0x7c),field<int>(user,0x78)}};
    const uint32_t now=GetTickCount();
    const bool manual=manualItemInteraction(self);
    const unsigned first=nextPotionChannel;
    unsigned requests[4]={};
    for(unsigned step=0;step<4;++step) {
        const unsigned i=(first+step)%4;
        settings[i].missing=autopotion::missingForPercent(values[i].maximum,percentages[i]);
        void *potion=boundItem(self,i);
        // Textures are renderer resources and can be reloaded independently
        // of the inventory item. They must not determine binding identity.
        const bool matches=potion&&field<unsigned>(potion,0x1b1c)==itemIds[i];
        if(!matches) {
            settings[i].enabled=false;
            restorePending[i]=savedTypes[i]!=0;
            // Keep the saved/user-selected intent while the bag is refreshing.
        }
        if(manual)continue;
        if(!autopotion::due(settings[i],states[i],values[i],now,values[1].current>0,matches,false,static_cast<autopotion::Mode>(modes[i])))continue;
        requests[i]=itemIds[i];
    }
    // Snapshot every eligible channel before native use can update inventory.
    // Dispatch all due channels in the same update; no shared cooldown or queue.
    bool dispatched=false;
    for(unsigned step=0;step<4;++step){
        const unsigned i=(first+step)%4;
        if(!requests[i])continue;
        if(!dispatched){nextPotionChannel=(i+1)%4;dispatched=true;}
        autopotion::attempted(states[i],now);
        useItem(console,requests[i]);
    }
}
void text(void *canvas,int x,int y,const wchar_t *s,unsigned color=0xffdcdcdc) {
    // NCanvas text, not the fixed glyph/number renderer at RVA 0x134d0.
    // The native epilogue is ret 0x3c: exactly 15 stack arguments.
    const int top=field<int>(canvas,0x54),bottom=field<int>(canvas,0x58),line=field<int>(canvas,0x5c);
    normalText(canvas,x,y,color,s,0,0,0,0,0,0,0,0,0,0,0);
    field<int>(canvas,0x54)=top;field<int>(canvas,0x58)=bottom;field<int>(canvas,0x5c)=line;
}
void background(void *self,void *canvas,int x,int y,int w,int h) {
    // Use only the flat interior of a native empty slot, not the full
    // shortcut strip with its repeated cell separators.
    void *texture=field<void *>(self,0x20c);
    tile(canvas,x,y,w,h,1,1,1,1,texture,255,1);
    if(w>2&&h>2)tile(canvas,x+1,y+1,w-2,h-2,16,16,1,1,texture,255,1);
}
void *compactToggleTextures[2]={};
bool compactToggleLoaded=false;
void activeEffect(void *self,void *canvas,int channel,int x,int y,int size=32) {
    if(!settings[channel].enabled)return;
    void *effect=field<void *>(self,0x214);
    if(!effect)return;
    const unsigned old=field<unsigned>(effect,0xb0);
    field<unsigned>(effect,0xb0)=0x41100000; // Same material setting as native active skills.
    tile(canvas,x,y,size,size,0,0,32,32,effect,255,1);
    field<unsigned>(effect,0xb0)=old;
}
void paint(void *self,void *canvas) {
    if(!nativePainting) {
        installInput();
        installDrops();
        installManualItemPriority();
        tick(self);
        syncNativeWindow(self);
        if(configWindow&&!collapsed)return;
    }
    anchor(self);
    const int oldX=field<int>(canvas,0x38),oldY=field<int>(canvas,0x3c);
    field<int>(canvas,0x38)=panelX;field<int>(canvas,0x3c)=panelY;
    pushClip(canvas,panelX,panelY,panelWidth(),panelHeight());
    background(self,canvas,0,0,panelWidth(),panelHeight());
    if(nativePainting&&dialogBackdrop) {
        // Use the actual dialog background, not the transparent item-slot center.
        for(int pass=0;pass<3;++pass)
            tile(canvas,1,1,panelWidth()-2,panelHeight()-2,16,16,1,1,dialogBackdrop,255,1);
    }
    if(collapsed) {
        for(int visual=0;visual<4;++visual) {
            const int i=displayOrder[visual],x=4+visual*30;void *p=boundItem(self,i);
            tile(canvas,x,4,26,26,0,0,34,34,field<void *>(self,0x20c),255,1);
            if(p)tile(canvas,x+1,5,24,24,0,0,32,32,field<void *>(p,0),255,1);
            else text(canvas,x+2,11,names[i],0xffdfbf78);
            if(p)activeEffect(self,canvas,i,x+1,5,24);
        }
        if(!compactToggleLoaded&&moduleBase) {
            using LoadTexture=void *(__thiscall *)(void *,const wchar_t *,int);
            auto load=reinterpret_cast<LoadTexture>(moduleBase+0x2b490);
            compactToggleTextures[0]=load(self,L"L2UI.Control.CheckBox",1);
            compactToggleTextures[1]=load(self,L"L2UI.Control.CheckBox_Checked",1);
            compactToggleLoaded=true;
        }
        background(self,canvas,127,4,24,26);
        void *toggle=compactToggleTextures[anyEnabled()?1:0];
        if(toggle)tile(canvas,131,9,16,16,0,0,16,16,toggle,255,1);
    } else {
        if(!configWindow){
            text(canvas,10,7,L"Auto Potion Settings",0xffdfbf78);
            text(canvas,279,7,L"x");
        }
        for(int visual=0;visual<4;++visual) {
            const int i=displayOrder[visual],y=32+visual*48;
            void *p=boundItem(self,i);
            tile(canvas,8,y+2,34,34,0,0,34,34,field<void *>(self,0x20c),255,1);
            if(p)tile(canvas,9,y+3,32,32,0,0,32,32,field<void *>(p,0),255,1);
            else text(canvas,18,y+10,L"+");
            if(p)activeEffect(self,canvas,i,9,y+3);
            const unsigned color=i==1?0xffff7777:i==2?0xff80b8ff:0xffdfbf78;
            text(canvas,50,y+3,labels[i],color);
            text(canvas,50,y+21,L"Use below",0xffb9b49f);
            background(self,canvas,148,y+6,40,24);
            text(canvas,151,y+10,draftEnabled[i]?L"On":L"Enable",draftEnabled[i]?0xff88dd88:0xffdfbf78);
            text(canvas,194,y+10,L"-");
            background(self,canvas,211,y+6,38,24);
            wchar_t digits[16];decimal(digits,editing==i?editValue:draftPercentages[i]);
            text(canvas,220,y+10,digits,editing==i?0xffffffff:0xffdcdcdc);
            text(canvas,255,y+10,L"+");text(canvas,274,y+10,L"%");
        }
        background(self,canvas,106,228,88,26);
        text(canvas,128,234,L"Apply",0xffdfbf78);
        text(canvas,10,256,advanced?L"[-] Advanced settings":L"[+] Advanced settings",0xffb9b49f);
        if(advanced) {
            for(int visual=0;visual<4;++visual) {
                const int i=displayOrder[visual],y=280+visual*28;
                text(canvas,10,y+5,labels[i],0xffdfbf78);
                text(canvas,65,y+5,modeNames[draftModes[i]]);
                text(canvas,194,y+5,L"-");
                wchar_t digits[16];decimal(digits,editing==i+4?editValue:draftIntervals[i]);
                text(canvas,217,y+5,digits);text(canvas,255,y+5,L"+");text(canvas,278,y+5,L"ms");
            }
            text(canvas,10,395,L"Percent: no delay. Interval: ms (1000 = 1s).",0xffb9b49f);
        }
    }
    popClip(canvas);field<int>(canvas,0x38)=oldX;field<int>(canvas,0x3c)=oldY;
}
#include "native_potion_window.h"
void init(unsigned char *base) {
    moduleBase=base;
    normalText=reinterpret_cast<NormalText>(base+0x12c20);
    tile=reinterpret_cast<Tile>(base+0x12f10);
    getUser=reinterpret_cast<GetUser>(base+0x73f30);
    useItem=reinterpret_cast<UseItem>(base+0x66480);
    const bool timingV2=GetPrivateProfileIntA("AutoPotion","TimingVersion",0,iniPath)==2;
    for(int i=0;i<4;++i){
        unsigned interval=GetPrivateProfileIntA("AutoPotion",intervalKeys[i],settings[i].intervalMs,iniPath);
        savedTypes[i]=GetPrivateProfileIntA("AutoPotion",typeKeys[i],0,iniPath);
        if(savedTypes[i]>10000000)savedTypes[i]=0;
        savedEnabled[i]=GetPrivateProfileIntA("AutoPotion",enabledKeys[i],0,iniPath)==1;
        restorePending[i]=savedTypes[i]!=0;
        int percent=GetPrivateProfileIntA("AutoPotion",percentKeys[i],percentages[i],iniPath);
        if(timingV2&&interval<=600000)settings[i].intervalMs=draftIntervals[i]=interval;
        int mode=timingV2?GetPrivateProfileIntA("AutoPotion",modeKeys[i],0,iniPath):0;
        if(mode>=0&&mode<=2)modes[i]=draftModes[i]=mode;
        if(percent>=1&&percent<=99)percentages[i]=draftPercentages[i]=percent;
    }
}
}
