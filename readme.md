# label-sea

[![CI](https://img.shields.io/github/actions/workflow/status/hoelkj/label-sea/ci.yml?branch=main&label=CI)](https://github.com/hoelkj/label-sea/actions/workflows/ci.yml)
[![Tests](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/hoelkj/label-sea/badges/tests.json)](https://github.com/hoelkj/label-sea/actions/workflows/ci.yml)
[![Quality](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/hoelkj/label-sea/badges/quality.json)](https://github.com/hoelkj/label-sea/actions/workflows/ci.yml)
[![Coverage](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/hoelkj/label-sea/badges/coverage.json)](https://github.com/hoelkj/label-sea/actions/workflows/ci.yml)
[![Image Size](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/hoelkj/label-sea/badges/image-size.json)](https://github.com/hoelkj/label-sea/actions/workflows/ci.yml)
[![SBOM](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/hoelkj/label-sea/badges/sbom.json)](https://github.com/hoelkj/label-sea/actions/workflows/ci.yml)
[![Critical CVEs](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/hoelkj/label-sea/badges/critical-cves.json)](https://github.com/hoelkj/label-sea/actions/workflows/ci.yml)
[![High CVEs](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/hoelkj/label-sea/badges/high-cves.json)](https://github.com/hoelkj/label-sea/actions/workflows/ci.yml)
[![License](https://img.shields.io/badge/license-MIT-lightgrey)](LICENSE)

- cli tool zum erzeugen von label
- label sind für anschlusspläne von Erzeugern / Verbrauchern / Verteilern für elktrische Notversorgungen
- diese sollen dem betreiner von (Not) Stromerzeugungsanlangen (SEA) und Netzersatzanlagen (NEA) dabei helfen einen Übersicht der verwendeten Komponenten, deren Verkabelung und über die Last / den Verbrauch zu haben. Im Fehlerfall soll eine strukturierte Fehlersuche und -eingrenzung unterstützt werden.
- Der Plan soll auf einem Whiteboard an der SEA/NEA aufgezeichnet werden. Dabei werden Kabelverbindungen gezeichnet und vorhanden Komponenenten als vorgeferitgte Elemente angebracht. Diese Label werden dazu gedruckt und laminiert in Magnetband (c Profil 40mm oder 50mm) geschoben.
- der Fokus liegt auf Ein und Ausgängen (Schüko oder CEE 16 bis 125A), den Leistungsparametern der Erzeuger und Verbraucher
- Die Labels sind in der höhe ans magnetband gebunden. die breite variiert anhand der anzahl der Input und outputs.
- Die Anschlüsse der Komponenten sind unten und oben (bei erzeugern nur unten und bei verbrauchern nur oben) jeweils mit einem strich der richtung rand geht. kurz vor dem rand mündet der strich in einen Halbkreis der die offene Steckerbuchse symbolisiert. an dem Stricht steht der Typ des Anschlusses inkl. ampere in vertikaler schriftrichtung 

## Features

- Verarbeitung von yaml Dateien (template hier im Repo)
- Ausgabe in svg label je komponente und option für ein optimiertes Druck PDF in A4 oder A3
- Bedienung über cli
- Drei Komponenten Typen (Erzeuger, Verbraucher, Verteiler)

## Verwendete Technologien

Die folgenden Technologien werden in diesem Projekt eingesetzt:

- Python
- uv
- GitHub Actions (Test, Build und manueller WF zum Erzeugen von Labeln)
- Docker verfügbar

## Installation

- `uv sync`
- `uv run label-sea build --input examples/template.yaml --band-height 50 --pdf a4`

## Verwendung

```bash
uv run label-sea build --input examples/template.yaml --band-height 50 --pdf a4
uv run label-sea validate --input examples/template.yaml
```

## CLI-Argumente
 - input: komponenten yaml im gültigen format
 - output-dir: zielverzeichnis für svg und optional pdf
 - optionen: pdf erstellen in a4 oder a3, höhe des magnetbands (40 oder 50mm)

## YAML-Format

- root enthält `title`, optional `connectors` und `components`
- `connectors` definiert zentrale anschlusstypen, die in komponenten per `ref` wiederverwendet werden koennen
- jede komponente hat mindestens `name`, `type` und je nach typ `inputs` oder `outputs`
- gültige typen sind `erzeuger`, `verbraucher`, `verteiler` sowie die englischen varianten
- anschlüsse bestehen aus `ref` plus optional `count`; inline `kind` und `ampere` werden weiter unterstützt
- `count` erweitert einen eintrag auf mehrere gleiche anschlüsse, ohne dass du ihn mehrfach auflisten musst
- `CEE` ist auf normnahe werte `16`, `32`, `63`, `125` begrenzt; `Schuko` ist fest `16A`
- das formale schema liegt in `schema/components.schema.json`

Beispiel:

```yaml
title: Beispiel Aufbau
connectors:
	cee125:
		kind: CEE
		ampere: 125
components:
	- key: sea-125
		name: SEA 125
		type: erzeuger
		power:
			apparent_kva: 125
			active_kw: 100
		outputs:
			- ref: cee125
```


## Entwicklung

Hinweise fuer lokale Entwicklung:

- `uv sync --dev`
- `uv run ruff check .`
- `uv run pytest --cov=label_sea --cov-report=term-missing`
- `docker build -t label-sea .`
- `docker run --rm label-sea validate --input examples/template.yaml`
- GitHub Actions prüft Ruff und Pytest automatisch und erzeugt zusätzlich SBOM und CVE-Scan für das Container-Image
- Für manuelles Rendern gibt es den Workflow `Render labels`; dort wird ein YAML-Pfad aus dem Repo übergeben und das Ergebnis als Artefakt mit 2 Tagen Retention abgelegt
- Die Ausgabe bevorzugt Lubalin, falls die Schrift installiert ist; wenn nicht, wird automatisch eine kompatible Systemschrift verwendet.

## Lizenz

MIT. Die Lizenzdatei liegt als `LICENSE` im Repo.

