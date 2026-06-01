"""
Gymnasium-kompatible Fahrstuhlumgebung auf Basis der echten SimPy-Simulation.

Verwendet die originalen Model-Klassen (Etage, Fahrstuhl, Buero, Tageszeit)
aus dem SimReinforce-Projekt. Ein hier trainiertes RL-Modell kann deshalb
direkt in simulation.py via RLStrategie eingesetzt werden – ohne Transfer-
verluste durch vereinfachte Physik oder andere Spawn-Logik.

Observation (27 float32):
    [0:3]   Aktuelle Etage jedes Aufzugs        (0 – 9)
    [3:6]   Passagiere im Aufzug                (0 – 5)
    [6:16]  Wartende ↑ pro Etage                (0 – 50)
    [16:26] Wartende ↓ pro Etage                (0 – 50)
    [26]    Normierte Simulationszeit            (0 – 1)

Action:
    MultiDiscrete([10, 10, 10]) – Zieletage für Aufzug A, B, C

Reward (pro Schritt):
    + max(0, 1 − Wartezeit/MAX_PATIENCE)  je abgeliefertem Passagier
    − 2.0                                  je Passagier der Treppe nimmt
    − 0.01 × (Anzahl aktuell Wartender)   laufende Strafe
"""

from __future__ import annotations

import random
from typing import Optional

import gymnasium as gym
import numpy as np
import simpy
from gymnasium import spaces

from Model.buero import Buero
from Model.etage import Etage
from Model.farhrstuhl import Fahrstuhl
from Model.strategie import ZielEtageStrategie
from Model.tageszeit import Tageszeit


class ElevatorEnv(gym.Env):

    metadata = {"render_modes": ["human", "ansi"], "render_fps": 4}

    # ── Parameter identisch mit simulation.py ──────────────────────────
    NUM_FLOORS: int = 10
    NUM_ELEVATORS: int = 3
    MAX_CAPACITY: int = 5
    TRAVEL_TIME: int = 5       # Sekunden je Etage
    DOOR_TIME: int = 5         # halt_zeit: Sekunden für Türbewegung
    MAX_PATIENCE: int = 240    # Sekunden bis Treppenhaus
    SPAWN_ENDE: int = 36_000   # Kein Spawning mehr ab dieser Zeit
    EPISODE_DURATION: float = 40_000.0  # Puffer für Nachzügler
    STEP_DURATION: float = 5.0

    _OBS_DIM: int = NUM_ELEVATORS * 2 + NUM_FLOORS * 2 + 1  # = 27

    def __init__(self, render_mode: Optional[str] = None) -> None:
        super().__init__()
        self.render_mode = render_mode

        high = np.array(
            [float(self.NUM_FLOORS - 1)] * self.NUM_ELEVATORS
            + [float(self.MAX_CAPACITY)] * self.NUM_ELEVATORS
            + [50.0] * (self.NUM_FLOORS * 2)
            + [1.0],
            dtype=np.float32,
        )
        self.observation_space = spaces.Box(
            low=np.zeros(self._OBS_DIM, dtype=np.float32),
            high=high,
            dtype=np.float32,
        )
        self.action_space = spaces.MultiDiscrete(
            [self.NUM_FLOORS] * self.NUM_ELEVATORS
        )

        self._sim: Optional[simpy.Environment] = None
        self._etagen: list[Etage] = []
        self._aufzuege: list[Fahrstuhl] = []
        self._strategie: Optional[ZielEtageStrategie] = None
        self._office: Optional[Buero] = None
        self._abgeschlossene: list = []

    # ── Gymnasium API ──────────────────────────────────────────────────

    def reset(self, seed: Optional[int] = None, options: Optional[dict] = None):
        super().reset(seed=seed)
        if seed is not None:
            random.seed(seed)
            np.random.seed(seed)
        self._build_sim()
        self._sim.run(until=self.STEP_DURATION)
        return self._observe(), {}

    def step(self, action):
        if self._sim is None:
            raise RuntimeError("reset() muss vor step() aufgerufen werden")

        for i, tgt in enumerate(action):
            self._strategie.setze_ziel(
                chr(ord("A") + i),
                int(np.clip(tgt, 0, self.NUM_FLOORS - 1)),
            )

        n_vorher = len(self._abgeschlossene)
        self._sim.run(until=self._sim.now + self.STEP_DURATION)

        neue = self._abgeschlossene[n_vorher:]
        obs = self._observe()
        reward = float(self._compute_reward(neue))
        terminated = bool(self._office.fertig.triggered)
        truncated = bool((not terminated) and (self._sim.now >= self.EPISODE_DURATION))
        info = {
            "sim_time": float(self._sim.now),
            "waiting": int(
                sum(len(e.store_up.items) + len(e.store_down.items)
                    for e in self._etagen)
            ),
            "delivered": int(sum(1 for fg in neue if not fg.nimmt_treppenhaus)),
            "stairs": int(sum(1 for fg in neue if fg.nimmt_treppenhaus)),
        }
        return obs, reward, terminated, truncated, info

    def render(self) -> Optional[str]:
        if self.render_mode not in ("human", "ansi"):
            return None
        if self._sim is None:
            return "Umgebung nicht initialisiert."

        t = self._sim.now
        lines = [f"┌── t = {t:7.0f}s / {self.SPAWN_ENDE}s ──"]
        for a in self._aufzuege:
            lines.append(
                f"│  Aufzug {a.aufzug_id}: Etage {a.aktuelle_etage:2d}"
                f"  [{a.zustand:15s}]"
                f"  Passagiere: {len(a.im_aufzug)}/{self.MAX_CAPACITY}"
            )
        wartezeilen = [
            f"Etage {j}: ↑{len(e.store_up.items)} ↓{len(e.store_down.items)}"
            for j, e in enumerate(self._etagen)
            if e.store_up.items or e.store_down.items
        ]
        if wartezeilen:
            lines.append("│  Wartend: " + "  |  ".join(wartezeilen))
        lines.append("└" + "─" * 44)
        text = "\n".join(lines)
        if self.render_mode == "human":
            print(text)
            return None
        return text

    def close(self) -> None:
        self._sim = None

    # ── Simulation aufbauen ────────────────────────────────────────────

    def _build_sim(self) -> None:
        self._sim = simpy.Environment()
        self._etagen = [Etage(self._sim, i) for i in range(self.NUM_FLOORS)]
        self._strategie = ZielEtageStrategie()
        self._abgeschlossene = []

        self._aufzuege = [
            Fahrstuhl(
                self._sim,
                self._etagen,
                self.NUM_FLOORS,
                self.TRAVEL_TIME,
                halt_zeit=self.DOOR_TIME,
                aufzug_id=chr(ord("A") + i),
                kapazitaet=self.MAX_CAPACITY,
                schrittlogger=None,
                strategie=self._strategie,
            )
            for i in range(self.NUM_ELEVATORS)
        ]
        self._strategie.initialisiere(self._aufzuege, self._etagen)

        for a in self._aufzuege:
            self._sim.process(a.run())

        tageszeiten, default_spawn = _build_tageszeiten(self.NUM_FLOORS)
        self._office = Buero(
            self._sim,
            self._etagen,
            self._aufzuege,
            self._abgeschlossene,
            self.SPAWN_ENDE,
            self.MAX_PATIENCE,
            tageszeiten,
            default_spawn,
            schrittlogger=None,
        )
        self._sim.process(self._office.fahrgast_generator())

    # ── Reward & Beobachtung ───────────────────────────────────────────

    def _compute_reward(self, neue_fahrgaeste: list) -> float:
        reward = 0.0
        for fg in neue_fahrgaeste:
            if fg.nimmt_treppenhaus:
                reward -= 2.0
            else:
                reward += max(0.0, 1.0 - fg.wartezeit / self.MAX_PATIENCE)
        total_waiting = sum(
            len(e.store_up.items) + len(e.store_down.items)
            for e in self._etagen
        )
        reward -= 0.01 * total_waiting
        return reward

    def _observe(self) -> np.ndarray:
        obs = np.zeros(self._OBS_DIM, dtype=np.float32)
        for i, a in enumerate(self._aufzuege):
            obs[i] = float(a.aktuelle_etage)
            obs[self.NUM_ELEVATORS + i] = float(len(a.im_aufzug))
        base = self.NUM_ELEVATORS * 2
        for j, e in enumerate(self._etagen):
            obs[base + j] = float(len(e.store_up.items))
            obs[base + self.NUM_FLOORS + j] = float(len(e.store_down.items))
        obs[-1] = min(float(self._sim.now) / self.EPISODE_DURATION, 1.0)
        np.clip(obs, self.observation_space.low, self.observation_space.high, out=obs)
        return obs


