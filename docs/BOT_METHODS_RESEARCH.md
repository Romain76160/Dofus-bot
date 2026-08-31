# Research — méthodes utilisées par des bots Dofus publics

Objectif : comprendre les grandes familles d'architecture pour choisir les briques utiles à un **serveur privé où l'automatisation est autorisée**.

Ce document ne retient pas les mécanismes de contournement, d'injection ou d'évasion anti-bot. L'intérêt est de comprendre comment les projets représentent l'état du jeu, les maps, les cellules, le combat, les actions et la robustesse.

## Projets étudiés

- Romain-P/Guinness-Bot
- louisabraham/LaBot
- Cooya/Tobby
- Azzary/NebulaR-Bot
- Garriden/Dofus3Click
- Gamerium/Dindo-Bot

## 1. Bot socket / protocole

Exemples : LaBot, Tobby.

Le moteur ne raisonne pas principalement en pixels. Il maintient des contextes internes : map courante, cellule courante, personnages/monstres, combat, interactifs, inventaire et dialogues.

LaBot sépare explicitement acquisition du flux, reader/writer, protocole et logique de comportement. Tobby montre la même idée avec des modules messages, frames, network, gamedata et des contextes roleplay/fight.

### Ce qu'on retient

~~~text
Transport / observation
        ↓
Decoder
        ↓
Semantic Events
        ↓
GameState / CombatState
        ↓
Decision Engine
~~~

Le CombatEngine ne doit jamais dépendre directement du format des paquets.

## 2. Bot event-driven

Exemples : Guinness-Bot, NebulaR-Bot.

Les messages réseau sont transformés en événements métier : MapChanged, FightStarted, PlayerMoved, TurnStarted, etc. Les scripts ou IA réagissent ensuite à ces événements.

Guinness-Bot possède un système de scripts où un changement de map devient un événement onMapChanged. NebulaR-Bot expose aussi une logique de scripting mouvement/combat et récupère les données carte/personnage/combat.

### Ce qu'on retient

Ajouter un EventBus interne :

~~~text
NetworkEvent
VisionEvent
GameDataEvent
       ↓
SemanticEventBus
       ↓
State reducers
       ↓
Bot modules
~~~

Événements cibles : MapChanged, PlayerCellChanged, FightStarted, FightEnded, FightTurnStarted, ActorMoved, ActionPointsChanged, MovementPointsChanged, PopupDetected, LoadingStarted, LoadingEnded.

## 3. Contexte séparé Roleplay / Combat

Tobby distingue les problèmes de contexte roleplay et fight. C'est pertinent pour notre architecture.

RoleplayState : map_id, player_cell, interactives, inventory, pods, dialog, current_route.

CombatState : fight_id, round, turn_actor, player_cell, action_points, movement_points, actors, occupied_cells, reachable_cells, spell_states.

### Ce qu'on retient

~~~text
GameState
├── RoleplayState
├── CombatState
└── UIState
~~~

## 4. Cellules et pathfinding

Tobby traite explicitement cellule courante, pathfinder, changements de map, chemins impossibles et cellule adjacente aux interactifs. Guinness-Bot montre aussi que le mouvement est exprimé avec des cellules plutôt qu'avec des coordonnées écran.

Le moteur doit travailler avec cell_id et un graphe de cellules. Seulement la couche Input traduit la cible en pixel.

~~~text
target cell
    ↓
GridProjection
    ↓
window-relative pixel
    ↓
InputController
~~~

Les données de map doivent fournir cellules marchables, obstacles, voisins, interactifs et transitions.

## 5. Pixel bot / vision

Exemples : Dindo-Bot, Dofus3Click.

Ces bots compensent l'absence d'état structuré par coordonnées enregistrées, capture d'une région, couleurs, comparaison avant/après, template matching, raccourcis clavier et clics souris.

Dindo-Bot ajuste les coordonnées par rapport à la taille/position de la fenêtre et utilise la différence entre captures pour vérifier qu'une action a eu un effet. Dofus3Click impose une disposition UI stable et utilise OpenCV avec des raccourcis prédéfinis.

### Ce qu'on retient

La vision sert surtout de validation secondaire : fenêtre chargée, popup, victoire/défaite, bouton fin de tour, changement visuel après clic, erreur inattendue.

