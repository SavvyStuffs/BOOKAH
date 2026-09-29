#!/usr/bin/env bash
#
# BOOKAH history repair
# ---------------------
# Removes build artifacts that were never meant to be committed, from
# every commit in history, while preserving all 77 commits with their
# original messages, authors, dates and ordering.
#
# REMOVED:  venv/  venv_test/  build/  dist/  flatpak_native/
#           .flatpak-builder/  __pycache__/  *.pyc
# KEPT:     src/  onnx_model/  data/  icons/  *.db  *.dll  *.model
#           all source, all JSON, all docs, LICENSE
#
# This script does NOT push. It stops before that.
#
set -euo pipefail

REPO="/home/savvy/Projects/BOOKAH"
REMOTE_URL="git@github.com:SavvyStuffs/BOOKAH.git"
BACKUP="$HOME/BOOKAH-backup-$(date +%Y%m%d-%H%M%S).bundle"

cd "$REPO"
git rev-parse --git-dir > /dev/null

echo "==> Repo:    $(pwd)"
echo "==> Commits: $(git rev-list --count HEAD)"
git count-objects -vH | sed 's/^/    /'
echo

# ---------------------------------------------------------------------
# 0. Refuse to run on a dirty tree. Your prompt showed a '*', so there
#    may be uncommitted work -- a history rewrite would put it at risk.
# ---------------------------------------------------------------------
if ! git diff-index --quiet HEAD -- 2>/dev/null; then
  echo "!! Working tree has uncommitted changes:"
  git status --short | sed 's/^/     /'
  echo
  echo "   Commit or stash them first, then re-run:"
  echo "     git add -A && git commit -m 'wip'"
  echo "     # or:  git stash"
  exit 1
fi

# ---------------------------------------------------------------------
# 1. Full backup. Everything below is reversible from this one file:
#      git clone BACKUP.bundle recovered-repo
# ---------------------------------------------------------------------
echo "==> Writing backup bundle (~2.5 GiB, takes a minute)"
git bundle create "$BACKUP" --all
echo "    $BACKUP"
echo

# ---------------------------------------------------------------------
# 2. Clear the two orphaned temp objects (381 MiB) and repack.
# ---------------------------------------------------------------------
echo "==> Clearing garbage objects"
find .git/objects -name 'tmp_obj_*' -delete
git gc --prune=now --quiet
echo

# ---------------------------------------------------------------------
# 3. Require git-filter-repo.
# ---------------------------------------------------------------------
if ! command -v git-filter-repo > /dev/null 2>&1; then
  echo "!! git-filter-repo not found. Install with one of:"
  echo "     pipx install git-filter-repo"
  echo "     pip install --user git-filter-repo"
  echo "     sudo apt install git-filter-repo"
  exit 1
fi

# ---------------------------------------------------------------------
# 4. Pass 1: drop artifact directories from every commit.
#
#    Globs cover both folder spellings that exist in history --
#    'Old_App_Files_(Obsolete)' (current) and 'Old App Files (Obsolete)'
#    (an earlier rename, still carried in history) -- plus root copies.
#    In filter-repo globs, * matches '/' as well.
#
#    NOTE: *.onnx is deliberately NOT stripped. The model is being kept.
# ---------------------------------------------------------------------
echo "==> Pass 1: removing build artifacts from all 77 commits"
git filter-repo --force --invert-paths \
  --path-glob '*venv/*'              --path-glob 'venv/*' \
  --path-glob '*venv_test/*'         --path-glob 'venv_test/*' \
  --path-glob '*.venv/*'             --path-glob '.venv/*' \
  --path-glob '*build/*'             --path-glob 'build/*' \
  --path-glob '*dist/*'              --path-glob 'dist/*' \
  --path-glob '*flatpak_native/*'    --path-glob 'flatpak_native/*' \
  --path-glob '*.flatpak-builder/*'  --path-glob '.flatpak-builder/*' \
  --path-glob '*__pycache__/*' \
  --path-glob '*.pyc' \
  --path-glob '*.filez' \
  --path-glob '*.flatpak'
