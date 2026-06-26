# Git Workflow: Dev (Mac Mini) ↔ Production (iMac)

## Daily workflow

### On the Mac Mini (dev) — make changes and push

```bash
cd /Users/pete/Projects/CMMS

# Check what's changed
git status

# Stage, commit, and push
git add -A
git commit -m "Describe what you changed"
git push
```

### On the iMac (production) — pull and restart

```bash
cd /Users/pete/CMMS
git pull
# Uvicorn auto-restarts if running with --reload
```

## Rules

1. **Only edit code on the Mac Mini.** Never edit files on the iMac.
2. **Always test on localhost:8000 before pushing.**
3. **Commit often** — small commits with clear messages are easier to undo.
4. **Never force push** unless recovering from a disaster.

## Starting the dev server (Mac Mini)

```bash
cd /Users/pete/Projects/CMMS
export CMMS_SECRET_KEY="dev-key"
uvicorn cmms_ui:app --host 127.0.0.1 --port 8000 --reload
```

Open `http://localhost:8000`

## Starting production (iMac)

```bash
cd /Users/pete/CMMS
./startup.sh
```

Open `https://192.168.1.224:8000`

## Common situations

### See what's changed before committing

```bash
git status          # which files changed
git diff            # what changed in those files
```

### Undo changes to a file before committing

```bash
git checkout -- filename.py
```

### Undo the last commit (keep the files)

```bash
git reset --soft HEAD~1
```

### Production won't pull (divergent branches)

This means someone edited files on the iMac. Force it to match GitHub:

```bash
cd /Users/pete/CMMS
git fetch origin
git reset --hard origin/main
```

Then re-move any data files if needed:

```bash
mkdir -p data
mv cmms.db data/cmms.db 2>/dev/null
```

### Database schema changes

Schema changes don't travel through git (the database is gitignored). Run SQL changes manually on both machines:

```bash
# Mac Mini (dev)
sqlite3 /Users/pete/Projects/CMMS/data/cmms.db "ALTER TABLE ..."

# iMac (production)
sqlite3 /Users/pete/CMMS/data/cmms.db "ALTER TABLE ..."
```

### Files that are machine-specific (not in git)

| File | Why |
|------|-----|
| `data/cmms.db` | Each machine has its own database |
| `data/*.pem` | SSL certs (iMac only) |
| `data/asset_import.log` | Import logs |
| `startup.sh` | Different paths/keys per machine |
| `cmms.log` | Log file |

These are in `.gitignore` — git won't track or push them.

### Before a big change — create a branch

```bash
git checkout -b feature/my-new-feature
# make changes, test, commit
git checkout main
git merge feature/my-new-feature
git push
git branch -d feature/my-new-feature
```

This keeps `main` stable while you experiment.
