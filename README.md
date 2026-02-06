# OpenClaw Frontend (LibreChat Fork)

This is a fork of LibreChat customized for OpenClaw.

## Setup

1. Copy `.env.example` to `.env` and fill in your values
2. Never commit `.env` - it contains secrets!

## Git Strategy: Keeping Upstream Updates

This repo is a **fork** of LibreChat. To get updates from upstream while keeping your changes:

### Initial Setup (One-time)

```bash
# Add LibreChat as upstream
git remote add upstream https://github.com/danny-avila/LibreChat.git
```

### Getting Updates (Monthly/Quarterly)

```bash
# Fetch upstream changes
git fetch upstream

# Create a branch for the update
git checkout -b update-from-upstream

# Merge upstream changes
git merge upstream/main

# Resolve any conflicts
# Test your application
# Then merge back to main
```

### Workflow

1. **Your changes**: Work on `main` or feature branches
2. **Upstream updates**: 
   - Fetch from upstream
   - Test in a branch
   - Merge when ready
3. **Conflicts**: Handle manually in the merge branch

## Important Files

- `.env` - Secrets (not committed)
- `librechat.yaml` - LibreChat config (customize as needed)
- Custom frontend changes - Track these carefully

## Security

⚠️ **Never commit:**
- `.env` files
- API keys
- JWT secrets
- Database files in `data-node/`
