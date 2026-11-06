#!/usr/bin/env bash
# Finds new Helium Windows builds, turns their symbols into small Windhawk cache
# files and publishes them on the symbol-cache branch.
# Needs: GH_TOKEN (read access to public repos), git push rights to this repo.
set -euo pipefail

SRC_REPO="imputnet/helium-windows"
SRC_WORKFLOW="main.yml"                     # "Build and release binaries"
ARTIFACT="helium-windows-x86_64-symbols"
CACHE_DIR="helium-acrylic-cache-v1"
BRANCH="symbol-cache"
MAX_BUILDS="${MAX_BUILDS:-2}"
FORCE_RUN="${FORCE_RUN:-}"
WORK="${RUNNER_TEMP:-/tmp}/helium-cache"
TOOLS="$(cd "$(dirname "$0")" && pwd)"

mkdir -p "$WORK"
PUB="$WORK/publish"
rm -rf "$PUB"

# Check out (or create) the data branch in its own folder.
REMOTE="$(git -C "$TOOLS/.." remote get-url origin)"
if git ls-remote --exit-code --heads "$REMOTE" "$BRANCH" >/dev/null 2>&1; then
  git clone --quiet --depth 1 --branch "$BRANCH" "$REMOTE" "$PUB"
else
  git init --quiet "$PUB"
  git -C "$PUB" checkout --quiet --orphan "$BRANCH"
  git -C "$PUB" remote add origin "$REMOTE"
  printf '# Helium Acrylic symbol cache\n\nSmall Windhawk symbol files, generated automatically. Do not edit.\n' > "$PUB/README.md"
fi
mkdir -p "$PUB/$CACHE_DIR" "$PUB/processed"

echo "Looking for recent successful '$SRC_WORKFLOW' runs in $SRC_REPO..."
RUNS=$(gh api "repos/$SRC_REPO/actions/workflows/$SRC_WORKFLOW/runs?status=success&per_page=10" \
        --jq '.workflow_runs[] | "\(.id) \(.created_at)"')
if [ -n "$FORCE_RUN" ]; then RUNS="$FORCE_RUN manual"; fi

done_count=0
while read -r RUN_ID CREATED; do
  [ -z "$RUN_ID" ] && continue
  [ "$done_count" -ge "$MAX_BUILDS" ] && break
  if [ -z "$FORCE_RUN" ] && [ -f "$PUB/processed/$RUN_ID.json" ]; then
    echo "Run $RUN_ID already processed."
    continue
  fi
  ART=$(gh api "repos/$SRC_REPO/actions/runs/$RUN_ID/artifacts?per_page=100" \
        --jq ".artifacts[] | select(.name == \"$ARTIFACT\" and .expired == false) | .id" | head -n1)
  if [ -z "$ART" ]; then
    echo "Run $RUN_ID ($CREATED): no live $ARTIFACT artifact, skipping."
    continue
  fi

  echo "Run $RUN_ID ($CREATED): downloading artifact $ART (about 1.5 GB)..."
  rm -rf "$WORK/build"; mkdir -p "$WORK/build"
  curl -fsSL --retry 3 -H "Authorization: Bearer $GH_TOKEN" -H "Accept: application/vnd.github+json" \
       -o "$WORK/build/symbols.zip" "https://api.github.com/repos/$SRC_REPO/actions/artifacts/$ART/zip"
  unzip -q -j -o "$WORK/build/symbols.zip" chrome.dll chrome.dll.pdb -d "$WORK/build"
  rm -f "$WORK/build/symbols.zip"

  python3 "$TOOLS/make_cache.py" "$WORK/build/chrome.dll" "$WORK/build/chrome.dll.pdb" \
          "$PUB/$CACHE_DIR" | tee "$WORK/build/summary.json"
  python3 - "$WORK/build/summary.json" "$PUB/processed/$RUN_ID.json" "$RUN_ID" "$CREATED" <<'EOF'
import json, sys
s = json.load(open(sys.argv[1]))
s.pop("file", None)
s["sourceRun"] = "https://github.com/imputnet/helium-windows/actions/runs/" + sys.argv[3]
s["sourceRunCreated"] = sys.argv[4]
json.dump(s, open(sys.argv[2], "w"), indent=2)
EOF
  rm -rf "$WORK/build"
  done_count=$((done_count + 1))
done <<< "$RUNS"

cd "$PUB"
git add -A
if git diff --cached --quiet; then
  echo "Nothing new to publish."
  exit 0
fi
git -c user.name="github-actions[bot]" -c user.email="41898282+github-actions[bot]@users.noreply.github.com" \
    commit --quiet -m "Update Helium symbol cache"
git push --quiet origin "$BRANCH"
echo "Published:"; git show --stat --oneline HEAD | tail -n +2