echo

# ---------------------------------------------------------------------
# 5. Pass 2: safety net for anything oversized left in an unexpected
#    path. 95 MiB is above the ONNX files (86.6 MiB) so they survive,
#    and below GitHub's 100 MiB hard block.
# ---------------------------------------------------------------------
echo "==> Pass 2: stripping any stray blob over 95 MiB"
git filter-repo --force --strip-blobs-bigger-than 95M
echo

# ---------------------------------------------------------------------
# 6. Replace the broken .gitignore.
#
#    The old one referenced 'Old_App_Code_(Obsolete)' but the folder is
#    actually 'Old_App_Files_(Obsolete)' -- Code vs Files -- so not one
#    of its rules ever matched. That is why the venv got committed.
#    It also used '//' double separators, which match nothing.
#
#    Rules below are root-relative and apply at any depth.
# ---------------------------------------------------------------------
echo "==> Writing corrected .gitignore"
cat > .gitignore <<'EOF'
# Python environments
venv/
venv_test/
.venv/
__pycache__/
*.py[cod]
*$py.class

# PyInstaller build output
build/
dist/
*.spec

# Flatpak packaging
flatpak_native/
.flatpak-builder/
*.filez
*.flatpak

# Installer tooling
installer_assets/
Bookah_Installer.iss

# Editor / test / logs
.vscode/
.pytest_cache/
*.log
tmp/

# Docker
.dockerignore
Dockerfile

# Note: UI_Bridge.dll, WebView2Loader.dll, onnx_model/ and the .db files
# are intentionally tracked -- they are shipped components of the
# archived application, not build artifacts.
EOF

git add .gitignore
git commit --quiet -F - <<'EOF'
Fix .gitignore and purge committed build artifacts

The previous .gitignore referenced Old_App_Code_(Obsolete)/ while the
actual directory is Old_App_Files_(Obsolete)/, so none of its rules
ever matched. As a result a Python virtualenv (including a 443 MB
libtorch_cpu.so), PyInstaller build/dist output and a Flatpak OSTree
repo were committed, pushing the repository past GitHub's 2 GiB push
limit and its 100 MB per-file limit.

History has been rewritten to remove those artifacts from all commits.
Source, data files, the ONNX model and shipped binaries are retained.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01NfSGeukBCir8QVFWdeN67E
EOF
echo

# ---------------------------------------------------------------------
# 7. filter-repo drops the remote by design. Restore it.
# ---------------------------------------------------------------------
git remote add origin "$REMOTE_URL" 2>/dev/null \
  || git remote set-url origin "$REMOTE_URL"

# ---------------------------------------------------------------------
# 8. Report.
# ---------------------------------------------------------------------
echo "========================================================"
echo "==> Done. Nothing has been pushed."
echo
echo "    Commits preserved: $(git rev-list --count HEAD)"
git count-objects -vH | grep -E 'size-pack' | sed 's/^/    /'
echo
echo "    Largest remaining blobs:"
git rev-list --objects --all \
  | git cat-file --batch-check='%(objecttype) %(objectname) %(objectsize) %(rest)' \
  | awk '$1=="blob"' | sort -k3 -nr | head -12 \
  | awk '{ printf "      %7.1f MB  ", $3/1048576;
           $1=""; $2=""; $3=""; sub(/^   /,""); print }'
echo
echo "    Backup: $BACKUP"
echo "========================================================"
echo
echo "    Sanity checks before pushing:"
echo "      git log --oneline | head -5      # history intact?"
echo "      ls -la                           # JSON files present?"
echo "      git show --stat HEAD             # .gitignore commit"
echo
echo "    Then push:"
echo "      cd $REPO"
echo "      git push --force origin HEAD:main"
echo
