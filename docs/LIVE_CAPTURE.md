# Capture TCP live — Windows

## Objectif

v0.8 rend le pont de capture **auto-configurable** pour un serveur privé autorisé.

L'utilisateur n'a plus besoin de connaître l'IP ou le port lorsque la connexion de jeu peut être identifiée de façon non ambiguë à partir du processus Dofus.

~~~text
Dofus.exe
  |
  | psutil
  v
connexions TCP ESTABLISHED
  |
  | classement conservateur
  v
endpoint distant
  |
  v
WinDivert SNIFF
  |
  | payloads seulement
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
- backend démarré sur 127.0.0.1:8000 ;
- PowerShell/Terminal administrateur pour la phase WinDivert.

Installer :

~~~powershell
cd backend
.venv\Scripts\activate
pip install -r requirements-live-windows.txt
~~~

Cette dépendance optionnelle contient :

- PyDivert / WinDivert pour la capture ;
- psutil pour repérer les connexions du processus.

## Lancement automatique

Commande normale :

~~~powershell
python tools/live_capture.py
~~~

Le script cherche par défaut :

~~~text
Dofus.exe
Dofus
~~~

Il attend jusqu'à 60 secondes une connexion TCP établie.

On peut donc :

1. démarrer le backend ;
2. ouvrir un PowerShell administrateur ;
3. lancer live_capture.py ;
4. ouvrir/connecter Dofus au serveur privé autorisé.

## Comment une cible est choisie

Chaque connexion distante ESTABLISHED du processus correspondant devient un candidat.

Le classement favorise :

- une connexion réellement ESTABLISHED ;
- un port non web ;
- une IP loopback ou privée, typique d'un environnement local/privé.

Aucun nom de serveur public ni aucune IP de fournisseur n'est codé en dur.

Si un candidat domine clairement, il est sélectionné automatiquement.

Si deux candidats sont trop proches, **le script s'arrête plutôt que de capturer la mauvaise connexion**.

## Connexions ambiguës

Lister :

~~~powershell
python tools/live_capture.py --list-endpoints
~~~

Exemple :

~~~text
[discovery] candidate endpoints:
  [0] 192.168.1.20:5555 pid=1234 process=Dofus.exe status=ESTABLISHED
  [1] 192.168.1.21:6666 pid=1234 process=Dofus.exe status=ESTABLISHED
~~~

Choisir :

~~~powershell
python tools/live_capture.py --candidate-index 0
~~~

## Nom de processus différent

Un client privé peut renommer l'exécutable :

~~~powershell
python tools/live_capture.py --process-name MonDofus.exe
~~~

Plusieurs alias :

~~~powershell
python tools/live_capture.py --process-name MonDofus.exe --process-name DofusClient.exe
~~~

## Attente de connexion

Par défaut :

~~~text
--discover-timeout 60
--discover-poll 1
~~~

Attente indéfinie :

~~~powershell
python tools/live_capture.py --discover-timeout 0
~~~

Échec immédiat si aucune connexion n'existe :

~~~powershell
python tools/live_capture.py --discover-timeout 0.1
~~~

## Mode manuel

Le mode manuel reste disponible et prend la priorité sur l'auto-détection :

~~~powershell
python tools/live_capture.py --server-host 192.168.1.20 --server-port 5555
~~~

Port seul :

~~~powershell
python tools/live_capture.py --server-port 5555
~~~

## Dry-run

Auto-détection sans ouvrir WinDivert :

~~~powershell
python tools/live_capture.py --dry-run
~~~

Le dry-run affiche notamment :

~~~text
[config] target source: process-auto
[config] process: Dofus.exe (pid 1234)
[config] server host: 192.168.1.20
[config] server port: 5555
[config] filter: ...
~~~

## Dashboard

La carte Capture TCP live affiche :

- état ACTIVE/INACTIVE ;
- endpoint détecté ;
- heartbeat ;
- paquets/payloads ;
- chunks transmis ;
- octets transmis ;
- retransmissions ignorées ;
- drops de file ;
- erreurs ;
- filtre WinDivert.

## Sécurité du pont

Le captureur utilise WinDivert Flag.SNIFF.

Il ne contient pas de logique pour :

- modifier les paquets ;
- injecter des paquets ;
- bloquer du trafic ;
- contourner un chiffrement applicatif ;
- masquer l'automatisation ou contourner un anti-cheat.

## Limitation protocole

Détecter automatiquement l'endpoint ne signifie pas que tous les serveurs utilisent exactement les mêmes messages.

La chaîne se découpe volontairement en deux parties :

~~~text
auto endpoint + capture TCP        générique
framing / profil / messages        dépendants de la build
~~~

C'est ce découplage qui permet d'adapter ensuite une build privée sans réécrire le captureur.

## Limitation TCP actuelle

v0.8 ne réordonne pas encore explicitement les segments TCP hors ordre.

Si les métriques montrent que la capture est saine mais que le framing décroche, l'étape suivante est un reassembleur TCP par flux et numéro de séquence.

## Arrêt

Ctrl+C arrête le processus. Le dashboard passe automatiquement INACTIVE lorsque le heartbeat expire.
