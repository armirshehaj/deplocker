#!/bin/bash
set -eo pipefail

# Works out whether a push changed the frontend, the backend or both, so the
# workflow runs only the checks those changes call for.
#
# Its argument is the commit from before the push. A part counts as changed
# when a file in its folder, frontend/ or backend/, changed since that commit;
# files elsewhere, like the top-level README, count for neither. If that
# commit is unavailable, as on a new branch's first push, both count. Each
# changed part is reported to later steps as frontend=true or backend=true.

before=$1

declare -A changed=()
if files=$(git diff --name-only "$before" HEAD 2>/dev/null); then
    echo "Files changed in this push:"
    sed 's/^/  /' <<< "$files"
    grep -q '^frontend/' <<< "$files" && changed[frontend]=true
    grep -q '^backend/' <<< "$files" && changed[backend]=true
else
    echo "No previous commit to compare with (new branch or force push), so everything gets checked."
    changed[frontend]=true changed[backend]=true
fi
echo
for part in frontend backend; do
    if [ "${changed[$part]}" ]; then
        echo "$part=true" >> "$GITHUB_OUTPUT"
        echo "${part^}: checks will run."
    else
        echo "${part^}: no changes, checks skipped."
    fi
done
