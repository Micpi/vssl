# Historique

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
