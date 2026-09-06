# VSSL MX pour Home Assistant

Contrôle local du **VSSL MS.1** dans Home Assistant, installable avec HACS.
Cette version remplace l’ancienne intégration expérimentale de diagnostic.

[![Ouvrir le dépôt dans HACS](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=Micpi&repository=vssl&category=integration)

## Fonctions

- Volume de 0 à 100 %, pas de 1 % et sourdine.
- Sélecteur de sources : **Streaming, HDMI, Optique, Coaxial, AUX et USB**,
  selon les entrées exposées par l’appareil.
- Pause et reprise du flux actif lorsque la source les autorise.
- État de lecture, titre, artiste, album, pochette et source.
- Détection automatique AirPlay/mDNS ou ajout par adresse IP.
- Retour d’état toutes les 5 secondes et après chaque commande.
- Respect du mode de volume fixe réglé dans l’application VSSL.
- Identifiant matériel stable, reconnexion et migration de la version 0.1.

L’intégration utilise l’API HTTP StreamSDK du lecteur, sur le port 80.
Aucun agent VSSL, cloud ou compte supplémentaire n’est nécessaire.

## Installation HACS

Home Assistant **2026.9 ou plus récent** est requis ; les tests ont été exécutés
avec Home Assistant **2026.9.1**.

1. Ouvrir **HACS → ⋮ → Dépôts personnalisés**.
2. Ajouter `https://github.com/Micpi/vssl`, catégorie **Intégration**.
3. Télécharger **VSSL MX** puis redémarrer Home Assistant.
4. Dans **Paramètres → Appareils et services**, configurer le VSSL découvert,
   ou **Ajouter une intégration → VSSL MX** et saisir son adresse IP.

Si ce dépôt est déjà installé via HACS, télécharger la mise à jour puis redémarrer.
L’adresse configurée dans la version expérimentale 0.1 est conservée et vérifiée.
Les anciennes entités de diagnostic ne sont plus fournies ; leurs entrées
indisponibles peuvent être supprimées du registre des entités.

Ce dépôt est disponible comme **dépôt personnalisé HACS**. Il n’est pas encore
référencé dans le catalogue HACS par défaut.

### Installation manuelle

Copier le dossier `custom_components/vssl` dans le dossier `custom_components`
de votre configuration Home Assistant, puis redémarrer. En remplaçant la 0.1,
remplacer le dossier complet pour éliminer ses anciens modules de diagnostic.

## Compatibilité et limites

| Appareil | Validation |
| --- | --- |
| MS.1, firmware `0.0.136.0x114a983` | Testé sur appareil réel |
| MA.1 | Reconnu par le code, pas encore testé sur matériel |
| A.1 / A.3 / A.6, série X, série SX | Non pris en charge |

Pour démarrer une musique ou une radio, utiliser Music Assistant, Google Cast,
AirPlay ou l’application VSSL. Cette version pilote le flux déjà actif ; elle
n’expose pas `play_media`, le groupement, l’égaliseur,
l’allumage/extinction ou le saut de piste.

La commande StreamSDK `pause` est une bascule. L’intégration relit l’état avant
de l’envoyer pour qu’une seconde demande de pause ne relance pas la lecture.
Une demande de reprise à l’arrêt renvoie une erreur explicite plutôt que de
tenter de lancer un contenu inconnu.

### Sélection de source (depuis la version 1.1)

Le menu **Source** de l’entité et l’action `media_player.select_source` permettent
de choisir les entrées locales. Leur liste et les paramètres d’activation sont lus
sur le MS.1, plutôt que reconstruits à partir d’un autre modèle.

**Streaming** arrête l’entrée locale pour permettre une nouvelle diffusion réseau.
Ce choix ne relance pas la session Cast/AirPlay interrompue : démarrer ou relancer
la musique depuis Music Assistant ou l’application émettrice. Si un flux réseau
est déjà actif, sélectionner Streaming le laisse jouer.

Cast, AirPlay et Spotify ne sont pas des entrées locales activables individuellement.
Le nom du service actif reste accessible dans l’attribut `streaming_service`.
Bluetooth peut être affiché lorsqu’il est actif, mais sa sélection et l’appairage
restent à effectuer dans l’application VSSL.

```yaml
action: media_player.select_source
target:
  entity_id: media_player.piece_a_vivre
data:
  source: HDMI
```

Réserver l’adresse IP dans le routeur est conseillé. L’accès HTTP local au VSSL
doit être possible depuis Home Assistant. La découverte mDNS nécessite sa
diffusion entre les réseaux ; l’ajout manuel fonctionne sans cette découverte.

## Exemple d’automatisation

Adapter l’identifiant de l’entité créé chez vous :

```yaml
actions:
  - action: media_player.volume_set
    target:
      entity_id: media_player.piece_a_vivre
    data:
      volume_level: 0.25
```

## Tests

Le [rapport de validation](VALIDATION.md) détaille les vérifications réelles et
leurs limites. Les tests automatisés du protocole n’accèdent pas au réseau local :

```shell
python -m pip install aiohttp
python -m unittest discover -s tests -v
```

`tools/ha_smoke.py` teste le chargement et la migration dans un conteneur Home
Assistant avec un appareil réel ; l’option `--write` teste aussi volume/sourdine
et restaure leurs valeurs initiales. Ne pas l’exécuter dans l’instance de production.

Intégration communautaire indépendante, non affiliée à VSSL. L’icône fournie est
un dessin original de haut-parleur et non le logo de la marque.