## 6. Coordonnées indépendantes de la résolution

Dindo-Bot montre une bonne idée : enregistrer les coordonnées dans un référentiel connu puis les reprojeter dans la fenêtre réelle.

Nous devons faire mieux avec la géométrie de la grille :

~~~text
cell_id
    ↓
logical grid position
    ↓
normalized window coordinates
    ↓
actual client rectangle
    ↓
screen x/y
~~~

## 7. State machine plutôt que sleeps

Les anciens bots utilisent souvent des pauses fixes et attendent un changement d'écran. Tobby mentionne explicitement l'intérêt de supprimer les attentes peu propres au profit d'états.

États recommandés : WAITING_FOR_MOVE_CONFIRMATION, WAITING_FOR_FIGHT_START, MY_TURN, WAITING_FOR_CAST_CONFIRMATION, WAITING_FOR_TURN_END.

Chaque état doit avoir événement attendu, timeout, condition de succès, condition d'échec et récupération.

## 8. CombatEngine recommandé

~~~text
CombatState
    ↓
TacticalAnalyzer
    ├── distances
    ├── line of sight
    ├── reachable cells
    ├── threats
    └── spell targets
    ↓
ActionGenerator
    ↓
ActionScorer
    ↓
ActionPlan
    ↓
Executor
~~~

Exemple d'ActionPlan : move vers une cellule, cast d'un sort sur une cellule, puis end_turn.

## 9. Exécution graphique

Pour notre environnement privé autorisé, l'exécution reste graphique :

~~~text
ActionPlan
   ↓
GridProjection / UIProjection
   ↓
InputController
   ↓
mouse / keyboard
   ↓
Visual + state confirmation
~~~

## 10. Ce qu'on ne retient pas

Certains projets anciens utilisent injection dans le processus, hooks système/client, MITM actif, modification/réécriture de paquets, modification du client ou mécanismes explicitement destinés à contourner des contrôles anti-bot.

Ces techniques ne sont pas nécessaires à notre architecture privée/autorisé et ne doivent pas devenir des dépendances du projet.

## Matrice de décision

| Technique | Précision état | Robustesse UI | Dépendance build | Usage retenu |
|---|---:|---:|---:|---|
| données statiques client | élevée | excellente | moyenne | oui |
| événements réseau décodés | très élevée | excellente | élevée | oui |
| capture réseau passive | brute | excellente | moyenne | oui |
| grille/cellId | très élevée | excellente | faible après décodage | oui |
| pathfinding interne | élevée | excellente | faible | oui |
| vision/OpenCV | moyenne | moyenne | faible | oui, validation |
| coordonnées fixes | faible | faible | faible | secours uniquement |
| comparaison d'écran | moyenne | moyenne | faible | oui |
| injection/hook client | élevée | élevée | très élevée | non |
| réécriture de paquets | élevée | élevée | très élevée | non |

## Architecture cible issue de cette recherche

~~~text
                 DATA SOURCES
                      |
       +--------------+--------------+
       |              |              |
    Network        Game Data       Vision
       |              |              |
       +--------------+--------------+
                      |
                SemanticEventBus
                      |
          +-----------+-----------+
          |                       |
    RoleplayReducer           FightReducer
          |                       |
    RoleplayState             CombatState
          |                       |
          +-----------+-----------+
                      |
                 Bot Engines
          +-----------+-----------+
          |                       |
      Navigation               Combat
          |                       |
          +-----------+-----------+
                      |
                  ActionPlan
                      |
                InputController
                      |
             Visual/State Verify
~~~

## Prochaines implémentations recommandées

1. SemanticEventBus
2. CombatState
3. ActorState
4. SpellState
5. GridGeometry
6. cell_id -> logical position
7. GridProjection vers pixels fenêtre
8. TacticalAnalyzer
9. ActionPlan
10. exécuteur graphique derrière ALLOW_INPUT
11. confirmation d'action multi-source
12. machine d'état du tour de combat

## Références

- https://github.com/Romain-P/Guinness-Bot
- https://github.com/louisabraham/LaBot
- https://github.com/Cooya/Tobby
- https://github.com/Azzary/NebulaR-Bot
- https://github.com/Garriden/Dofus3Click
- https://github.com/Gamerium/Dindo-Bot