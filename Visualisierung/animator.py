import pygame
import csv
import copy

# ── Farben ────────────────────────────────────────────────────────────────────
HG             = (28,  30,  45)
PANEL_BG       = (40,  42,  62)
ETAGE_GERADE   = (42,  44,  64)
ETAGE_UNGERADE = (48,  50,  72)
ETAGE_LINIE    = (65,  68,  95)
SCHACHT_BG     = (52,  55,  78)
GRAU_DUNKEL    = (55,  58,  82)
WEISS          = (240, 240, 248)
GRAU_HELL      = (180, 182, 205)
GRAU           = (110, 112, 138)
ROT_HELL       = (215,  75,  75)
ROT_DUNKEL     = (140,  45,  45)

ZUSTAND_FARBE = {
    "WARTEN":         (85,  90, 130),
    "EINLADEN":       (225, 180,  40),
    "AUSLADEN":     (225, 125,  40),
    "FAHREND_HOCH":   (55, 180,  85),
    "FAHREND_RUNTER": (55, 115, 215),
}

EREIGNIS_FARBE = {
    "FAHRGAST_SPAWN":        (140, 215, 140),
    "EINGESTIEGEN":          (225, 180,  40),
    "ANGEKOMMEN":            (55, 180,  85),
    "TREPPENHAUS":           (215,  75,  75),
    "AUFZUG_FAHREND_HOCH":   (55, 180,  85),
    "AUFZUG_FAHREND_RUNTER": (55, 115, 215),
    "AUFZUG_WARTEND":        (85,  90, 130),
}

ID_FARBE = {
    "A": (100, 180, 255),
    "B": (255, 155,  75),
    "C": (175, 115, 255),
    "D": (75, 215, 175),
}

GESCHWINDIGKEITEN = [1, 5, 10, 30, 60, 120]


