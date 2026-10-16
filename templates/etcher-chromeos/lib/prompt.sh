#!/usr/bin/env bash

ask() {
    local _ask_value=""
    read -r -p "$2" _ask_value || true
    printf -v "$1" '%s' "$_ask_value"
}
