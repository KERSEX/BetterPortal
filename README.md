# BetterPortal

Komfortable Skylanders-Verwaltung für den emulierten Portal von **RPCS3** – besonders für die
nervigen Swap-Force-Swapper.

## Start

Doppelklick auf `start.bat` (oder `python main.py`). Der Browser öffnet sich automatisch auf
`http://127.0.0.1:5177`. Benötigt nur Python + Flask (wird beim ersten Start installiert).

## Was es kann

- **🔮 Portal** – 8 Slots wie in RPCS3. Die Dateien landen nummeriert (`01 - …`, `02 - …`) im
  Ordner `Portal/`. In RPCS3 einfach **Werkzeuge → Skylanders Portal → Load** und diesen einen
  Ordner wählen – nie wieder suchen.
- **🔄 Swapper-Studio** – Oberteil + Unterteil anklicken, fertig. BetterPortal erzeugt beide
  Hälften und legt sie in zwei freie Slots. Das Unterteil bestimmt die Swap-Zone (wird angezeigt).
- **📚 Bibliothek** – alle erstellten Figuren, nach Spiel sortiert. Portal-Slots sind **Hardlinks**
  auf die Bibliothek: Level/Geld/Hüte, die das Spiel auf die Figur schreibt, bleiben erhalten,
  auch wenn du den Slot leerst.
- **🗂️ Alle Figuren** – die komplette Datenbank aus dem RPCS3-Quellcode (472 Einträge: Figuren,
  Fallen, Fahrzeuge, Items), filterbar nach Spiel/Element/Kategorie. Ein Klick erstellt die Figur.
- **💾 Loadouts** – Portal-Belegungen benennen und speichern (z. B. „Trap Team Story"),
  später mit einem Klick wiederherstellen.
- **⚡ Hot-Swap** – Loadouts oder Einzelfiguren auf **Strg+Shift+F1…F9** legen. Die Hotkeys
  funktionieren **global**, auch während RPCS3 im Vordergrund läuft (hoher Doppelton = OK,
  tiefer Ton = Fehler). Ablauf im Spiel: belegte Slots in RPCS3 per **Clear** freigeben →
  Hotkey → **Load** (der Ordner ist noch offen). In RPCS3 geladene, gesperrte Slots werden
  übersprungen (einzelner mittlerer Ton). Der Modifier ist in `hotswap.json` änderbar
  (`"modifier": "ctrl+shift"`).

- **🎮 Direkt in RPCS3 (Auto-Inject)** – Schalter oben rechts. Wenn aktiv, steuert BetterPortal
  RPCS3s Skylanders-Manager per UI-Automation fern: Jede Auswahl (Figur, Swapper-Kombi, Loadout,
  Hotkey) landet **sofort im laufenden Spiel**, ohne einen Klick in RPCS3. „▶ Jetzt senden"
  gleicht RPCS3 manuell mit dem aktuellen Portal ab. Voraussetzung: RPCS3 läuft (grüner Punkt).

## Wichtig zu wissen

- Solange eine Figur in RPCS3 geladen ist, ist die Datei gesperrt – erst dort „Clear" drücken
  oder das Spiel schließen, dann kann BetterPortal den Slot ändern.
- `.sky`-Dateien werden byte-identisch zu RPCS3s eigenem „Create"-Dialog erzeugt
  (Quelle: `rpcs3/rpcs3qt/skylander_dialog.cpp`).
- Eigene Dumps (`.sky`, `.bin`, `.dmp`, `.dump`) kannst du einfach in den Ordner `Bibliothek/`
  kopieren – sie werden erkannt.
