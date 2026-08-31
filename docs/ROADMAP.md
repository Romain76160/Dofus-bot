# Roadmap

## Étape 0 — Socle
- [x] API FastAPI
- [x] WebSocket
- [x] État unifié
- [x] Interface Next.js
- [x] Contrôle des entrées désactivé par défaut
- [x] CI backend + frontend

## Étape 1 — Observation réseau
- [x] Outil de diagnostic de la build locale
- [x] Replay binaire + framing heuristique
- [x] Profils de build Protobuf
- [x] Ingestion d'événements JSON déjà décodés
- [x] Discovery conservateur map_id / player_cell
- [x] Journal des événements récents
- [ ] Brancher un décodeur live autorisé spécifique à la build cible
- [ ] Générer/valider automatiquement un profil après mise à jour du client

## Étape 2 — Données locales
- [x] Lecture SQLite en mode read-only
- [x] Schéma map_interactions
- [x] Résolution map -> interactifs/cellules
- [x] Enrichissement automatique après détection de map_id
- [x] Script d'installation + SHA-256
- [ ] Associer interactionId / gfxId aux noms métiers quand une table fiable est disponible

## Étape 3 — Vision
- [x] Détection de la fenêtre Dofus sous Windows
- [x] Capture limitée à la zone cliente
- [x] Pas de fallback bureau complet par défaut
- [x] Chargement paresseux MSS/OpenCV
- [ ] Détection de chargement
- [ ] Détection interface de combat
- [ ] Détection popup
- [ ] Overlay de debug

## Étape 4 — Fusion / diagnostic
- [x] Confiance par champ
- [x] Provenance par champ
- [x] Historique borné des observations
- [x] Dashboard multi-source
- [x] Reconnexion WebSocket automatique
- [x] Journal explicite des contradictions entre sources
- [x] Politique de priorité configurable par champ
- [x] Métriques de latence et fraîcheur des sources
- [x] Rejet explicite des observations anciennes / moins prioritaires
- [ ] Persistance optionnelle des diagnostics entre redémarrages

## Étape 5 — Validation
- [ ] Fixture de replay issue d'une session autorisée
- [ ] Tests end-to-end backend + dashboard
- [ ] Matrice de compatibilité par build Dofus
- [ ] Procédure de mise à jour du profil après patch
