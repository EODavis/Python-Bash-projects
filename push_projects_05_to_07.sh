#!/bin/bash
# =============================================================================
#  push_projects_05_to_07.sh
#  Pushes Projects 05, 06, 07 to GitHub as new public repos
#  GitHub user : EODavis
#  Base dir    : /projects/
#  Usage       : bash push_projects_05_to_07.sh
# =============================================================================

set -e

GITHUB_USER="EODavis"
BASE_DIR="/projects"

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
RED='\033[0;31m'
NC='\033[0m'

log()  { echo -e "${CYAN}  ──▶  $1${NC}"; }
ok()   { echo -e "${GREEN}  ✅  $1${NC}"; }
warn() { echo -e "${YELLOW}  ⚠️   $1${NC}"; }
fail() { echo -e "${RED}  ✗   $1${NC}"; exit 1; }

# ─── PRE-FLIGHT ───────────────────────────────────────────────────────────────

echo ""
echo "============================================================"
echo "  🚀  Python Portfolio — Push Projects 05–07"
echo "  User    : $GITHUB_USER"
echo "  Base dir: $BASE_DIR"
echo "============================================================"
echo ""

command -v git >/dev/null 2>&1 || fail "git not found."
command -v gh  >/dev/null 2>&1 || fail "GitHub CLI (gh) not found. Run: gh auth login"
gh auth status >/dev/null 2>&1 || fail "Not logged into GitHub CLI. Run: gh auth login"
ok "GitHub CLI authenticated"

# ─── PROJECT DEFINITIONS ─────────────────────────────────────────────────────
# folder | repo-name | description | topics (comma-separated)

declare -a PROJECTS=(
  "project_05_file_age_auditor|py-file-age-auditor|Scans directories and classifies files into 5 age buckets. Flags stale files, detects sensitive credential files, generates CSV and HTML reports.|python,file-automation,cli,security,portfolio"
  "project_06_text_merger_splitter|py-text-merger-splitter|Merge files with TOC injection, split by lines/size/delimiter, and merge CSVs with automatic deduplication. Three tools in one CLI.|python,file-automation,cli,text-processing,portfolio"
  "project_07_watch_folder|py-watch-folder|Monitors a folder and auto-processes new/modified files via a JSON ruleset: move, copy, rename, archive, tag, alert. No third-party dependencies.|python,file-automation,cli,automation,portfolio"
)

# ─── LOOP ─────────────────────────────────────────────────────────────────────

for entry in "${PROJECTS[@]}"; do
  IFS="|" read -r FOLDER REPO DESCRIPTION TOPICS <<< "$entry"
  PROJECT_DIR="$BASE_DIR/$FOLDER"

  echo ""
  echo "────────────────────────────────────────────────────────────"
  echo "  📁  $REPO"
  echo "       $PROJECT_DIR"
  echo "────────────────────────────────────────────────────────────"

  # ── Validate folder exists ──────────────────────────────────────────────
  if [ ! -d "$PROJECT_DIR" ]; then
    fail "Folder not found: $PROJECT_DIR"
  fi

  cd "$PROJECT_DIR"

  # ── Clean pycache before committing ─────────────────────────────────────
  find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
  find . -name "*.pyc" -delete 2>/dev/null || true
  log "Cleaned __pycache__"

  # ── Ensure .gitignore exists ─────────────────────────────────────────────
  if [ ! -f ".gitignore" ]; then
    log "Writing .gitignore..."
    cat > .gitignore << 'GITIGNORE'
__pycache__/
*.pyc
*.pyo
.env
venv/
.pytest_cache/
logs/
output/
test_data/workspace/
test_data/inbox/
.DS_Store
Thumbs.db
GITIGNORE
  fi

  # ── Ensure requirements.txt exists ──────────────────────────────────────
  if [ ! -f "requirements.txt" ]; then
    echo "# No external dependencies — stdlib only" > requirements.txt
    log "Created requirements.txt"
  fi

  # ── Git init ─────────────────────────────────────────────────────────────
  if [ ! -d ".git" ]; then
    log "Initialising git repo (main branch)..."
    git init -b main
    ok "git init done"
  else
    warn "Git already initialised — skipping init"
  fi

  # ── Stage ────────────────────────────────────────────────────────────────
  log "Staging all files..."
  git add .
  echo ""
  git status --short
  echo ""

  # ── Commit ───────────────────────────────────────────────────────────────
  if git diff --cached --quiet; then
    warn "Nothing to commit — already up to date"
  else
    log "Committing..."
    git commit -m "feat: initial implementation

Part of the 120-project Python × Shell × GitHub portfolio by @$GITHUB_USER.

Includes:
  - Core script with full CLI
  - Unit test suite (stdlib only, no pytest required)
  - Synthetic test data generator
  - README with badges, usage examples, and skills learned
  - .gitignore and requirements.txt"
    ok "Commit created"
  fi

  # ── Create GitHub repo ───────────────────────────────────────────────────
  if gh repo view "$GITHUB_USER/$REPO" >/dev/null 2>&1; then
    warn "Repo $GITHUB_USER/$REPO already exists on GitHub"
  else
    log "Creating GitHub repo: $GITHUB_USER/$REPO ..."
    gh repo create "$GITHUB_USER/$REPO" \
      --public \
      --description "$DESCRIPTION" \
      --source=. \
      --remote=origin \
      --push
    ok "Repo created → https://github.com/$GITHUB_USER/$REPO"
  fi

  # ── Set remote if missing ────────────────────────────────────────────────
  if ! git remote get-url origin >/dev/null 2>&1; then
    log "Adding remote origin..."
    git remote add origin "https://github.com/$GITHUB_USER/$REPO.git"
  fi

  # ── Push ─────────────────────────────────────────────────────────────────
  log "Pushing to GitHub..."
  git push -u origin main
  ok "Pushed → https://github.com/$GITHUB_USER/$REPO"

  # ── Set topics ───────────────────────────────────────────────────────────
  log "Setting repo topics..."
  IFS=',' read -ra TOPIC_LIST <<< "$TOPICS"
  TOPIC_FLAGS=""
  for t in "${TOPIC_LIST[@]}"; do
    TOPIC_FLAGS="$TOPIC_FLAGS --add-topic $t"
  done
  gh repo edit "$GITHUB_USER/$REPO" $TOPIC_FLAGS 2>/dev/null && ok "Topics set" || warn "Topics failed (non-critical)"

done

# ─── SUMMARY ─────────────────────────────────────────────────────────────────

echo ""
echo "============================================================"
echo -e "${GREEN}  🎉  Projects 05–07 pushed!${NC}"
echo "============================================================"
echo ""
echo "  Your new repos:"
for entry in "${PROJECTS[@]}"; do
  IFS="|" read -r FOLDER REPO REST <<< "$entry"
  echo -e "  ${CYAN}→  https://github.com/$GITHUB_USER/$REPO${NC}"
done
echo ""
echo "  Suggested next steps:"
echo "  1. Visit each repo — verify README renders and files look right"
echo "  2. Pin your favourites on your GitHub profile page"
echo "  3. Run: bash push_projects_05_to_07.sh again anytime to push new commits"
echo ""
