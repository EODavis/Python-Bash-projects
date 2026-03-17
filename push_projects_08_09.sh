#!/bin/bash
# =============================================================================
#  push_projects_08_09.sh
#  Pushes Projects 08 and 09 to GitHub as new public repos
#  GitHub user : EODavis
#  Base dir    : /projects/
#  Usage       : bash push_projects_08_09.sh
# =============================================================================

set -e

GITHUB_USER="EODavis"
BASE_DIR="/projects"

GREEN='\033[0;32m'; YELLOW='\033[1;33m'; CYAN='\033[0;36m'; RED='\033[0;31m'; NC='\033[0m'
log()  { echo -e "${CYAN}  ──▶  $1${NC}"; }
ok()   { echo -e "${GREEN}  ✅  $1${NC}"; }
warn() { echo -e "${YELLOW}  ⚠️   $1${NC}"; }
fail() { echo -e "${RED}  ✗   $1${NC}"; exit 1; }

echo ""
echo "============================================================"
echo "  🚀  Python Portfolio — Push Projects 08–09"
echo "  User    : $GITHUB_USER"
echo "  Base dir: $BASE_DIR"
echo "============================================================"
echo ""

command -v git >/dev/null 2>&1 || fail "git not found."
command -v gh  >/dev/null 2>&1 || fail "GitHub CLI (gh) not found."
gh auth status >/dev/null 2>&1 || fail "Not logged in. Run: gh auth login"
ok "GitHub CLI authenticated"

declare -a PROJECTS=(
  "project_08_directory_tree|py-directory-tree|Renders directory structures as text trees, markdown, or JSON. Supports depth limits, file sizes, dates, and glob-pattern filtering. Zero dependencies.|python,file-automation,cli,visualization,portfolio"
  "project_09_log_summarizer|py-log-summarizer|Reads raw .log files, extracts events by regex, deduplicates messages, computes a health score, and produces console/markdown/JSON digests.|python,log-analysis,cli,regex,portfolio"
)

for entry in "${PROJECTS[@]}"; do
  IFS="|" read -r FOLDER REPO DESCRIPTION TOPICS <<< "$entry"
  PROJECT_DIR="$BASE_DIR/$FOLDER"

  echo ""
  echo "────────────────────────────────────────────────────────────"
  echo "  📁  $REPO"
  echo "       $PROJECT_DIR"
  echo "────────────────────────────────────────────────────────────"

  [ -d "$PROJECT_DIR" ] || fail "Folder not found: $PROJECT_DIR"
  cd "$PROJECT_DIR"

  find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
  find . -name "*.pyc" -delete 2>/dev/null || true
  log "Cleaned __pycache__"

  [ -f ".gitignore" ] || cat > .gitignore << 'GITIGNORE'
__pycache__/
*.pyc
.pytest_cache/
logs/
output/
test_data/workspace/
test_data/inbox/
.DS_Store
GITIGNORE

  [ -f "requirements.txt" ] || echo "# No external dependencies — stdlib only" > requirements.txt

  if [ ! -d ".git" ]; then
    log "Initialising git repo (main branch)..."
    git init -b main
    ok "git init done"
  else
    warn "Git already initialised — skipping init"
  fi

  log "Staging all files..."
  git add .
  echo ""; git status --short; echo ""

  if git diff --cached --quiet; then
    warn "Nothing to commit — already up to date"
  else
    log "Committing..."
    git commit -m "feat: initial implementation

Part of the 120-project Python × Shell × GitHub portfolio by @$GITHUB_USER.

Includes:
  - Core script with full CLI
  - Unit test suite (stdlib only)
  - Synthetic test data generator
  - README with badges, usage, and skills
  - .gitignore and requirements.txt"
    ok "Commit created"
  fi

  if gh repo view "$GITHUB_USER/$REPO" >/dev/null 2>&1; then
    warn "Repo $GITHUB_USER/$REPO already exists — skipping create"
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

  if ! git remote get-url origin >/dev/null 2>&1; then
    git remote add origin "https://github.com/$GITHUB_USER/$REPO.git"
  fi

  log "Pushing to GitHub..."
  git push -u origin main
  ok "Pushed → https://github.com/$GITHUB_USER/$REPO"

  log "Setting repo topics..."
  IFS=',' read -ra TOPIC_LIST <<< "$TOPICS"
  TOPIC_FLAGS=""
  for t in "${TOPIC_LIST[@]}"; do TOPIC_FLAGS="$TOPIC_FLAGS --add-topic $t"; done
  gh repo edit "$GITHUB_USER/$REPO" $TOPIC_FLAGS 2>/dev/null && ok "Topics set" || warn "Topics failed (non-critical)"

done

echo ""
echo "============================================================"
echo -e "${GREEN}  🎉  Projects 08–09 pushed!${NC}"
echo "============================================================"
echo ""
echo "  Your new repos:"
for entry in "${PROJECTS[@]}"; do
  IFS="|" read -r FOLDER REPO REST <<< "$entry"
  echo -e "  ${CYAN}→  https://github.com/$GITHUB_USER/$REPO${NC}"
done
echo ""
