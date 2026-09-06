# Validation

## Version 1.1.0 — 6 septembre 2026

- Le 5 septembre, le catalogue du MS.1 réel a exposé AUX, SPDIF/optique, coaxial,
  HDMI et USB avec leurs paramètres de lecture StreamSDK.
- Activation HDMI réelle réussie : réponse acceptée puis état `playing` avec
  `serviceID: HDMI`. Aucun signal audio HDMI n’a été évalué ; le test confirme le
  routage et le retour d’état du lecteur.
- La tentative de restauration d’une ancienne session Cast par ses métadonnées
  n’a pas repris la musique. Cette stratégie n’est pas utilisée dans l’intégration.
- 17 tests automatisés du protocole passent, dont sélection, refus des sources
  absentes, non-interruption d’un flux réseau, et métadonnées de piste obsolètes.
- Dans Home Assistant 2026.9.1 avec un serveur simulant les réponses du MS.1 :
  vérification de la liste de six sources et des six appels `select_source`.
- À la reprise le 6 septembre, le PC était sur un autre réseau : les commandes
  Optique, Coaxial, AUX, USB et retour Streaming n’ont pas été retestées sur le
  matériel. Elles suivent le même format de catalogue, ou la commande `stop`
  pour libérer l’entrée. Le comportement audio de ces entrées reste à confirmer.

## Version 1.0.0

Vérifications réalisées le 5 septembre 2026.

## Matériel réel

- Modèle retourné par l’appareil : VSSL MS1.
- Firmware : `0.0.136.0x114a983` (StreamSDK).
- Source active pendant les tests : Google Cast / Music Assistant.
- API locale HTTP : identification, réseau, volume, sourdine et état du lecteur.
- Volume : passage de 41 à 40 puis retour à 41, valeurs relues sur le lecteur.
- Sourdine : activation confirmée puis rétablissement de l’état non muet.
- Pause/reprise corrigée : `playing → paused → playing`, avec lecture de l’état
  après chaque commande. StreamSDK utilise `pause` comme bascule ; envoyer
  `play` directement est incorrect sur ce firmware.

## Home Assistant réel en conteneur isolé

Image : `ghcr.io/home-assistant/home-assistant:2026.9.1`, Python 3.14.
Le conteneur communiquait directement avec le MS.1 du réseau local.

- Chargement de l’intégration et du formulaire de configuration.
- Création d’une entrée et d’une entité `media_player` disponible.
- Affichage de l’état de lecture, du volume et des métadonnées du flux actif.
- Appels `media_player.volume_set` et `media_player.volume_mute` via Home
  Assistant : changement confirmé et rétablissement des valeurs initiales.
- Deuxième ajout du même appareil : refus du doublon.
- Indisponibilité HTTP simulée côté client : entité indisponible, puis retour
  à l’état disponible après rétablissement de l’adresse du client.
- Déchargement / rechargement de l’intégration.
- Migration d’une entrée au format expérimental v1 : conservation de l’hôte,
  conversion vers une identité matérielle stable et chargement réussi en v2.

## Tests automatisés

10 tests de protocole passent sur serveur HTTP local simulé : volume/sourdine,
pause/reprise idempotente et sérialisée, refus de reprise à l’arrêt, volume fixe,
erreurs HTTP et JSON, données invalides, modèle incompatible et validation des
paramètres. La CI exécute ces tests et compile les modules ; elle comprend aussi
les contrôles HACS et Hassfest.

## Périmètre non validé

Le MA.1, les autres firmwares, la lecture AirPlay, le comportement pendant une
coupure électrique réelle et l’installation dans l’instance Home Assistant de
production n’ont pas été testés. La découverte mDNS de l’appareil a été observée
sur le réseau Windows ; l’ajout Home Assistant a été testé avec l’adresse IP.

Les anciennes séries A/X et SX ne sont pas couvertes par cette intégration.
