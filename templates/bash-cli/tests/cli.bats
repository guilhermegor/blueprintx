#!/usr/bin/env bats
# Smoke coverage for bin/${PROJECT_NAME} — the "one runnable check" a lazy skeleton
# still owes its own logic (a case statement over --version/--help/unknown).

CLI="$BATS_TEST_DIRNAME/../bin/${PROJECT_NAME}"

@test "--version prints the project name and a version" {
    run "$CLI" --version
    [ "$status" -eq 0 ]
    [[ "$output" == "${PROJECT_NAME} "* ]]
}

@test "--help prints usage" {
    run "$CLI" --help
    [ "$status" -eq 0 ]
    [[ "$output" == "Usage: ${PROJECT_NAME}"* ]]
}

@test "no arguments prints usage" {
    run "$CLI"
    [ "$status" -eq 0 ]
    [[ "$output" == "Usage: ${PROJECT_NAME}"* ]]
}

@test "an unknown command fails with an error and usage" {
    run "$CLI" bogus-command
    [ "$status" -eq 1 ]
    [[ "$output" == *"Unknown command: bogus-command"* ]]
}
