#!/bin/sh
# Save the current worktree as a tree under a new implementation baseline ref.
# Keep the temporary index beside the real index for split-index support.
# HEAD, real staging, and working files are preserved; stdout is the tree ID.
set -eu

if [ "$#" -ne 1 ]; then
    printf '%s\n' 'Usage: snapshot-tree.sh refs/baselines/impl/<loop-id>/<snapshot>' >&2
    exit 2
fi

snapshot_ref=$1
case "$snapshot_ref" in
    refs/baselines/impl/*) ;;
    *) printf '%s\n' 'Snapshot reference must be under refs/baselines/impl/.' >&2; exit 2 ;;
esac
git check-ref-format "$snapshot_ref"

snapshot_root=$(git rev-parse --show-toplevel)
snapshot_index=$(git -C "$snapshot_root" rev-parse --path-format=absolute --git-path index)
snapshot_temp_index=$(mktemp "${snapshot_index}.impl.XXXXXX")
trap 'rm -f "$snapshot_temp_index" "${snapshot_temp_index}.lock"' 0
trap 'exit 1' HUP INT TERM

if [ -f "$snapshot_index" ]; then
    cp "$snapshot_index" "$snapshot_temp_index"
else
    rm -f "$snapshot_temp_index"
fi

GIT_INDEX_FILE="$snapshot_temp_index" git -C "$snapshot_root" -c core.splitIndex=false add -A -- .
snapshot_tree=$(GIT_INDEX_FILE="$snapshot_temp_index" git -C "$snapshot_root" write-tree)
git -C "$snapshot_root" update-ref "$snapshot_ref" "$snapshot_tree" ''
printf '%s\n' "$snapshot_tree"
