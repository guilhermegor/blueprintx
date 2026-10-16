#!/usr/bin/env bash

verify_hash() {
    local str_algo="$1" str_expected="$2" str_file="$3" str_actual
    str_actual="$("${str_algo}sum" "$str_file" | cut -d' ' -f1)"
    if [ "${str_actual,,}" != "${str_expected,,}" ]; then
        print_status "error" "$str_algo mismatch for $str_file: expected $str_expected, got $str_actual"
        return 1
    fi
}

verify_size() {
    local int_expected="$1" str_file="$2" int_actual
    int_actual="$(stat -c %s "$str_file")"
    if [ "$int_actual" != "$int_expected" ]; then
        print_status "error" "size mismatch for $str_file: expected $int_expected bytes, got $int_actual"
        return 1
    fi
}
