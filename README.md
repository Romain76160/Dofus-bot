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


## Identifier la build locale

Depuis le dossier `backend`, lance le diagnostic en donnant le dossier racine du client :

```powershell
python tools/diagnose_client.py "C:\chemin\vers\Dofus"
```

Le script est en lecture seule. Il cherche notamment :

- `GameAssembly.dll`
- `global-metadata.dat`
- `StreamingAssets/Content`
- les bundles `mapdata_assets_world_*.bundle`

Il affiche un rapport JSON avec les chemins, tailles et SHA-256. Ce rapport permet de savoir précisément à quelle build le profil réseau doit être associé.

## Endpoints d'observation

```text
GET  /health
GET  /api/state
GET  /api/network/status
POST /api/network/replay-hex
GET  /api/game-data/status
GET  /api/game-data/maps/{map_id}/interactions
WS   /ws
```

### maps.sqlite

Le backend reconnaît le schéma `maps.sqlite` produit par `ledouxm/dofus-sqlite` :

```text
map_interactions(mapId, worldId, gfxId, cellId, interactionId)
```

Place la base à l'emplacement configuré par `GAME_DATA_DB_PATH`.
