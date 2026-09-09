#pragma once
#include <stdint.h>

namespace autopotion {
enum class Mode { Percent=0, Interval=1, Both=2 };
struct Settings {
    uint32_t intervalMs;
    int missing;
    bool enabled;
};
struct State {
    uint32_t lastAttempt = 0;
    bool attempted = false;
};
struct Vitals {
    int current;
    int maximum;
};
inline int missingForPercent(int maximum,int percent) {
    if(maximum<=0||percent<1||percent>99)return 0;
    const int delta=100-percent;
    return (maximum/100)*delta+((maximum%100)*delta+99)/100;
}
inline bool due(const Settings &setting, const State &state, Vitals value,
                uint32_t now, bool alive, bool itemAvailable, bool blocked, Mode mode=Mode::Both) {
    if (!setting.enabled || !alive || !itemAvailable || blocked) return false;
    if (value.maximum <= 0 || value.current < 0 || value.current > value.maximum) return false;
    if (mode!=Mode::Percent && mode!=Mode::Interval && mode!=Mode::Both)return false;
    if (mode!=Mode::Interval && (setting.missing<1 || value.maximum-value.current<setting.missing))return false;
    if (mode==Mode::Percent)return true;
    if (setting.intervalMs==0 || setting.intervalMs>600000)return false;
    return !state.attempted || static_cast<uint32_t>(now-state.lastAttempt)>=setting.intervalMs;
}
inline void attempted(State &state, uint32_t now) {
    state.lastAttempt = now;
    state.attempted = true;
}
}