class Animator:
    BREITE = 1100
    HOEHE  = 820

    def __init__(self, csv_pfad, tageszeiten=None):
        self._schritte    = self._lade_und_baue(csv_pfad)
        self._tageszeiten = tageszeiten or []
        self._index       = 0
        self._play        = False
        self._speed_i     = 2
        self._acc         = 0.0

        pygame.init()
        self._screen = pygame.display.set_mode((self.BREITE, self.HOEHE))
        pygame.display.set_caption("SimReinforce – Schritt-Visualisierung v2")
        self._clock  = pygame.time.Clock()
        self._font_s      = pygame.font.SysFont("Consolas", 13)
        self._font_s_bold = pygame.font.SysFont("Consolas", 13, bold=True)
        self._font_m      = pygame.font.SysFont("Consolas", 16)
        self._font_l      = pygame.font.SysFont("Consolas", 20, bold=True)

        TITEL_H  = 38
        HEADER_H = 22   # Zeile für Aufzug-IDs über den Etagen
        CTRL_H   = 55
        PANEL_W  = 395
        self._bau_x  = 10
        self._bau_y  = TITEL_H
        self._bau_w  = self.BREITE - PANEL_W - 20
        self._bau_h  = self.HOEHE - TITEL_H - HEADER_H - CTRL_H - 5
        self._pan_x  = self.BREITE - PANEL_W - 5
        self._pan_y  = TITEL_H
        self._pan_w  = PANEL_W
        self._pan_h  = self.HOEHE - TITEL_H - CTRL_H - 5
        self._ctrl_y = self.HOEHE - CTRL_H

    # ── CSV laden & Zustände aufbauen ─────────────────────────────────────────

    def _lade_und_baue(self, pfad):
        with open(pfad, newline="", encoding="utf-8") as f:
            zeilen = list(csv.DictReader(f))

        aufzug_ids, etagen_set = set(), set()
        for z in zeilen:
            if z["aufzug_id"]:
                aufzug_ids.add(z["aufzug_id"])
            for feld in ("aufzug_etage", "fahrgast_etage", "fahrgast_ziel"):
                if z[feld]:
                    etagen_set.add(int(z[feld]))

        self._aufzug_ids = sorted(aufzug_ids)
        self._num_etagen = max(etagen_set) + 1 if etagen_set else 10

        aufzuege = {
            aid: {"etage": 0, "zustand": "WARTEND", "fahrgaeste": 0, "pax_ziele": []}
            for aid in self._aufzug_ids
        }
        floor_w      = {e: {"up": 0, "down": 0} for e in range(self._num_etagen)}
        floor_treppe = {e: 0 for e in range(self._num_etagen)}
        treppe_gesamt = 0

        schritte = []
        for z in zeilen:
            t        = float(z["t"])
            ereignis = z["ereignis"]
            aid      = z["aufzug_id"]
            fid      = int(z["fahrgast_id"])    if z["fahrgast_id"]    else None
            f_etage  = int(z["fahrgast_etage"]) if z["fahrgast_etage"] else None
            f_ziel   = int(z["fahrgast_ziel"])  if z["fahrgast_ziel"]  else None

            if aid and z["aufzug_etage"]:
                aufzuege[aid].update({
                    "etage":      int(z["aufzug_etage"]),
                    "zustand":    z["aufzug_zustand"],
                    "fahrgaeste": int(z["aufzug_fahrgaeste"]),
                })

            if f_etage is not None and f_ziel is not None:
                richtung = "up" if f_ziel > f_etage else "down"
                if ereignis == "FAHRGAST_SPAWN":
                    floor_w[f_etage][richtung] += 1
                elif ereignis == "EINGESTIEGEN":
                    floor_w[f_etage][richtung] = max(0, floor_w[f_etage][richtung] - 1)
                    if aid:
                        aufzuege[aid]["pax_ziele"].append(f_ziel)
                elif ereignis == "ANGEKOMMEN":
                    if aid and f_ziel in aufzuege[aid]["pax_ziele"]:
                        aufzuege[aid]["pax_ziele"].remove(f_ziel)
                elif ereignis == "TREPPENHAUS":
                    floor_w[f_etage][richtung] = max(0, floor_w[f_etage][richtung] - 1)
                    floor_treppe[f_etage] += 1
                    treppe_gesamt += 1

            schritte.append({
                "t":             t,
                "ereignis":      ereignis,
                "aid":           aid,
                "fid":           fid,
                "f_etage":       f_etage,
                "f_ziel":        f_ziel,
                "aufzuege":      copy.deepcopy(aufzuege),
                "floor_w":       copy.deepcopy(floor_w),
                "floor_treppe":  copy.deepcopy(floor_treppe),
                "treppe_gesamt": treppe_gesamt,
                "w_hoch":        int(z["wartend_hoch"])   if z["wartend_hoch"]   else 0,
                "w_runter":      int(z["wartend_runter"]) if z["wartend_runter"] else 0,
            })

        return schritte

    # ── Hauptschleife ─────────────────────────────────────────────────────────

    def run(self):
        while True:
            dt = self._clock.tick(60) / 1000.0

            for ev in pygame.event.get():
                if ev.type == pygame.QUIT:
                    pygame.quit()
                    return
                if ev.type == pygame.KEYDOWN:
                    self._taste(ev.key)
                if ev.type == pygame.MOUSEBUTTONDOWN and ev.button == 1:
                    self._klick(ev.pos)

            if self._play and self._schritte:
                self._acc += dt
                spd = GESCHWINDIGKEITEN[self._speed_i]
                while self._acc >= 1.0 / spd:
                    self._acc -= 1.0 / spd
                    if self._index < len(self._schritte) - 1:
                        self._index += 1
                    else:
                        self._play = False
                        break

            self._zeichne()
            pygame.display.flip()

    def _taste(self, key):
        if key == pygame.K_SPACE:
            self._play = not self._play
            self._acc  = 0.0
        elif key == pygame.K_RIGHT:
            self._index = min(self._index + 1, len(self._schritte) - 1)
        elif key == pygame.K_LEFT:
            self._index = max(self._index - 1, 0)
        elif key == pygame.K_UP:
            self._speed_i = min(self._speed_i + 1, len(GESCHWINDIGKEITEN) - 1)
        elif key == pygame.K_DOWN:
            self._speed_i = max(self._speed_i - 1, 0)
        elif key == pygame.K_HOME:
            self._index = 0
        elif key == pygame.K_END:
            self._index = len(self._schritte) - 1

    def _klick(self, pos):
        mx, my = pos
        bar_y = self._ctrl_y + 10
        if bar_y - 4 <= my <= bar_y + 18 and 10 <= mx <= self.BREITE - 10:
            ratio = (mx - 10) / (self.BREITE - 20)
            self._index = max(0, min(int(ratio * (len(self._schritte) - 1)),
                                     len(self._schritte) - 1))

    # ── Zeichnen ──────────────────────────────────────────────────────────────

    def _zeichne(self):
        self._screen.fill(HG)
        s = self._schritte[self._index] if self._schritte else None
        self._zeichne_titel(s)
        if s:
            self._zeichne_gebaeude(s)
            self._zeichne_panel(s)
        self._zeichne_steuerleiste(s)

    def _zeichne_titel(self, s):
        self._txt("Fahrstuhlsimulation Visualisierung v2", 12, 8, self._font_l, WEISS)
        if s:
            self._txt(
                f"Schritt {self._index + 1} / {len(self._schritte)}",
                self.BREITE - 260, 10, self._font_m, GRAU,
            )

    def _zeichne_gebaeude(self, s):
        bx, by = self._bau_x, self._bau_y
        bw, bh = self._bau_w, self._bau_h
        n       = self._num_etagen
        aids    = self._aufzug_ids

        LABEL_W   = 42
        WARTE_W   = 68
        schacht_w = max(75, (bw - LABEL_W - WARTE_W) // len(aids))
        etage_h   = bh // n

        # Aufzug-Header mit Richtungsdreiecken
        for i, aid in enumerate(aids):
            hx = bx + LABEL_W + i * schacht_w + 8
            self._txt(f"[{aid}]", hx, by + 2, self._font_m, ID_FARBE.get(aid, GRAU_HELL))

            zustand = s["aufzuege"].get(aid, {}).get("zustand", "")
            tri_y   = by + 11
            tri_s   = 6
            up_x    = bx + LABEL_W + i * schacht_w + schacht_w - 22
            dn_x    = up_x + 15

            # Aufwärts-Dreieck
            up_pts = [(up_x, tri_y - tri_s), (up_x - tri_s, tri_y + tri_s), (up_x + tri_s, tri_y + tri_s)]
            if zustand == "FAHREND_HOCH":
                pygame.draw.polygon(self._screen, (255, 215, 0), up_pts)
                pygame.draw.polygon(self._screen, (30, 25, 0), up_pts, 1)
            else:
                pygame.draw.polygon(self._screen, GRAU, up_pts, 1)

            # Abwärts-Dreieck
            dn_pts = [(dn_x, tri_y + tri_s), (dn_x - tri_s, tri_y - tri_s), (dn_x + tri_s, tri_y - tri_s)]
            if zustand == "FAHREND_RUNTER":
                pygame.draw.polygon(self._screen, (255, 215, 0), dn_pts)
                pygame.draw.polygon(self._screen, (30, 25, 0), dn_pts, 1)
            else:
                pygame.draw.polygon(self._screen, GRAU, dn_pts, 1)

        y0 = by + 22

        # aktuelles Treppenhaus-Ereignis merken für Hervorhebung
        treppe_etage = s["f_etage"] if s["ereignis"] == "TREPPENHAUS" else None

        for e in range(n - 1, -1, -1):
            ry = y0 + (n - 1 - e) * etage_h

            # Hintergrund — rot aufleuchten wenn gerade Treppenhaus auf dieser Etage
            if e == treppe_etage:
                bg = (70, 30, 30)
            else:
                bg = ETAGE_GERADE if e % 2 == 0 else ETAGE_UNGERADE
            pygame.draw.rect(self._screen, bg, (bx, ry, bw, etage_h))
            pygame.draw.line(self._screen, ETAGE_LINIE, (bx, ry), (bx + bw, ry))

            # Etagen-Label
            self._txt(f"E{e:2d}", bx + 4, ry + etage_h // 2 - 8, self._font_m, GRAU_HELL)

            # Schächte
            for i, aid in enumerate(aids):
                sx = bx + LABEL_W + i * schacht_w
                pygame.draw.rect(self._screen, SCHACHT_BG,
                                 (sx + 2, ry + 1, schacht_w - 4, etage_h - 2))

                az = s["aufzuege"].get(aid, {})
                if az.get("etage") == e:
                    zst    = az.get("zustand", "WARTEND")
                    zfarbe = ZUSTAND_FARBE.get(zst, GRAU)
                    ifarbe = ID_FARBE.get(aid, GRAU_HELL)
                    rect   = (sx + 4, ry + 3, schacht_w - 8, etage_h - 6)
                    pygame.draw.rect(self._screen, zfarbe, rect, border_radius=5)
                    pygame.draw.rect(self._screen, ifarbe, rect, width=2, border_radius=5)
                    pax_ziele = az.get("pax_ziele", [])
                    self._txt(f"[{aid}]", sx + 8, ry + 7, self._font_s, WEISS)
                    if pax_ziele:
                        ziele_str = ",".join(str(z) for z in sorted(pax_ziele))
                        self._txt(f"→{ziele_str}", sx + 8, ry + etage_h // 2 + 2,
                                  self._font_s, WEISS)

            # Wartende + Treppenhaus pro Etage
            fw  = s["floor_w"].get(e, {"up": 0, "down": 0})
            ft  = s["floor_treppe"].get(e, 0)
            wx  = bx + LABEL_W + len(aids) * schacht_w + 5

            if fw["up"] > 0:
                self._txt(f"▲{fw['up']}", wx, ry + 3, self._font_s, (100, 225, 100))
            if fw["down"] > 0:
                self._txt(f"▼{fw['down']}", wx, ry + etage_h // 2 + 1,
                          self._font_s, (100, 145, 255))

            # Treppenhaus-Zähler, gleiche Formatierung wie Wartezahlen
            if ft > 0:
                treppe_farbe = ROT_HELL if e == treppe_etage else ROT_DUNKEL
                self._txt(f"T:{ft}", wx, ry + etage_h - 17,
                          self._font_s, treppe_farbe)

        # Rahmen
        pygame.draw.rect(self._screen, ETAGE_LINIE,
                         (bx, y0, bw, n * etage_h), width=1)

    def _get_tageszeit_name(self, t):
        for tz in self._tageszeiten:
            if tz.start <= t < tz.ende:
                return tz.beschreibung
        return "Normalbetrieb"

    def _zeichne_panel(self, s):
        px, py = self._pan_x, self._pan_y
        pw     = self._pan_w

        pygame.draw.rect(self._screen, PANEL_BG,
                         (px, py, pw, self._pan_h), border_radius=8)

        cy = py + 14

        # ── Tageszeit ──
        if self._tageszeiten:
            self._txt("Tageszeit", px + 12, cy, self._font_s, GRAU)
            cy += 18
            tz_name = self._get_tageszeit_name(s["t"])
            self._txt(tz_name, px + 12, cy, self._font_l, WEISS)
            cy += 26
            self._txt(self._uhrzeit(s["t"]), px + 12, cy, self._font_m, GRAU_HELL)
            cy += 24
            self._linie(px, cy, pw)
            cy += 10

        # ── Ereignis ──
        ereignis = s["ereignis"]
        efarbe   = EREIGNIS_FARBE.get(ereignis, WEISS)
        self._txt("Ereignis", px + 12, cy, self._font_s, GRAU)
        cy += 18
        self._txt(ereignis, px + 12, cy, self._font_l, efarbe)
        cy += 28

        if s["fid"] is not None:
            self._txt(f"F{s['fid']:03d}: E{s['f_etage']} → E{s['f_ziel']}",
                      px + 12, cy, self._font_m, GRAU_HELL)
            cy += 22
        if s["aid"]:
            self._txt(f"Aufzug {s['aid']}", px + 12, cy, self._font_m,
                      ID_FARBE.get(s["aid"], GRAU_HELL))
            cy += 22
        cy += 6

        self._linie(px, cy, pw)
        cy += 10

        # ── Aufzüge ──
        self._txt("Aufzüge", px + 12, cy, self._font_s, GRAU)
        cy += 18
        for aid in self._aufzug_ids:
            az     = s["aufzuege"].get(aid, {})
            zst    = az.get("zustand", "?")
            etg    = az.get("etage", 0)
            pax    = az.get("fahrgaeste", 0)
            zfarbe = ZUSTAND_FARBE.get(zst, GRAU)
            ifarbe = ID_FARBE.get(aid, GRAU_HELL)
            pygame.draw.rect(self._screen, zfarbe,
                             (px + 12, cy + 2, 8, 15), border_radius=2)
            self._txt(f"[{aid}] E{etg:2d}  {pax} Pax", px + 24, cy, self._font_m, ifarbe)
            cy += 20
            self._txt(f"      {zst}", px + 24, cy, self._font_s, zfarbe)
            cy += 22
        cy += 6

        self._linie(px, cy, pw)
        cy += 10

        # ── Wartend + Treppenhaus gesamt ──
        self._txt("Wartend gesamt", px + 12, cy, self._font_s, GRAU)
        cy += 18
        self._txt(f"▲ Hoch:   {s['w_hoch']:3d}", px + 12, cy, self._font_m, (100, 225, 100))
        cy += 22
        self._txt(f"▼ Runter: {s['w_runter']:3d}", px + 12, cy, self._font_m, (100, 145, 255))
        cy += 22

        # Treppenhaus-Counter
        tg = s["treppe_gesamt"]
        self._txt(f"Treppenhaus: {tg:3d}", px + 12, cy, self._font_m, ROT_HELL)
        cy += 26

        self._linie(px, cy, pw)
        cy += 10

        # ── Steuerung ──
        self._txt("Steuerung", px + 12, cy, self._font_s, GRAU)
        cy += 18
        for taste, beschr in [
            ("SPACE",  "Play / Pause"),
            ("← →",    "Schritt vor/zurück"),
            ("↑ ↓",    "Geschwindigkeit"),
            ("Pos1",   "Anfang"),
            ("Ende",   "Letzter Schritt"),
            ("Klick",  "Zeitleiste springen"),
        ]:
            self._txt(f"{taste:<8}{beschr}", px + 12, cy, self._font_s, GRAU_HELL)
            cy += 17

    def _zeichne_steuerleiste(self, s):
        y  = self._ctrl_y
        bw = self.BREITE

        pygame.draw.rect(self._screen, PANEL_BG, (0, y, bw, self.HOEHE - y))
        pygame.draw.line(self._screen, ETAGE_LINIE, (0, y), (bw, y))

        bar_x, bar_y = 10, y + 10
        bar_w, bar_h = bw - 20, 10
        pygame.draw.rect(self._screen, GRAU_DUNKEL,
                         (bar_x, bar_y, bar_w, bar_h), border_radius=5)
        if s and self._schritte:
            ratio  = self._index / max(1, len(self._schritte) - 1)
            filled = int(bar_w * ratio)
            if filled > 0:
                pygame.draw.rect(self._screen, (80, 155, 220),
                                 (bar_x, bar_y, filled, bar_h), border_radius=5)
            cx = bar_x + filled
            pygame.draw.line(self._screen, WEISS, (cx, bar_y - 3), (cx, bar_y + bar_h + 3))

        spd    = GESCHWINDIGKEITEN[self._speed_i]
        status = "▶ PLAY" if self._play else "⏸ PAUSE"
        self._txt(f"{status}   {spd} Schritte/s", 12, y + 28, self._font_m, GRAU_HELL)

        if s and self._schritte:
            t_end = self._schritte[-1]["t"]
            self._txt(f"{self._uhrzeit(s['t'])} / {self._uhrzeit(t_end)}",
                      bw - 270, y + 28, self._font_m, GRAU)

    # ── Hilfsmethoden ─────────────────────────────────────────────────────────

    @staticmethod
    def _uhrzeit(sekunden, start_stunde=8):
        gesamt_sek = int(start_stunde * 3600 + sekunden)
        h = (gesamt_sek // 3600) % 24
        m = (gesamt_sek % 3600) // 60
        s = gesamt_sek % 60
        return f"{h:02d}:{m:02d}:{s:02d}"

    def _txt(self, text, x, y, font, farbe):
        self._screen.blit(font.render(str(text), True, farbe), (x, y))

    def _linie(self, px, y, pw):
        pygame.draw.line(self._screen, ETAGE_LINIE,
                         (px + 8, y), (px + pw - 8, y))
