# OpenClaw Frontend (LibreChat Fork)

This is a fork of LibreChat customized for OpenClaw.

## Setup

1. Copy `.env.example` to `.env` and fill in your values
2. Never commit `.env` - it contains secrets!

## Git Strategy: Keeping Upstream Updates

This repo is a **fork** of LibreChat. To get updates from upstream while keeping your changes:

### Repository Structure

You have **two remotes** configured:
- `origin` - Your GitHub repo (https://github.com/kokayicobb/openclaw-frontend-librechat)
- `upstream` - LibreChat official repo (https://github.com/danny-avila/LibreChat)

### Initial Setup (One-time)

```bash
# Add LibreChat as upstream (already done)
git remote add upstream https://github.com/danny-avila/LibreChat.git

# Verify remotes
git remote -v
```

### Your Daily Workflow

```bash
# Make your changes
git add .
git commit -m "Your custom changes"
git push origin main
```

### Getting LibreChat Updates (Monthly/Quarterly)

**Recommended approach - Test first:**

```bash
# 1. Fetch upstream changes
git fetch upstream

# 2. Create a test branch
git checkout -b test-upstream-update

# 3. Merge upstream changes
git merge upstream/main

# 4. Resolve any conflicts
#    - If librechat.yaml conflicts, keep YOUR version
#    - If docker-compose.yml conflicts, review carefully
#    - For frontend files, compare and merge manually

# 5. Test everything thoroughly
#    - Start the application
#    - Verify OpenClaw/OpenCode/ClaudeCode endpoints work
#    - Check your customizations are intact

# 6. If tests pass, merge to main
git checkout main
git merge test-upstream-update
git push origin main

# 7. Clean up
git branch -d test-upstream-update
```

### What to Watch For During Updates

**Files likely to conflict:**
- `librechat.yaml` - Contains your custom endpoints (OpenClaw, OpenCode, ClaudeCode)
- `docker-compose.yml` - May have upstream changes
- Frontend files - If you've customized UI components

**Your customizations to preserve:**
- OpenClaw endpoint configuration
- OpenCode endpoint configuration  
- ClaudeCode endpoint configuration
- Custom logos (suelo-logo.svg, opencode-logo.png)
- Proxy configurations (claude-proxy/, opencode-proxy/)

### If Conflicts Are Too Complex

Since you mentioned most work is "vibe coding":

```bash
# Skip the merge, start fresh approach:

# 1. Save your custom files somewhere safe
cp librechat.yaml ~/librechat-backup.yaml
cp -r claude-proxy/ ~/claude-proxy-backup/
cp -r opencode-proxy/ ~/opencode-proxy-backup/

# 2. Reset to upstream
git checkout main
git fetch upstream
git reset --hard upstream/main

# 3. Restore your custom files
cp ~/librechat-backup.yaml ./librechat.yaml
cp -r ~/claude-proxy-backup/ ./claude-proxy/
cp -r ~/opencode-proxy-backup/ ./opencode-proxy/

# 4. Commit and push
git add .
git commit -m "Reset to upstream + reapply OpenClaw customizations"
git push origin main --force
```

## Sandpack Self-Hosted Code Execution

LibreChat uses Sandpack for code artifacts. This setup includes a self-hosted bundler for better privacy and reliability.

### Setup

The Sandpack bundler files are already included in `sandpack-bundler/` and served via nginx.

### Configuration

Add to your `.env` file:
```bash
SANDPACK_BUNDLER_URL=http://localhost:3210/sandpack/
```

### After Docker Rebuilds

Vite generates new hashed filenames in `index.html` after each build. To update:

```bash
# After rebuilding LibreChat image
./update-index-html.sh
```

This copies the fresh `index.html` from the running container.

## Protected Files (Never Committed)

These are in `.gitignore` and won't be pushed to GitHub:
- `.env` - All API keys, secrets, and credentials
- `data-node/` - MongoDB database files
- `meili_data/` - Search index data

## Important Files to Track

- `librechat.yaml` - LibreChat config (keep your custom endpoints)
- `docker-compose.yml` - Docker setup
- `claude-proxy/proxy.py` - Claude proxy configuration
- `opencode-proxy/proxy.py` - OpenCode proxy configuration
- `suelo-logo.svg` - Custom logo
- `opencode-logo.png` - Custom logo

## Security Checklist

⚠️ **Before every push, verify:**
- [ ] `.env` is NOT in the commit
- [ ] No API keys in any committed files
- [ ] `data-node/` directory is NOT committed
- [ ] No `*.key`, `*.pem`, or `*.secret` files committed

## Quick Reference

```bash
# Check what's being committed (always do this before push!)
git status

# Check if sensitive files are properly ignored
git check-ignore -v .env data-node/

# View all remotes
git remote -v

# Fetch latest from LibreChat (without merging)
git fetch upstream

# See what changed in upstream
git log upstream/main --oneline -10
```

## Troubleshooting

**"Permission denied" when pushing:**
- Make sure you're authenticated with GitHub CLI: `gh auth status`
- Or use HTTPS with a personal access token

**"Merge conflict in librechat.yaml":**
- Keep YOUR version (with OpenClaw/OpenCode/ClaudeCode endpoints)
- Check if upstream added new features you want

**"Accidentally committed .env":**
```bash
# Remove from git but keep the file
git rm --cached .env
git commit -m "Remove .env from tracking"
git push origin main
# Then rotate your secrets immediately!
```
