# Historique

## 1.1.0

- Ajoute le sélecteur de sources Streaming, HDMI, Optique, Coaxial, AUX et USB.
- Découvre les entrées et leurs paramètres dans le catalogue StreamSDK du lecteur.
- Affiche la source réelle à partir des informations du lecteur, même lorsque les
  métadonnées du morceau précédent sont encore présentes.
- Conserve le service réseau actif dans l’attribut `streaming_service`.
- Préserve un flux réseau déjà actif lors de la sélection de Streaming ; ce choix
  arrête une entrée locale mais ne relance pas une ancienne session Cast/AirPlay.
- Ajoute 7 tests de protocole et un test des services de sélection dans Home Assistant
  avec appareil simulé. Activation HDMI confirmée sur le MS.1 réel le 5 septembre.

## 1.0.0

- Remplace le prototype de diagnostic UDP/TCP par le contrôle HTTP StreamSDK
  vérifié sur un VSSL MS.1 réel.
- Ajoute volume, sourdine, pause/reprise et métadonnées dans une entité media_player.
- Ajoute la découverte mDNS, la configuration en français et en anglais,
  une identité matérielle stable et la migration des entrées 0.1.
- Respecte le volume fixe et gère les interruptions de communication.
- Ajoute des tests de protocole, un test dans Home Assistant 2026.9.1 et les
  validations GitHub Actions / HACS / Hassfest.

## 0.1.0

Prototype de diagnostic réseau, sans contrôle de lecture ni de volume.
La compatibilité matérielle n’était pas confirmée.
