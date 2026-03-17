#!/bin/bash
# =============================================================================
#  push_to_github.sh
#  Initialises and pushes Projects 01, 02, 03 to GitHub
#  GitHub user : EODavis
#  Usage       : bash push_to_github.sh
# =============================================================================

set -e  # Exit immediately on any error

GITHUB_USER="EODavis"
BASE_DIR="/projects"

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
RED='\033[0;31m'
NC='\033[0m' # No Colour

log()  { echo -e "${CYAN}  ──▶  $1${NC}"; }
ok()   { echo -e "${GREEN}  ✅  $1${NC}"; }
warn() { echo -e "${YELLOW}  ⚠️   $1${NC}"; }
fail() { echo -e "${RED}  ✗   $1${NC}"; exit 1; }

# ─── PRE-FLIGHT CHECKS ───────────────────────────────────────────────────────

echo ""
echo "============================================================"
echo "  🚀  Python Portfolio — GitHub Push Script"
echo "  User : $GITHUB_USER"
echo "============================================================"
echo ""

command -v git >/dev/null 2>&1 || fail "git not found. Please install git."
command -v gh  >/dev/null 2>&1 || fail "GitHub CLI (gh) not found. Install from https://cli.github.com"

log "Checking GitHub auth..."
gh auth status >/dev/null 2>&1 || fail "Not logged into GitHub CLI. Run: gh auth login"
ok "GitHub CLI authenticated"

# ─── PROJECT DEFINITIONS ─────────────────────────────────────────────────────
# Format: "folder_name|repo_name|description|topics"

declare -a PROJECTS=(
  "project_01_file_organizer|py-file-organizer-bot|Automatically sorts messy folders into categorised subfolders by file type. Supports dry-run mode and CSV move-logging.|python,file-automation,cli,portfolio"
  "project_02_duplicate_finder|py-duplicate-finder|Recursively scans directories using SHA-256 hashing to detect duplicate files across folders. Outputs a CSV cleanup report.|python,file-automation,hashing,cli,portfolio"
  "project_03_bulk_renamer|py-bulk-file-renamer|Bulk renames files using composable strategies: slugify, snake_case, strip versions, dedupe words, date-prefix, sequential.|python,file-automation,cli,renaming,portfolio"
  "project_04_folder_snapshot|py-folder-snapshot|Cryptographic directory snapshots with diff engine detecting ADDED, DELETED, MODIFIED and MOVED files. Per-file history tracking.|python,file-automation,hashing,diffing,portfolio"
)

# ─── LOOP THROUGH EACH PROJECT ───────────────────────────────────────────────

for entry in "${PROJECTS[@]}"; do
  IFS="|" read -r FOLDER REPO_NAME DESCRIPTION TOPICS <<< "$entry"
  PROJECT_DIR="$BASE_DIR/$FOLDER"

  echo ""
  echo "────────────────────────────────────────────────────────────"
  echo "  📁  $REPO_NAME"
  echo "────────────────────────────────────────────────────────────"

  # Validate project folder exists
  [ -d "$PROJECT_DIR" ] || fail "Project folder not found: $PROJECT_DIR"
  cd "$PROJECT_DIR"

  # ── Clean up any leftover __pycache__ before committing ──────────────────
  find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
  find . -name "*.pyc" -delete 2>/dev/null || true

  # ── Ensure .gitignore is present ─────────────────────────────────────────
  if [ ! -f ".gitignore" ]; then
    log "Writing .gitignore..."
    cat > .gitignore << 'GITIGNORE'
__pycache__/
*.pyc
*.pyo
.env
.venv/
venv/
*.egg-info/
.pytest_cache/
dist/
build/
organised/
output/
logs/
test_data/
.DS_Store
Thumbs.db
GITIGNORE
  fi

  # ── Ensure requirements.txt is present ───────────────────────────────────
  if [ ! -f "requirements.txt" ]; then
    log "Writing requirements.txt..."
    echo "# No external dependencies — stdlib only" > requirements.txt
  fi

  # ── Git init ─────────────────────────────────────────────────────────────
  if [ ! -d ".git" ]; then
    log "Initialising git repo..."
    git init -b main
    ok "git init done"
  else
    warn "Git already initialised — skipping git init"
  fi

  # ── Stage all files ──────────────────────────────────────────────────────
  log "Staging files..."
  git add .
  git status --short

  # ── Commit ───────────────────────────────────────────────────────────────
  # Check if there's anything to commit
  if git diff --cached --quiet; then
    warn "Nothing new to commit — already up to date"
  else
    log "Committing..."
    git commit -m "feat: initial project scaffold and implementation

- Core script with full CLI interface
- Synthetic test data generator
- Unit test suite
- README with usage examples and skills learned
- .gitignore and requirements.txt

Part of the 120-project Python portfolio by @$GITHUB_USER"
    ok "Commit created"
  fi

  # ── Create GitHub repo (skip if already exists) ──────────────────────────
  log "Creating GitHub repo: $GITHUB_USER/$REPO_NAME ..."
  if gh repo view "$GITHUB_USER/$REPO_NAME" >/dev/null 2>&1; then
    warn "Repo already exists on GitHub — skipping creation"
  else
    gh repo create "$GITHUB_USER/$REPO_NAME" \
      --public \
      --description "$DESCRIPTION" \
      --source=. \
      --remote=origin \
      --push
    ok "Repo created and pushed: https://github.com/$GITHUB_USER/$REPO_NAME"
  fi

  # ── Add remote if not present ─────────────────────────────────────────────
  if ! git remote get-url origin >/dev/null 2>&1; then
    log "Adding remote origin..."
    git remote add origin "https://github.com/$GITHUB_USER/$REPO_NAME.git"
  fi

  # ── Push ─────────────────────────────────────────────────────────────────
  log "Pushing to GitHub..."
  git push -u origin main 2>/dev/null || git push --set-upstream origin main
  ok "Pushed → https://github.com/$GITHUB_USER/$REPO_NAME"

  # ── Set repo topics ──────────────────────────────────────────────────────
  log "Setting repo topics: $TOPICS"
  gh repo edit "$GITHUB_USER/$REPO_NAME" \
    --add-topic python \
    --add-topic portfolio \
    --add-topic file-automation \
    --add-topic cli 2>/dev/null || warn "Could not set topics (non-critical)"

done

# ─── FINAL SUMMARY ───────────────────────────────────────────────────────────

echo ""
echo "============================================================"
echo -e "${GREEN}  🎉  All 3 projects pushed to GitHub!${NC}"
echo "============================================================"
echo ""
echo "  Your repos:"
for entry in "${PROJECTS[@]}"; do
  IFS="|" read -r FOLDER REPO_NAME REST <<< "$entry"
  echo -e "  ${CYAN}→  https://github.com/$GITHUB_USER/$REPO_NAME${NC}"
done
echo ""
echo "  Next steps:"
echo "  1. Visit each repo and verify the README renders correctly"
echo "  2. Star your own repos (signals activity to GitHub)"
echo "  3. Pin your favourites on your GitHub profile"
echo "  4. Say 'next' to build Project 04: Smart Folder Snapshot 🚀"
echo ""
