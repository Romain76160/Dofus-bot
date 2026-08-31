# Dofus Hybrid Observer

Architecture expérimentale d'observation d'un client Dofus sur un **serveur privé où l'automatisation et l'observation réseau sont autorisées**.

Le projet combine plusieurs sources en lecture seule :

- **auto-détection TCP** : repérage des connexions établies du processus Dofus ;
- **capture TCP live** : pont Windows/WinDivert en mode SNIFF ;
- **réseau brut** : framing heuristique + profil de build Protobuf ;
- **réseau déjà décodé** : ingestion JSON et discovery sémantique ;
- **données locales** : maps.sqlite pour les interactifs statiques ;
- **vision** : capture limitée à la zone cliente de la fenêtre Dofus.

Les actions clavier/souris restent séparées et désactivées par défaut.

## Démarrage rapide

### 1. Backend

~~~powershell
cd backend
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
~~~

### 2. Frontend

~~~bash
cd frontend
npm install
npm run dev
~~~

Dashboard :

~~~text
http://localhost:3000
~~~

### 3. Capture live Windows — mode automatique

Installer les dépendances Windows optionnelles :

~~~powershell
cd backend
.venv\Scripts\activate
pip install -r requirements-live-windows.txt
~~~

Pour un serveur privé autorisé, le mode normal ne demande plus l'IP ni le port :

~~~powershell
python tools/live_capture.py
~~~

Le captureur :

1. cherche Dofus.exe / Dofus ;
2. récupère ses connexions TCP établies ;
3. classe les endpoints distants sans coder en dur un serveur ;
4. choisit automatiquement uniquement si un candidat est clairement meilleur ;
5. construit le filtre WinDivert ;
6. envoie les payloads au backend local.

Le processus attend par défaut jusqu'à 60 secondes qu'une connexion Dofus apparaisse. Lancer Dofus et se connecter au serveur privé suffit donc dans le cas non ambigu.

Le terminal doit être lancé **en administrateur** pour la capture WinDivert.

## Si plusieurs connexions sont possibles

Afficher les candidats :

~~~powershell
python tools/live_capture.py --list-endpoints
~~~

Puis sélectionner explicitement :

~~~powershell
python tools/live_capture.py --candidate-index 0
~~~

L'outil préfère automatiquement les endpoints de réseau local/privé et les ports non web, mais il refuse de choisir au hasard si plusieurs connexions ont un score proche.

## Configuration manuelle de secours

Le mode précédent reste disponible :

~~~powershell
python tools/live_capture.py --server-host 192.168.1.20 --server-port 5555
~~~

Ou port seul :

~~~powershell
python tools/live_capture.py --server-port 5555
~~~

## Tester sans capturer

Avec auto-détection :

~~~powershell
python tools/live_capture.py --dry-run
~~~

Avec cible explicite :

~~~powershell
python tools/live_capture.py --server-host 127.0.0.1 --server-port 5555 --dry-run
~~~

## Flux

~~~text
Dofus.exe
   |
   +--> psutil : endpoints TCP établis
                     |
                     v
               cible sélectionnée
                     |
                     v
WinDivert SNIFF -> TCP payloads -> /api/network/replay-batch ─┐
Décodeur externe JSON -> /api/network/ingest ────────────────┤
maps.sqlite ──────────────────────────────────────────────────┼-> GameState -> WS -> Dashboard
Fenêtre Dofus / vision ───────────────────────────────────────┘
~~~

Lorsqu'un map_id sûr est accepté, le backend charge automatiquement les interactifs correspondants depuis maps.sqlite.

## Réseau

Endpoints principaux :

~~~text
POST /api/network/replay-hex
POST /api/network/replay-batch
POST /api/network/ingest
POST /api/network/ingest-batch
GET  /api/network/debug
GET  /api/network/events
GET  /api/network/live-capture/status
POST /api/network/live-capture/heartbeat
~~~

Le batch brut conserve l'ordre de capture et alimente les framers stateful.

## Limites actuelles

Le captureur :

- observe les paquets en mode SNIFF ;
- ne modifie pas les payloads ;
- ne bloque pas les paquets ;
- ne contourne pas un éventuel chiffrement applicatif ;
- filtre les retransmissions TCP exactes sur une courte fenêtre ;
- groupe les chunks avant envoi HTTP ;
- ne réordonne pas encore explicitement les segments TCP hors ordre.

L'auto-détection sélectionne des connexions du **processus local Dofus**, pas un serveur codé en dur. Cela rend le pont portable entre différents serveurs privés autorisés, mais ne garantit pas que leur protocole applicatif soit identique.

## maps.sqlite

Le backend reconnaît :

~~~text
map_interactions(mapId, worldId, gfxId, cellId, interactionId)
~~~

Installation :

~~~bash
cd backend
python tools/setup_maps_sqlite.py
~~~

## Vision

La capture vise uniquement la zone cliente de la fenêtre dont le titre contient DOFUS_WINDOW_TITLE.

~~~text
VISION_FULL_DESKTOP_FALLBACK=false
~~~

## Diagnostics

~~~text
GET /api/state
GET /api/observations?limit=50
GET /api/diagnostics/health
GET /api/diagnostics/conflicts
GET /api/diagnostics/fusion-policy
GET /api/vision/status
WS  /ws
~~~

## Identifier la build locale

~~~powershell
cd backend
python tools/diagnose_client.py "C:\chemin\vers\Dofus"
~~~

## Tests

~~~bash
cd backend
pytest -q
~~~

La CI compile le backend et les outils, lance les tests, typecheck le frontend puis construit Next.js.

Documentation détaillée : docs/LIVE_CAPTURE.md.
