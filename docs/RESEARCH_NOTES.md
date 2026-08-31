# Notes de recherche — Dofus 3

## Données statiques

Le projet public `ledouxm/dofus-sqlite` publie des données Dofus 3 extraites du client.

Son pipeline de maps génère une table :

```text
map_interactions
- mapId
- worldId
- gfxId
- cellId
- interactionId
```

Notre `GameDataRepository` valide ce schéma avant toute lecture.

Source :
https://github.com/ledouxm/dofus-sqlite

## Flux réseau

Le projet public `Miou-zora/SniffSniffSquared` documente une observation passive de Dofus 3 utilisant des frames de longueur variable et des messages Protobuf. Les messages applicatifs peuvent être encapsulés dans `google.protobuf.Any`.

Point important : les clés de messages obfusquées peuvent changer entre builds. Notre code ne lie donc pas directement une clé à `map_id` ou `player_cell`.

La correspondance est stockée dans :

```text
backend/config/network-profile.json
```

Le parser générique reste inchangé quand la build tourne.

Source :
https://github.com/Miou-zora/SniffSniffSquared

## Stratégie de calibration

1. Identifier précisément la build locale.
2. Enregistrer un court échantillon d'événements en lecture seule.
3. Faire une action contrôlée et évidente, par exemple changer une seule fois de map.
4. Comparer les messages avant/après.
5. Identifier la clé et le chemin de champ qui portent la valeur.
6. Ajouter seulement cette règle au profil.
7. Répéter pour `player_cell`, combat, tour, etc.

La vision reste une source indépendante de validation.
