# State fusion diagnostics

La fusion multi-source conserve une valeur courante par champ avec :

- source ;
- confiance ;
- timestamp ;
- priorité de source.

## Priorités par défaut

Les priorités sont définies par champ. Exemples :

- map_id : network > manual > vision > game_data > system
- player_cell : network > vision > manual > game_data > system
- popup_visible : vision > network > manual > game_data > system
- interactives : game_data > network > manual > vision > system

La carte complète est exposée par :

~~~text
GET /api/diagnostics/fusion-policy
~~~

Elle peut être remplacée via STATE_SOURCE_PRIORITY avec un objet JSON compatible avec la configuration Pydantic.

SOURCE_PRIORITY_PENALTY contrôle l'écart de confiance exigé lorsqu'une source moins prioritaire tente de remplacer une source plus prioritaire.

## Contradictions

Un conflit est journalisé uniquement lorsque deux sources différentes proposent deux valeurs différentes pour le même champ.

Chaque conflit contient :

- valeur/source/confiance actuelle ;
- valeur/source/confiance entrante ;
- décision acceptée ou rejetée ;
- raison de la décision.

Raisons possibles :

- older_observation
- lower_confidence
- lower_source_priority
- source_disagreement

Endpoint :

~~~text
GET /api/diagnostics/conflicts?limit=50
~~~

## Fraîcheur

Un champ est considéré stale lorsqu'il n'a jamais été réellement observé ou lorsque son âge dépasse STATE_STALE_AFTER_SECONDS.

~~~text
GET /api/diagnostics/health
GET /api/diagnostics/health?stale_after_seconds=30
~~~

La réponse contient :

- âge et statut de chaque champ ;
- champs stale / healthy ;
- nombre d'observations par source ;
- âge de la dernière observation par source ;
- nombre total de conflits et de conflits rejetés.

## Reset

~~~text
POST /api/diagnostics/reset
~~~

Ce reset efface uniquement les historiques d'observations et de conflits. Il ne remet pas à zéro le GameState courant.
