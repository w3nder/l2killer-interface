#include "potion_policy.h"
#include <cassert>
#include <cstdio>
#include <initializer_list>
int main() {
    using namespace autopotion;
    assert(missingForPercent(1000,90)==100);
    assert(missingForPercent(4726,90)==473);
    assert(missingForPercent(1000,50)==500);
    assert(missingForPercent(2147483647,1)==2126008811);
    assert(missingForPercent(1000,0)==0);
    Settings percentSetting{3000,missingForPercent(4726,90),true};
    assert(due(percentSetting,State{},{4253,4726},100,true,true,false));
    assert(!due(percentSetting,State{},{4254,4726},100,true,true,false));
    Settings instant{0,100,true};State justUsed;attempted(justUsed,100);
    assert(due(instant,justUsed,{800,1000},100,true,true,false,Mode::Percent));
    assert(!due(instant,justUsed,{1000,1000},100,true,true,false,Mode::Percent));
    assert(!due(instant,justUsed,{800,1000},100,true,true,false,Mode::Interval));
    instant.intervalMs=100;
    assert(due(instant,justUsed,{1000,1000},200,true,true,false,Mode::Interval));
    assert(!due(instant,justUsed,{1000,1000},200,true,true,false,Mode::Both));
    assert(due(instant,justUsed,{800,1000},200,true,true,false,Mode::Both));
    Settings cp{3000, 200, false}; State state;
    assert(!due(cp, state, {0,1508}, 100, true, true, false));
    cp.enabled = true;
    assert(due(cp, state, {1308,1508}, 100, true, true, false));
    assert(!due(cp, state, {1309,1508}, 100, true, true, false));
    assert(!due(cp, state, {0,1508}, 100, false, true, false));
    assert(!due(cp, state, {0,1508}, 100, true, false, false));
    assert(!due(cp, state, {0,1508}, 100, true, true, true));
    for (Vitals bad : {Vitals{-1,1508}, Vitals{1509,1508}, Vitals{0,0}})
        assert(!due(cp, state, bad, 100, true, true, false));
    attempted(state, 100);
    assert(!due(cp, state, {0,1508}, 3099, true, true, false));
    assert(due(cp, state, {0,1508}, 3100, true, true, false));
    attempted(state, UINT32_MAX - 1000);
    assert(!due(cp, state, {0,1508}, 1998, true, true, false));
    assert(due(cp, state, {0,1508}, 1999, true, true, false));
    std::puts("Potion policy: disabled state, deficit threshold, cooldown, wraparound, invalid stats, death and missing item passed");
}
