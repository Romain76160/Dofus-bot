# Network ingest

Le backend accepte des événements réseau **déjà décodés** afin de ne pas coupler le reste du projet à une build Dofus particulière.

## Format minimal

~~~json
{
  "payload": {
    "mapId": 191105026
  }
}
~~~

## Format complet

~~~json
{
  "message_type": "map_update",
  "direction": "server_to_client",
  "wire_key": "optional-key",
  "captured_at": "2026-08-31T20:00:00+02:00",
  "payload": {
    "mapId": 191105026,
    "character": {
      "cellId": 287
    }
  }
}
~~~

## Discovery

Le mapper recherche des alias sémantiques connus sans dépendre d'un nom obfusqué précis.

Auto-application :

- mapId, currentMapId, map_id -> map_id
- playerCell, character.cellId, etc. -> player_cell

Debug uniquement :

- actors[...].cellId
- un cellId dont le propriétaire n'est pas identifiable

Les cellules manifestement hors plage sont ignorées.

## Batch

POST /api/network/ingest-batch accepte au maximum 500 événements par requête.

## JSONL

tools/forward_jsonl.py regroupe par défaut 25 lignes par requête :

~~~bash
python tools/forward_jsonl.py capture.jsonl --batch-size 50
~~~

Les lignes qui contiennent seulement un objet payload sont automatiquement enveloppées.

## Important

Cette couche ne capture pas elle-même le trafic. Elle constitue une frontière stable entre :

1. un décodeur externe adapté à la build ;
2. le moteur sémantique du projet.

Le replay brut /api/network/replay-hex reste disponible en parallèle.
