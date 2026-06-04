"""
Aufzugsstrategien nach dem Strategy-Pattern.

Alle Strategien implementieren dieselbe Schnittstelle, sodass sie ohne
Änderung am Fahrstuhl ausgetauscht werden können.

Verfügbare Strategien
---------------------
ScanStrategie       – originaler SCAN-Algorithmus (Standard)
ZielEtageStrategie  – fährt zu explizit gesetzten Zieletagen
                      (Basis für eigene Regeln oder manuelles Testen)
RLStrategie         – nutzt ein SB3-Modell (PPO, A2C, …) zur Steuerung
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Optional

import numpy as np


class Strategie(ABC):
    """Abstrakte Basisklasse; implementiere naechste_richtung()."""

    @abstractmethod
    def naechste_richtung(
        self, aufzug, etagen: list, sim_now: float
    ) -> Optional[str]:
        """
        Gibt die gewünschte Fahrtrichtung zurück.

        Returns
        -------
        'up'   Aufzug soll eine Etage nach oben fahren
        'down' Aufzug soll eine Etage nach unten fahren
        None   Kein Fahrgrund – Aufzug bleibt an aktueller Etage
        """

    def blockiere_wenn_leer(self) -> bool:
        """
        True  → Aufzug wartet via warte_event auf einen neuen Fahrgast
                 (sinnvoll für SCAN: spart Rechenzeit).
        False → Aufzug yieldet nur einen kurzen Timeout und fragt die
                 Strategie danach erneut (sinnvoll für RL/Zieletage).
        """
        return True

    def hat_fahrgrund(self, aufzug) -> bool:
        """
        True → Fahre auch wenn keine Passagiere an Bord und keine
               Fahrgäste in Stores der aktuellen Richtung warten.
               Wird von ZielEtageStrategie / RLStrategie genutzt, damit
               leere Aufzüge zur Zieletage fahren.
        """
        return False

    def initialisiere(self, aufzuege: list, etagen: list) -> None:
        """Optionaler Setup-Schritt nach Aufzug-Erstellung."""


# ──────────────────────────────────────────────────────────────────────── #
#  SCAN                                                                    #
# ──────────────────────────────────────────────────────────────────────── #

class ScanStrategie(Strategie):
    """
    Klassischer SCAN-Algorithmus: fährt in einer Richtung bis keine
    Ziele mehr vorhanden sind, wählt dann die optimal nächste Richtung.

    Entspricht dem Originalverhalten aus Model/farhrstuhl.py.
    """

    def naechste_richtung(self, aufzug, etagen, sim_now) -> Optional[str]:
        return aufzug.bestimme_richtung()

    # blockiere_wenn_leer() und hat_fahrgrund() bleiben auf Default (True/False)


# ──────────────────────────────────────────────────────────────────────── #
#  Zieletage                                                               #
# ──────────────────────────────────────────────────────────────────────── #

class ZielEtageStrategie(Strategie):
    """
    Fährt jeden Aufzug zur explizit gesetzten Zieletage.

    Kann als Basis für eigene regelbasierte Strategien verwendet werden
    oder zum manuellen Testen (z.B. alle Aufzüge zu EG schicken).

    Beispiel
    --------
    strategie = ZielEtageStrategie()
    # In Simulation:
    strategie.setze_ziel("A", 5)  # Aufzug A soll zu Etage 5 fahren
    """

    def __init__(self, startetage: int = 0) -> None:
        self._ziele: dict[str, int] = {}
        self._startetage = startetage

    def initialisiere(self, aufzuege: list, etagen: list) -> None:
        for a in aufzuege:
            if a.aufzug_id not in self._ziele:
                self._ziele[a.aufzug_id] = self._startetage

    def setze_ziel(self, aufzug_id: str, etage: int) -> None:
        self._ziele[aufzug_id] = int(etage)

    def naechste_richtung(self, aufzug, etagen, sim_now) -> Optional[str]:
        ziel = self._ziele.get(aufzug.aufzug_id, aufzug.aktuelle_etage)
        if ziel > aufzug.aktuelle_etage:
            return "up"
        if ziel < aufzug.aktuelle_etage:
            return "down"
        # An Zieletage: Richtung nach wartenden Fahrgästen wählen,
        # damit der Aufzug nicht mit falscher Richtung stehen bleibt.
        cur = aufzug.aktuelle_etage
        if etagen[cur].store_up.items:
            return "up"
        if etagen[cur].store_down.items:
            return "down"
        return None

    def blockiere_wenn_leer(self) -> bool:
        return False

    def hat_fahrgrund(self, aufzug) -> bool:
        ziel = self._ziele.get(aufzug.aufzug_id, aufzug.aktuelle_etage)
        return ziel != aufzug.aktuelle_etage


# ──────────────────────────────────────────────────────────────────────── #
#  RL                                                                      #
# ──────────────────────────────────────────────────────────────────────── #

class RLStrategie(ZielEtageStrategie):
    """
    Nutzt ein SB3-kompatibles Modell zur Aufzugssteuerung.

    Das Modell wird alle `step_duration` Simulationssekunden abgefragt.
    Der Beobachtungsvektor ist identisch mit dem der ElevatorEnv (27 Werte).

    Verwendung
    ----------
    from stable_baselines3 import PPO
    from Model.strategie import RLStrategie

    model = PPO.load("elevator_ppo")
    main(strategie=RLStrategie(model))
    """

    _NUM_FLOORS: int = 10
    _NUM_ELEVATORS: int = 3
    _EPISODE_DURATION: float = 36_000.0

    def __init__(self, model, step_duration: float = 5.0) -> None:
        super().__init__()
        self.model = model
        self.step_duration = step_duration
        self._aufzuege: list = []
        self._etagen: list = []
        self._letzter_entscheid: float = -step_duration

    def initialisiere(self, aufzuege: list, etagen: list) -> None:
        super().initialisiere(aufzuege, etagen)
        self._aufzuege = list(aufzuege)
        self._etagen = list(etagen)

    def naechste_richtung(self, aufzug, etagen, sim_now) -> Optional[str]:
        if sim_now - self._letzter_entscheid >= self.step_duration:
            self._aktualisiere_ziele(sim_now)
        return super().naechste_richtung(aufzug, etagen, sim_now)

    # ------------------------------------------------------------------ #

    def _aktualisiere_ziele(self, sim_now: float) -> None:
        obs = self._beobachtung(sim_now)
        aktionen, _ = self.model.predict(obs, deterministic=True)
        for aufzug, akt in zip(self._aufzuege, aktionen):
            if akt == 1:
                ziel = min(aufzug.aktuelle_etage + 1, self._NUM_FLOORS - 1)
            elif akt == 2:
                ziel = max(aufzug.aktuelle_etage - 1, 0)
            else:
                ziel = aufzug.aktuelle_etage
            self._ziele[aufzug.aufzug_id] = ziel
        self._letzter_entscheid = sim_now

    def _beobachtung(self, sim_now: float) -> np.ndarray:
        """Baut denselben 27-dim Beobachtungsvektor wie ElevatorEnv._observe()."""
        obs = np.zeros(27, dtype=np.float32)
        for i, a in enumerate(self._aufzuege):
            obs[i] = float(a.aktuelle_etage)
            obs[self._NUM_ELEVATORS + i] = float(len(a.im_aufzug))
        base = self._NUM_ELEVATORS * 2
        for j, etage in enumerate(self._etagen):
            obs[base + j] = float(len(etage.store_up.items))
            obs[base + self._NUM_FLOORS + j] = float(len(etage.store_down.items))
        obs[-1] = min(float(sim_now) / self._EPISODE_DURATION, 1.0)
        np.clip(obs[:self._NUM_ELEVATORS * 2 + self._NUM_FLOORS * 2], 0.0, 50.0,
                out=obs[:self._NUM_ELEVATORS * 2 + self._NUM_FLOORS * 2])
        return obs
