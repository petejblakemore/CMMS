# Git Workflow: Dev (Mac Mini) ↔ Production

## Current setup

| Machine | Role | Path | Python |
| --- | --- | --- | --- |
| Mac Mini | Development | `/Users/pete/Projects/CMMS` | 3.9+ |
| iMac | Production (current) | `/Users/pete/CMMS` | 3.9 |
| Raspberry Pi | Production (planned) | TBD | 3.11 (Bookworm) |

## Daily workflow

### On the Mac Mini (dev) — make changes and push

```
cd /Users/pete/Projects/CMMS

# Check what's changed
git status

# Stage, commit, and push
git add -A
git commit -m "Describe what you changed"
git push
```

### On production — pull and restart

```
cd /path/to/CMMS
git pull
# Uvicorn auto-restarts if running with --reload
```

## Rules

1. **Only edit code on the Mac Mini.** Never edit files on the production server.
2. **Always test on localhost:8000 before pushing.**
3. **Commit often** — small commits with clear messages are easier to undo.
4. **Never force push** unless recovering from a disaster.

## Starting the dev server (Mac Mini)

```
cd /Users/pete/Projects/CMMS
export CMMS_SECRET_KEY="dev-key"
uvicorn cmms_ui:app --host 127.0.0.1 --port 8000 --reload
```

Open `http://localhost:8000`

## Starting production (iMac — current)

```
cd /Users/pete/CMMS
./startup.sh
```

Open `https://192.168.1.224:8000`

## Common situations

### See what's changed before committing

```
git status          # which files changed
git diff            # what changed in those files
```

### Undo changes to a file before committing

```
git checkout -- filename.py
```

### Undo the last commit (keep the files)

```
git reset --soft HEAD~1
```

### Production won't pull (divergent branches)

This means someone edited files on the production server. Force it to match GitHub:

```
cd /path/to/CMMS
git fetch origin
git reset --hard origin/main
```

### Database schema changes

Schema changes don't travel through git (the database is gitignored). Run SQL changes manually on both machines:

```
sqlite3 /path/to/data/cmms.db "ALTER TABLE ..."
```

### Files that are machine-specific (not in git)

| File | Why |
| --- | --- |
| `data/cmms.db` | Each machine has its own database |
| `data/*.pem` | SSL certs (production only) |
| `data/asset_import.log` | Import logs |
| `startup.sh` | Different paths/keys per machine |
| `cmms.log` | Log file |

These are in `.gitignore` — git won't track or push them.

### Before a big change — create a branch

```
git checkout -b feature/my-new-feature
# make changes, test, commit
git checkout main
git merge feature/my-new-feature
git push
git branch -d feature/my-new-feature
```

This keeps `main` stable while you experiment.

---

## Pi Migration Guide (planned)

### What moves

| Item | How |
| --- | --- |
| Code | `git clone` on the Pi |
| Database | Copy `data/cmms.db` from iMac to Pi via SCP or USB |
| SSL certs | Regenerate with `mkcert` for the Pi's IP address |
| Secret key | Generate a new one on the Pi |
| startup.sh | Create new with Pi paths |

### Setup steps

```
# 1. Install prerequisites
sudo apt update && sudo apt install -y python3 python3-pip python3-venv sqlite3

# 2. Clone the repo
git clone https://github.com/petejblakemore/CMMS.git
cd CMMS

# 3. Create venv and install dependencies
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# 4. Copy the database from iMac
mkdir -p data
scp pete@192.168.1.224:/Users/pete/CMMS/data/cmms.db data/cmms.db

# 5. Generate SSL certs (if serving HTTPS)
# Install mkcert, generate certs for the Pi's LAN IP

# 6. Generate a secret key
python3 -c "import secrets; print(secrets.token_hex(32))"

# 7. Create startup.sh
cat > startup.sh << 'EOF'
#!/bin/bash
cd /home/pete/CMMS
source .venv/bin/activate
export CMMS_SECRET_KEY="your-generated-key"
uvicorn cmms_ui:app --host 0.0.0.0 --port 8000 --reload \
  --ssl-keyfile=data/pi-key.pem \
  --ssl-certfile=data/pi.pem
EOF
chmod +x startup.sh

# 8. Optional: run as a systemd service for auto-start on boot
```

### systemd service (auto-start on boot)

Create `/etc/systemd/system/cmms.service`:

```ini
[Unit]
Description=Home CMMS
After=network.target

[Service]
User=pete
WorkingDirectory=/home/pete/CMMS
ExecStart=/home/pete/CMMS/.venv/bin/uvicorn cmms_ui:app --host 0.0.0.0 --port 8000 --ssl-keyfile=data/pi-key.pem --ssl-certfile=data/pi.pem
Environment=CMMS_SECRET_KEY=your-generated-key
Restart=always

[Install]
WantedBy=multi-user.target
```

Then:

```
sudo systemctl enable cmms
sudo systemctl start cmms
```

### After migration

Update the daily workflow to pull to the Pi instead of the iMac. The Mac Mini dev workflow stays the same.
