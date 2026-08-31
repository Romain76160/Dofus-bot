# Capture TCP live — Windows

## Objectif

tools/live_capture.py crée un pont entre une connexion TCP autorisée vers le serveur privé et le décodeur réseau du backend.

Le processus de capture est séparé de FastAPI afin que seul le petit processus WinDivert ait besoin des droits administrateur.

~~~text
Client Dofus
    |
    | TCP
    v
WinDivert SNIFF
    |
    | payloads seulement
    v
tools/live_capture.py
    |
    | batches JSON locaux
    v
POST /api/network/replay-batch
    |
    v
NetworkStreamDecoder -> StateStore -> Dashboard
~~~

## Prérequis

- Windows 11 64-bit ;
- Python 3.12 64-bit recommandé ;
- serveur privé où la capture est autorisée ;
- backend déjà démarré sur 127.0.0.1:8000 ;
- terminal administrateur uniquement pour live_capture.py.

Installer :

~~~powershell
cd backend
.venv\Scripts\activate
pip install -r requirements-live-windows.txt
~~~

## Vérifier le filtre

Avec adresse et port :

~~~powershell
python tools/live_capture.py --server-host 127.0.0.1 --server-port 5555 --dry-run
~~~

Le dry-run ne charge pas WinDivert et ne demande pas les droits administrateur.

Sans adresse :

~~~powershell
python tools/live_capture.py --server-port 5555 --dry-run
~~~

Le filtre par port seul est moins restrictif.

## Démarrer

Dans un PowerShell administrateur :

~~~powershell
cd C:\chemin\Dofus-bot\backend
.venv\Scripts\activate
python tools/live_capture.py --server-host 127.0.0.1 --server-port 5555
~~~

Sortie attendue :

~~~text
[config] server host: 127.0.0.1
[config] resolved IPv4: 127.0.0.1
[config] server port: 5555
[config] backend: http://127.0.0.1:8000
[live] session ...
[live] backend reachable; starting passive capture
[capture] SNIFF filter: ...
~~~

## Dashboard

La carte "Capture TCP live" affiche :

- état ACTIVE/INACTIVE ;
- cible serveur ;
- âge du heartbeat ;
- paquets vus ;
- paquets contenant un payload ;
- chunks effectivement envoyés ;
- volume transmis ;
- retransmissions exactes ignorées ;
- drops de file ;
- erreurs de forwarding ;
- filtre WinDivert réellement utilisé.

Status API :

~~~text
GET /api/network/live-capture/status
~~~

Un heartbeat absent depuis LIVE_CAPTURE_HEARTBEAT_TTL_SECONDS rend la session INACTIVE.

## Batching

Par défaut :

- file : 4096 chunks ;
- batch : 48 chunks max ;
- flush : 35 ms ;
- heartbeat : 2 s ;
- fenêtre de déduplication : 1500 ms.

Exemple de réglage manuel sur une seule ligne :

~~~powershell
python tools/live_capture.py --server-host 127.0.0.1 --server-port 5555 --queue-size 8192 --batch-size 64 --flush-ms 25
~~~

Le backend limite une requête à 500 chunks et 8 MiB.

## Mode SNIFF

Le captureur ouvre WinDivert avec Flag.SNIFF.

Cela signifie que le pont est conçu pour observer les paquets correspondants sans les retirer du chemin réseau. Le script n'appelle aucune fonction de modification du payload et n'utilise pas le captureur pour bloquer du trafic.

## Retransmissions

Chaque segment est identifié avec :

- direction ;
- IP/ports source et destination ;
- numéro de séquence TCP lorsque disponible ;
- longueur ;
- empreinte courte du payload.

Une répétition exacte dans la fenêtre de déduplication est ignorée.

## Limitation TCP actuelle

v0.7 ne réordonne pas encore explicitement les segments TCP hors ordre.

Si le décodeur :

- perd fréquemment son framing ;
- ne produit plus de packets après un burst ;
- fonctionne en replay mais mal en live ;

alors la priorité suivante est un reassembleur TCP par flux/numéro de séquence.

## Chiffrement

Cette couche récupère le payload visible au niveau TCP.

Si la build/serveur chiffre son protocole applicatif, le captureur ne le contourne pas. Dans ce cas, il faut utiliser une source décodée autorisée côté serveur/client ou instrumenter le serveur privé directement.

## Arrêt

Ctrl+C arrête le captureur. Si le processus est tué brutalement, le dashboard passe automatiquement INACTIVE après expiration du heartbeat.
