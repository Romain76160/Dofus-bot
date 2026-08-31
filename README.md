# Dofus Hybrid Observer

Architecture expérimentale d'observation d'un client Dofus sur un **serveur privé où l'automatisation est autorisée**.

Le projet combine plusieurs sources en lecture seule :

- **réseau brut** : replay de flux encadrés + profil de build Protobuf ;
- **réseau déjà décodé** : ingestion JSON et discovery sémantique de map/cellule ;
- **données locales** : maps.sqlite pour les interactifs statiques ;
- **vision** : capture limitée à la zone cliente de la fenêtre Dofus.

Les actions clavier/souris restent séparées et désactivées par défaut.

## Stack

- Backend : Python 3.12, FastAPI, WebSocket
- Réseau : framing heuristique + Protobuf wire parser + profils de build
- Données : SQLite en mode lecture seule
- Vision : MSS + OpenCV chargés à la demande
- Frontend : Next.js + TypeScript
- État : GameState avec source, confiance et historique d'observations

## Flux

~~~text
Décodeur externe JSON ───────────┐
Flux brut / replay + profil ─────┼──> StateStore / GameState ──> WebSocket
maps.sqlite ─────────────────────┤              │
Fenêtre Dofus / vision ──────────┘              └──> Dashboard
~~~

Lorsqu'un map_id sûr est accepté, le backend charge automatiquement les interactifs correspondants depuis maps.sqlite.

## Backend

~~~bash
cd backend
python -m venv .venv

# Windows
.venv\Scripts\activate

pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
~~~

Documentation API :

~~~text
http://127.0.0.1:8000/docs
~~~

## Frontend

~~~bash
cd frontend
npm install
npm run dev
~~~

Dashboard :

~~~text
http://localhost:3000
~~~

Le WebSocket se reconnecte automatiquement avec backoff en cas de coupure.

## Réseau : deux modes complémentaires

### 1. Replay brut

Le décodeur historique reste disponible :

~~~text
POST /api/network/replay-hex
~~~

Il détecte le framing, extrait les enveloppes Protobuf et applique les règles du profil configuré dans NETWORK_PROFILE_PATH.

### 2. Événements JSON déjà décodés

Un décodeur ou outil externe peut envoyer des événements sémantiques :

~~~json
{
  "message_type": "map_update",
  "direction": "server_to_client",
  "wire_key": "optional-build-key",
  "payload": {
    "mapId": 191105026,
    "character": {
      "cellId": 287
    }
  }
}
~~~

Endpoints :

~~~text
POST /api/network/ingest
POST /api/network/ingest-batch
GET  /api/network/debug
GET  /api/network/events
POST /api/network/reset
~~~

Le discovery est volontairement conservateur : un cellId générique d'un monstre/PNJ est affiché comme candidat de debug mais n'est pas automatiquement appliqué à player_cell.

Pour une source JSONL :

~~~bash
cd backend
python tools/forward_jsonl.py capture.jsonl
~~~

Ou depuis stdin :

~~~bash
some_decoder --jsonl | python tools/forward_jsonl.py -
~~~

## maps.sqlite

Le backend reconnaît la table générée par dofus-sqlite :

~~~text
map_interactions(mapId, worldId, gfxId, cellId, interactionId)
~~~

La base est ouverte avec SQLite mode=ro.

Installation assistée :

~~~bash
cd backend
python tools/setup_maps_sqlite.py
~~~

Le script calcule le SHA-256 et le compare au digest de release lorsque GitHub en fournit un. Il accepte aussi un hash explicitement épinglé avec --sha256.

Endpoints :

~~~text
GET /api/game-data/status
GET /api/game-data/maps/{map_id}/interactions
GET /api/game-data/maps/{map_id}/interactives
~~~

## Vision

La capture vise uniquement la zone cliente de la fenêtre dont le titre contient DOFUS_WINDOW_TITLE.

Par défaut :

~~~text
VISION_FULL_DESKTOP_FALLBACK=false
~~~

Donc si la fenêtre Dofus n'est pas trouvée, aucune capture de tout le bureau n'est effectuée.

Diagnostic :

~~~text
GET /api/vision/status
~~~

OpenCV et MSS sont chargés à la demande : l'API et l'observation réseau peuvent démarrer même si la partie vision n'est pas installée.

## État et historique

~~~text
GET /api/state
GET /api/observations?limit=50
WS  /ws
~~~

Chaque champ principal contient sa valeur, sa source, sa confiance et sa date de mise à jour.

Les observations récentes sont conservées dans un buffer borné via OBSERVATION_HISTORY_SIZE.

## Identifier la build locale

Depuis backend :

~~~powershell
python tools/diagnose_client.py "C:\chemin\vers\Dofus"
~~~

Le script reste en lecture seule et cherche notamment GameAssembly.dll, global-metadata.dat, StreamingAssets/Content et les bundles mapdata_assets_world_*.bundle.

## Configuration

Voir .env.example.

~~~text
ALLOW_INPUT=false
DOFUS_WINDOW_TITLE=Dofus
VISION_ENABLED=true
VISION_FULL_DESKTOP_FALLBACK=false
NETWORK_OBSERVER_ENABLED=false
GAME_DATA_DB_PATH=../data/maps.sqlite
NETWORK_PROFILE_PATH=config/network-profile.json
NETWORK_HISTORY_SIZE=100
OBSERVATION_HISTORY_SIZE=200
~~~

## Tests

~~~bash
cd backend
pytest -q
~~~

La CI compile aussi le backend, lance les tests, typecheck le frontend puis construit Next.js.
