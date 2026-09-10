#!/bin/sh
# shellcheck shell=dash
# Generic pilot policy. Temperatures are millidegrees Celsius; RPM labels are
# nominal GPIO states, NOT tachometer measurements. Never source private config.

fan_curve() {
    # temperature previous-state low medium high hysteresis
    local t="$1" previous="$2" low="$3" medium="$4" high="$5" hyst="$6" state=0
    [ "$t" -lt "$low" ] || state=1
    [ "$t" -lt "$medium" ] || state=2
    [ "$t" -lt "$high" ] || state=3
    [ "$previous" -lt 1 ] || [ "$t" -lt "$((low-hyst))" ] || [ "$state" -ge 1 ] || state=1
    [ "$previous" -lt 2 ] || [ "$t" -lt "$((medium-hyst))" ] || [ "$state" -ge 2 ] || state=2
    [ "$previous" -lt 3 ] || [ "$t" -lt "$((high-hyst))" ] || [ "$state" -ge 3 ] || state=3
    echo "$state"
}

fan_now() { local t rest; read -r t rest </proc/uptime; echo "${t%%.*}"; }

fan_find() {
    local c
    for c in /sys/class/thermal/cooling_device*; do
        [ "$(cat "$c/type" 2>/dev/null)" = gpio-fan ] || continue
        [ "$(cat "$c/max_state")" = 3 ] || return 1
        echo "$c"; return 0
    done
    return 1
}

fan_take_control() {
    # Only this userspace owner drives the fan. Otherwise step_wise could undo
    # a CPU request. Disabled zones remain readable. Critical HDD/PHY limits
    # are explicitly reproduced below; the tripless CPU gains a limit too.
    local c="$1" z link
    for z in /sys/class/thermal/thermal_zone*; do
        for link in "$z"/cdev[0-9]*; do
            [ -L "$link" ] || continue
            [ "$(readlink -f "$link")" = "$(readlink -f "$c")" ] || continue
            [ "$(cat "$z/mode")" = disabled ] || echo disabled >"$z/mode" || return 1
            break
        done
    done
}

fan_full() {
    local c
    c="$(fan_find)" || return 1
    fan_take_control "$c" || return 1
    echo 3 >"$c/cur_state"
}

fan_temperature() {
    local value
    value="$(cat "$1" 2>/dev/null)" || return 1
    case "$value" in ''|*[!0-9]*) return 1;; esac
    # Reject zero, sentinel and implausible sensor readings conservatively.
    [ "$value" -ge 1000 ] && [ "$value" -le 150000 ] || return 1
    echo "$value"
}

fan_emergency() {
    fan_full || true
    logger -p daemon.crit -t ls420d-fan "THERMAL SHUTDOWN: $*"
    if [ -w /sys/class/rtc/rtc0/wakealarm ]; then
        echo 0 >/sys/class/rtc/rtc0/wakealarm
    fi
    /sbin/poweroff
}
