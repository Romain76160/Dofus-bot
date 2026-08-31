# Dofus Hybrid Bot

Architecture expérimentale pour piloter un client Dofus sur un **serveur privé où l'automatisation est autorisée**.

Le projet combine trois sources d'observation :

- **réseau (lecture seule)** pour les événements/IDs lorsqu'ils sont disponibles ;
- **données locales du client** pour les maps, cellules et interactifs ;
- **vision OpenCV** pour confirmer l'état réellement affiché à l'écran.

Les actions restent séparées derrière un contrôleur d'entrée désactivé par défaut.

## Stack

- Backend : Python, FastAPI, WebSocket
- Vision : MSS + OpenCV
- Frontend : Next.js + TypeScript
- État : GameState unifié avec provenance/confiance

## Flux

```text
Dofus
 ├─ réseau observé ──────┐
 ├─ données client ──────┼─> StateStore / GameState ─> Bot Manager
 └─ capture écran ───────┘                │
                                          ├─> WebSocket -> Next.js
                                          └─> Input Controller (off par défaut)
```

## Démarrage backend

```bash
cd backend
python -m venv .venv
# Windows
.venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

Docs API : http://127.0.0.1:8000/docs

## Démarrage frontend

```bash
cd frontend
npm install
npm run dev
```

Dashboard : http://localhost:3000

## Objectif du premier jalon

Afficher en temps réel dans le dashboard :

- `map_id`
- `player_cell`
- événements observés
- état vision
- provenance de chaque donnée

Aucun clic automatique n'est requis pour ce premier jalon.
