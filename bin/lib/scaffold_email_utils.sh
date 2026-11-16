#!/usr/bin/env bash

copy_email_only_utils() {
    local project_path="$1"
    if [[ "$INCLUDE_EMAIL" != "true" ]]; then
        rm -f "$project_path/src/utils/ms_office/outlook_gateway.py"
        return
    fi
    cp "$COMMON_TEMPLATE_ROOT/src/utils/signatures.py" "$project_path/src/utils/signatures.py"
    cp "$COMMON_TEMPLATE_ROOT/tests/unit/test_signatures.py" "$project_path/tests/unit/test_signatures.py"
    cp "$COMMON_TEMPLATE_ROOT/tests/unit/test_ms_office_outlook_gateway.py" \
        "$project_path/tests/unit/test_ms_office_outlook_gateway.py"
}
