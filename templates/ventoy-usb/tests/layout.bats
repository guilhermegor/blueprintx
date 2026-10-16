#!/usr/bin/env bats

load helpers/common

@test "layout reproduces the measured drive tree exactly" {
    run "$CLI" layout
    [ "$status" -eq 0 ]
    expected="dotfiles
dotfiles/windows
dynfileos
isos
isos/Android
isos/Linux
isos/Linux/Desktop
isos/Linux/Rescue and Maintenance
isos/Linux/Security and Pentest
isos/Linux/Servers
isos/Others
isos/Windows
persistance
recovery_tools
temp
ventoy"
    actual="$(cd "$BUILD_DIR/drive" && find . -mindepth 1 -type d | sed 's|^\./||' | sort)"
    diff <(printf '%s\n' "$expected") <(printf '%s\n' "$actual")
}

@test "layout never creates the local @tools folder on the drive" {
    run "$CLI" layout
    [ "$status" -eq 0 ]
    [ ! -e "$BUILD_DIR/drive/@tools" ]
}