# ── Tageszeiten (identisch mit simulation.py, ohne random.randint) ────

def _build_tageszeiten(num_etagen: int) -> tuple[list[Tageszeit], Tageszeit]:
    obere = list(range(1, num_etagen))
    alle = list(range(num_etagen))

    default_spawn = Tageszeit(
        start=0, ende=0,
        spawn_rate=10.0,
        beschreibung="Normalbetrieb",
        start_etagen=alle, start_gewichtung=None,
        ziel_etagen=alle,  ziel_gewichtung=None,
    )
    tageszeiten = [
        Tageszeit(
            start=0, ende=3_600,
            spawn_rate=4.5,
            beschreibung="Arbeitsbeginn",
            start_etagen=[0],    start_gewichtung=None,
            ziel_etagen=obere,   ziel_gewichtung=None,
        ),
        Tageszeit(
            start=14_400, ende=15_600,
            spawn_rate=6.0,
            beschreibung="Anfang Mittagspause",
            start_etagen=obere,  start_gewichtung=None,
            ziel_etagen=[0, 2],  ziel_gewichtung=[0.7, 0.3],
        ),
        Tageszeit(
            start=16_800, ende=18_000,
            spawn_rate=5.0,
            beschreibung="Ende Mittagspause",
            start_etagen=[0, 2], start_gewichtung=[0.7, 0.3],
            ziel_etagen=obere,   ziel_gewichtung=None,
        ),
        Tageszeit(
            start=32_400, ende=36_000,
            spawn_rate=4.0,
            beschreibung="Feierabend",
            start_etagen=obere,  start_gewichtung=None,
            ziel_etagen=[0, 5],  ziel_gewichtung=[0.95, 0.05],
        ),
    ]
    return tageszeiten, default_spawn
