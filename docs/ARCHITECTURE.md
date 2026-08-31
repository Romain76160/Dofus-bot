# Architecture

## Règle principale

Le moteur n'interprète jamais directement des pixels ou des paquets. Chaque source produit une observation structurée. Le `StateStore` fusionne ensuite ces observations dans un `GameState`.

## Sources

### Network observer
Adaptateur en **lecture seule**. Il doit convertir les événements autorisés du client en observations génériques, sans logique métier.

### Game data
Accès aux données statiques : maps, cellules, interactifs, métadonnées.

### Vision
Capture de la fenêtre et détection OpenCV : état de chargement, combat, popups et validation d'éléments.

## État unifié

Chaque champ peut conserver :

- sa valeur ;
- sa source ;
- un score de confiance ;
- l'heure de dernière mise à jour.

## Exécution

Les futurs modules navigation/récolte/combat consomment uniquement le `GameState`.

Le contrôleur souris/clavier est séparé et verrouillé par `ALLOW_INPUT=false` par défaut.
