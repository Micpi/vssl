# VSSL MS.1 — session terrain

Cette procédure prépare une collecte non destructive et corrélable. Les fixtures
livrées avec l’intégration sont **synthétiques** : le support MS.1 ne sera confirmé
qu’après validation d’une capture réelle.

## 1. Préparer avant la fenêtre réseau

Synchroniser automatiquement l’heure du téléphone, du PC et de Home Assistant.
Noter le fuseau et l’heure UTC affichée par `Get-Date -AsUTC` (PowerShell) ou
`date -u` (Linux). Fermer VSSL CNCT. Identifier l’adresse IPv4 du MS.1 dans le
routeur, sans changer son nom ni sa configuration.

Créer un dossier dont le contenu brut restera local :

```powershell
Set-Location integrations\VSSL
..\..\.venv\Scripts\python.exe tools\vssl_probe.py --help
..\..\.venv\Scripts\python.exe tools\sanitize_capture.py --help
..\..\.venv\Scripts\python.exe tools\validate_fixture.py --help
```

Depuis la racine de ce composant, si Python est global :

```bash
python3 tools/vssl_probe.py --help
python3 tools/sanitize_capture.py --help
python3 tools/validate_fixture.py --help
```

## 2. Choisir l’interface et lancer le PCAP

Dans Wireshark, ouvrir **Capture > Options** et choisir l’interface dont l’adresse
IPv4 appartient au même sous-réseau que le MS.1. Observer brièvement le trafic ou
utiliser `ipconfig` (Windows), `ip -br addr` (Linux) ou les propriétés réseau pour
éviter l’interface VPN/virtuelle. Démarrer avant d’ouvrir VSSL CNCT.

Filtre de capture Wireshark/libpcap, après remplacement de l’IP :

```text
host <IP_DU_MS1> and (udp port 1800 or udp port 1900 or udp port 5353 or tcp port 80 or tcp port 443 or tcp port 7777 or tcp port 8009 or tcp port 50002 or tcp port 50006)
```

Sous Linux, lister d’abord les interfaces puis choisir explicitement `<INTERFACE>` :

```bash
ip -br addr
sudo tcpdump -i <INTERFACE> -s 0 -w captures/session-YYYYMMDD/ms1-01.pcap \
  'host <IP_DU_MS1> and (udp port 1800 or udp port 1900 or udp port 5353 or tcp port 80 or tcp port 443 or tcp port 7777 or tcp port 8009 or tcp port 50002 or tcp port 50006)'
```

Home Assistant OS ne garantit pas `tcpdump`. Si le module Terminal/SSH l’expose,
l’utiliser seulement après vérification. Sinon capturer depuis un PC du même réseau,
sur l’hôte d’un Home Assistant Container, sur un port miroir du commutateur, ou sur
le routeur. Pour Home Assistant Container, la commande s’exécute sur **l’hôte** en
choisissant son interface (`ip -br addr`, puis `sudo tcpdump -i <INTERFACE> ...`),
pas dans le conteneur sauf image/outillage explicitement préparés.

Le PCAP brut peut révéler des identifiants et reste local. Arrêter avec le bouton
Stop de Wireshark ou `Ctrl+C`, puis nommer chaque fichier `ms1-01-before-app.pcap`,
`ms1-02-actions.pcap`, etc. Partager d’abord le JSON anonymisé. Si un PCAP doit être
partagé, l’inspecter et exporter uniquement les paquets/flux pertinents dans
Wireshark (`File > Export Specified Packets`).

## 3. Première sonde

PowerShell :

```powershell
python tools\vssl_probe.py --target <IP_DU_MS1> --output-dir captures\session-YYYYMMDD
```

Linux/macOS :

```bash
python3 tools/vssl_probe.py --target <IP_DU_MS1> --output-dir captures/session-YYYYMMDD
```

Sans IP connue, omettre `--target` pour les deux recherches multicast :

```bash
python3 tools/vssl_probe.py --output-dir captures/session-YYYYMMDD
```

La sonde n’écrase jamais un dossier : elle ajoute `-001`, `-002`, etc. Elle envoie
une requête M-SEARCH distincte sur UDP 1800 et UDP 1900, puis effectue uniquement
une connexion TCP sans payload sur 80, 443, 7777, 8009, 50002 et 50006 pour les IP
dont la réponse mentionne VSSL ou celles explicitement fournies. Elle ne sonde donc
pas les autres équipements qui répondent au SSDP général. Aucun `(QRY)`, LUCI,
renommage, reset ou firmware n’est envoyé.

