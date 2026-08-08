#!/data/data/com.termux/files/usr/bin/bash
# ------------------------------------------------------------------
# run_and_push.sh
# Esegue lo scraper Amazon e pubblica offerte.json su GitHub.
# Pensato per girare dentro Termux (Android).
# ------------------------------------------------------------------

set -e  # ferma lo script al primo errore

# --- CONFIGURA QUESTI 3 VALORI -------------------------------------
REPO_DIR="$HOME/amazon-deals-bot"          # dove hai clonato il repo
GIT_USER_NAME="Il Tuo Nome"
GIT_USER_EMAIL="tuaemail@example.com"
# ---------------------------------------------------------------------

cd "$REPO_DIR"

echo "[$(date '+%H:%M:%S')] Aggiorno il repo locale..."
git pull --quiet

echo "[$(date '+%H:%M:%S')] Eseguo lo scraper..."
python scraper/scrape_amazon.py

git config user.name "$GIT_USER_NAME"
git config user.email "$GIT_USER_EMAIL"

if git diff --quiet -- offerte.json; then
    echo "[$(date '+%H:%M:%S')] Nessuna modifica, nulla da pubblicare."
else
    echo "[$(date '+%H:%M:%S')] Pubblico su GitHub..."
    git add offerte.json
    git commit -m "Aggiorna offerte.json [termux]"
    git push
    echo "[$(date '+%H:%M:%S')] Fatto."
fi
