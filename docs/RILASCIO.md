# RILASCIO.md — Come creare la release con il .exe su GitHub

Due strade: **A) GitHub Actions (consigliata, automatica)** oppure
**B) manuale dal tuo PC Windows**. Il workflow `A` e' gia' nel repo:
`.github/workflows/release.yml`.

---

## A) Release automatica con GitHub Actions (passi da eseguire una volta sola)

### 1. Allinea le versioni nel codice (esempio: nuova versione 0.5.0)
Modifica questi tre file portando lo stesso numero (senza "v"):

| File | Cosa cambiare | Esempio |
|---|---|---|
| `app/version.py` | variabile `__version__` | `"0.5.0"` |
| `installer/LIBRI.iss` | `#define AppVersion` | `"0.5.0"` |
| `latest_version.json` | campo `"version"` + `"changelog"` | `"0.5.0"` |

Il changelog di `latest_version.json` serve all'updater interno dell'app;
quello della Release lo scrive GitHub automaticamente dai commit
(`generate_release_notes: true`).

### 2. Commit + push sulla branch principale (`main`)
```powershell
git checkout main
git add app/version.py installer/LIBRI.iss latest_version.json
git commit -m "Release v0.5.0: generazione paragrafi assistita da AI"
git push origin main
```

### 3. Crea il tag e pubblicalo: e' LUI che innesca tutto
```powershell
git tag v0.5.0
git push origin v0.5.0
```

Appena GitHub riceve il tag `v*`, parte in automatico il job
**Pubblica release Windows** su un runner Windows gratuito.

### 4. Dove guardare l'andamento
Repo → scheda **Actions** → workflow "Pubblica release Windows".
Al termine (≈10-15 min) la Release appare in
**Releases** con due allegati:

- `LIBRI-Setup-v0.5.0.exe` → installer Inno Setup (la demo da scaricare);
- `LIBRI-v0.5.0-portable.zip` → cartella già pronta senza installazione.

Gli utenti scaricano il `.exe`; l'app installata controlla gli aggiornamenti
leggendo `latest_version.json` dal branch `main`.

### Note sul workflow
- Nessun secret aggiuntivo: basta `GITHUB_TOKEN` con permesso
  `contents: write` (gia' impostato nel file).
- Se il repository ha **"Restrict access to releases"** attivo, disattivalo
  in Settings → Actions → General, altrimenti il publish fallisce.
- PyInstaller gira su Windows perché l'exe deve nascere su Windows: per
  questo il runner e' `windows-latest`.

---

## B) Alternativa manuale (senza Actions)

Sul tuo PC Windows, nella cartella del progetto:

```powershell
pip install pyinstaller
pyinstaller libri.spec --noconfirm          # crea dist\LIBRI\LIBRI.exe
```

Poi compila l'installer con Inno Setup (apri `installer\LIBRI.iss`
e premi Ctrl+F9): genera `dist\LIBRI-Setup-0.5.0.exe`.

Infine su GitHub.com: **Releases → Draft a new release** → scegli o crea il
tag `v0.5.0` → trascina il `.exe` (e lo zip) in "Assets" → Publish.

In questo caso ricordati comunque di fare commit+push dei tre file di
versione e di aggiornare `latest_version.json` su `main`, altrimenti
l'updater interno degli utenti non vedrà la nuova release.

---

## Checklist pre-rilascio (rapida)
- [ ] `python main.py` si avvia senza errori dalla root del repo
- [ ] `pytest tests/` verde (inclusi i test AI offline)
- [ ] Modalità manuale ancora funzionante (regola d'oro: l'AI produce solo bozze)
- [ ] Numeri di versione allineati nei 3 file
- [ ] Changelog di `latest_version.json` aggiornato