Codes de sortie : `0` collecte complète avec réponse, `1` collecte partielle ou sans
réponse VSSL, `2` arguments invalides, `3` échec fatal de création/écriture. Même en
code `1`, examiner les trois artefacts produits.

## 4. Manipulation chronométrée

Conserver 10 à 20 secondes entre les actions, sauf le repos de 30 secondes. Inscrire
l’heure exacte (idéalement UTC) à chaque ligne :

- [ ] `__:__:__` — 30 s de repos, application fermée.
- [ ] `__:__:__` — lancer VSSL CNCT.
- [ ] `__:__:__` — actualiser/rechercher les appareils.
- [ ] `__:__:__` — ouvrir la fiche du MS.1.
- [ ] `__:__:__` — consulter chaque écran de réglage sans modification.
- [ ] `__:__:__` — lire un flux via Google Cast.
- [ ] `__:__:__` — pause, puis reprise.
- [ ] `__:__:__` — volume `20 % → 25 % → 20 %`.
- [ ] `__:__:__` — mute, puis unmute.
- [ ] `__:__:__` — ouvrir Source Select et noter « disponible plus tard » exactement.
- [ ] `__:__:__` — ouvrir Sleep Timer et noter « disponible plus tard » exactement.
- [ ] `__:__:__` — ouvrir Alarm Clock et noter « disponible plus tard » exactement.
- [ ] `__:__:__` — arrêter le flux, puis 30 s de repos.
- [ ] `__:__:__` — télécharger les diagnostics HA et exécuter une seconde sonde.

## 5. Home Assistant pendant la session

Journalisation temporaire dans `configuration.yaml` :

```yaml
logger:
  default: info
  logs:
    custom_components.vssl: debug
```

Redémarrer/recharger la configuration de journalisation selon la version HA. Les
logs debug indiquent étape, port de destination, durée, réponses et motifs de rejet,
mais jamais les datagrammes bruts. Dans **Outils de développement > Actions**,
exécuter `homeassistant.update_entity` sur l’entité `sensor.*_discovery_status` pour
demander un refresh immédiat via le mécanisme standard. Aucun service VSSL permanent
n’est ajouté. Télécharger ensuite les diagnostics depuis l’entrée VSSL, y compris
si le premier refresh a échoué.

## 6. Transformer la capture en test

```powershell
python tools\sanitize_capture.py captures\session-YYYYMMDD\capture.raw.SENSITIVE.json captures\session-YYYYMMDD\review.sanitized.json
python tools\validate_fixture.py captures\session-YYYYMMDD\review.sanitized.json --baseline tests\fixtures\synthetic_capture.json --output captures\session-YYYYMMDD\normalized.json
Copy-Item captures\session-YYYYMMDD\review.sanitized.json tests\fixtures\real_ms1_sanitized.json
python -m pytest
git diff --no-index tests\fixtures\synthetic_capture.json tests\fixtures\real_ms1_sanitized.json
```

Équivalent Linux :

```bash
python3 tools/sanitize_capture.py captures/session-YYYYMMDD/capture.raw.SENSITIVE.json captures/session-YYYYMMDD/review.sanitized.json
python3 tools/validate_fixture.py captures/session-YYYYMMDD/review.sanitized.json --baseline tests/fixtures/synthetic_capture.json --output captures/session-YYYYMMDD/normalized.json
cp captures/session-YYYYMMDD/review.sanitized.json tests/fixtures/real_ms1_sanitized.json
python3 -m pytest
git diff --no-index tests/fixtures/synthetic_capture.json tests/fixtures/real_ms1_sanitized.json
```

Lire `baseline_comparison.new_headers` et `header_analysis.unknown_meaning` dans
`normalized.json`. Ajouter les nouveaux noms à une issue/table de recherche sans
inventer leur sens ; conserver une liste « inconnu » jusqu’à corrélation répétable
avec la checklist. Le `git diff --no-index` reste utile pour la structure complète.

Dans Home Assistant Container, copier le dossier du composant ou le monter dans un
conteneur Python 3.11+ pour les outils autonomes ; la capture PCAP reste à faire sur
l’hôte. Le plus simple reste d’exécuter la sonde sur le PC du même LAN puis de copier
uniquement `capture.sanitized.json` vers l’environnement de développement.

## Tests optionnels nécessitant accord explicite

Reset usine, mise à jour firmware, oubli du Wi-Fi et changement permanent du nom ne
font pas partie du MVP. Ne les exécuter qu’avec accord explicite du propriétaire et
une fenêtre de récupération prévue.
