# Dofus Hybrid Observer

Architecture expérimentale d'observation d'un client Dofus sur un **serveur privé où l'automatisation et l'observation réseau sont autorisées**.

Le projet combine plusieurs sources en lecture seule :

- **capture TCP live** : pont Windows/WinDivert en mode SNIFF ;
- **réseau brut** : framing heuristique + profil de build Protobuf ;
- **réseau déjà décodé** : ingestion JSON et discovery sémantique ;
- **données locales** : maps.sqlite pour les interactifs statiques ;
- **vision** : capture limitée à la zone cliente de la fenêtre Dofus.

Les actions clavier/souris restent séparées et désactivées par défaut.

## Stack

- Backend : Python 3.12, FastAPI, WebSocket
- Capture live : PyDivert/WinDivert optionnel sous Windows
- Réseau : framing heuristique + Protobuf wire parser + profils de build
- Données : SQLite en mode lecture seule
- Vision : MSS + OpenCV chargés à la demande
- Frontend : Next.js + TypeScript
- État : GameState multi-source avec confiance, priorités, conflits et fraîcheur

## Flux

~~~text
WinDivert SNIFF -> TCP payloads -> /api/network/replay-batch ─┐
Décodeur externe JSON -> /api/network/ingest ────────────────┤
maps.sqlite ──────────────────────────────────────────────────┼-> GameState -> WS -> Dashboard
Fenêtre Dofus / vision ───────────────────────────────────────┘
~~~

Lorsqu'un map_id sûr est accepté, le backend charge automatiquement les interactifs correspondants depuis maps.sqlite.

## Démarrage

### Backend

Dans un terminal normal :

~~~powershell
cd backend
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
~~~

API :

~~~text
http://127.0.0.1:8000/docs
~~~

### Frontend

~~~bash
cd frontend
npm install
npm run dev
~~~

Dashboard :

~~~text
http://localhost:3000
~~~

### Capture TCP live sous Windows

Installer la dépendance optionnelle :

~~~powershell
cd backend
.venv\Scripts\activate
pip install -r requirements-live-windows.txt
~~~

Tester le filtre sans capturer :

~~~powershell
python tools/live_capture.py --server-host 127.0.0.1 --server-port 5555 --dry-run
~~~

Puis ouvrir **PowerShell/Terminal en administrateur** et lancer :

~~~powershell
python tools/live_capture.py --server-host 127.0.0.1 --server-port 5555
~~~

Remplacer l'hôte et le port par ceux du serveur privé.

Si l'adresse du serveur n'est pas connue mais que son port est suffisamment spécifique :

~~~powershell
python tools/live_capture.py --server-port 5555
~~~

Le mode adresse + port est préférable car le filtre est plus étroit.

Le backend doit être lancé avant le captureur. Le captureur envoie un heartbeat et refuse de démarrer si l'API locale n'est pas joignable.

Documentation détaillée : docs/LIVE_CAPTURE.md.

## Réseau

### Capture/replay brut

Endpoints :

~~~text
POST /api/network/replay-hex
POST /api/network/replay-batch
GET  /api/network/live-capture/status
POST /api/network/live-capture/heartbeat
~~~

Le batch conserve l'ordre de capture et alimente les mêmes framers stateful que le replay unitaire.

### Événements JSON déjà décodés

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

Le discovery est volontairement conservateur : un cellId générique de monstre/PNJ est affiché comme candidat de debug mais n'est pas automatiquement appliqué à player_cell.

Pour une source JSONL déjà décodée :

~~~bash
cd backend
python tools/forward_jsonl.py capture.jsonl
~~~

## Limites du pont live v0.7

Le captureur :

- observe les paquets en mode SNIFF ;
- ne modifie pas les payloads ;
- ne bloque pas les paquets ;
- ne contourne pas un éventuel chiffrement applicatif ;
- filtre les retransmissions TCP exactes sur une courte fenêtre ;
- groupe les chunks avant envoi HTTP pour préserver les performances.

Le framing actuel reçoit les segments dans l'ordre observé par WinDivert. Si la session réelle montre des problèmes liés à des segments TCP hors ordre, l'étape suivante sera d'ajouter un reassembleur par numéro de séquence.

## maps.sqlite

Le backend reconnaît :

~~~text
map_interactions(mapId, worldId, gfxId, cellId, interactionId)
~~~

La base est ouverte avec SQLite mode=ro.

~~~bash
cd backend
python tools/setup_maps_sqlite.py
~~~

Endpoints :

~~~text
GET /api/game-data/status
GET /api/game-data/maps/{map_id}/interactions
GET /api/game-data/maps/{map_id}/interactives
~~~

## Vision

La capture vise uniquement la zone cliente de la fenêtre dont le titre contient DOFUS_WINDOW_TITLE.

~~~text
VISION_FULL_DESKTOP_FALLBACK=false
~~~

Diagnostic :

~~~text
GET /api/vision/status
~~~

## État et diagnostics

~~~text
GET /api/state
GET /api/observations?limit=50
GET /api/diagnostics/health
GET /api/diagnostics/conflicts
GET /api/diagnostics/fusion-policy
WS  /ws
~~~

Chaque champ principal contient sa valeur, sa source, sa confiance et sa date de mise à jour.

## Identifier la build locale

~~~powershell
cd backend
python tools/diagnose_client.py "C:\chemin\vers\Dofus"
~~~

Le script reste en lecture seule et cherche notamment GameAssembly.dll, global-metadata.dat, StreamingAssets/Content et les bundles mapdata_assets_world_*.bundle.

## Configuration

Voir .env.example.

Variables principales :

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
CONFLICT_HISTORY_SIZE=100
LIVE_CAPTURE_HEARTBEAT_TTL_SECONDS=7
STATE_STALE_AFTER_SECONDS=15
SOURCE_PRIORITY_PENALTY=0.15
~~~

## Tests

~~~bash
cd backend
pytest -q
~~~

La CI compile le backend et les outils, lance les tests, typecheck le frontend puis construit Next.js.
