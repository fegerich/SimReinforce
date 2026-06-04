"""
Beispieltraining eines PPO-Agenten für die Fahrstuhlsimulation.

Ablauf
------
1. Trainingsumgebungen erstellen (echte SimPy-Simulation)
2. PPO-Modell konfigurieren und trainieren
3. Bestes Modell speichern
4. Schnellvergleich: RL-Agent vs. Zufallsstrategie in der Gym-Umgebung
5. Hinweis für vollständigen SCAN-Vergleich in simulation.py

Ausführen
---------
    conda run -n sim_reinforce_fg python train.py

TensorBoard (während oder nach dem Training)
--------------------------------------------
    tensorboard --logdir Output/rl_training/tb_logs
"""

import os
import sys
import time

# Verhindert OpenMP-Konflikt zwischen Intel-MKL (Conda) und PyTorch auf Windows.
# Muss vor dem ersten numpy/torch-Import gesetzt werden.
os.environ.setdefault("KMP_DUPLICATE_LIB_OK", "TRUE")

# SB3/torch muss vor numpy importiert werden, damit PyTorch-DLLs zuerst geladen
# werden – andernfalls lädt Intel-MKL (über numpy) libiomp5md.dll und blockiert
# anschließend das Laden von torch/lib/shm.dll (WinError 127, Windows/Conda).
import torch as th
from stable_baselines3 import PPO
from stable_baselines3.common.callbacks import CheckpointCallback, EvalCallback
from stable_baselines3.common.env_util import make_vec_env
from stable_baselines3.common.monitor import Monitor

import numpy as np

sys.path.insert(0, os.path.dirname(__file__))
import Env  # noqa: F401 – registriert "ElevatorEnv-v0" bei Gymnasium

import gymnasium

# Konfiguration 
OUTPUT_DIR      = os.path.join("Output", "rl_training")
N_ENVS          = 4          # Parallele Trainingsumgebungen
TOTAL_TIMESTEPS = 2_000_000    # Demo-Wert, für richtiges Training höher
SEED            = 42

os.makedirs(OUTPUT_DIR, exist_ok=True)
os.makedirs("Output", exist_ok=True)

# 1. Umgebungen 
print("Erstelle Umgebungen …")
train_env = make_vec_env("ElevatorEnv-v0", n_envs=N_ENVS, seed=SEED)
eval_env  = Monitor(gymnasium.make("ElevatorEnv-v0"))

# 2. Modell 
model = PPO(
    "MlpPolicy",
    train_env,
    verbose=1,
    seed=SEED,
    policy_kwargs=dict(net_arch=[64, 128, 64], activation_fn=th.nn.ReLU),
    # Hyperparameter
    learning_rate=3e-4,
    n_steps=2048,      # Schritte je Update-Zyklus pro Env
    batch_size=256,
    n_epochs=10,
    gamma=0.995,       # Hoher Discount-Faktor: Episoden sind ~8 000 Schritte lang
    gae_lambda=0.95,
    ent_coef=0.01,     # Entropie-Bonus hält Exploration aufrecht
    clip_range=0.2,
    tensorboard_log=os.path.join(OUTPUT_DIR, "tb_logs"),
)

# 3. Callbacks 
eval_callback = EvalCallback(
    eval_env,
    best_model_save_path=OUTPUT_DIR,          # speichert als best_model.zip
    log_path=os.path.join(OUTPUT_DIR, "eval"),
    eval_freq=max(50_000 // N_ENVS, 1),       # alle ~50k Gesamtschritte
    n_eval_episodes=2,
    deterministic=True,
    verbose=1,
)

checkpoint_callback = CheckpointCallback(
    save_freq=max(100_000 // N_ENVS, 1),
    save_path=os.path.join(OUTPUT_DIR, "checkpoints"),
    name_prefix="elevator_ppo",
    verbose=0,
)

# 4. Training 
print(f"\nStarte Training: {TOTAL_TIMESTEPS:,} Schritte | {N_ENVS} parallele Envs")
print(f"TensorBoard:  tensorboard --logdir {OUTPUT_DIR}/tb_logs\n")

t0 = time.time()
model.learn(
    total_timesteps=TOTAL_TIMESTEPS,
    callback=[eval_callback, checkpoint_callback],
)
dauer_min = (time.time() - t0) / 60

final_path = os.path.join(OUTPUT_DIR, "elevator_ppo_final")
model.save(final_path)
print(f"\nModell gespeichert: {final_path}.zip")
print(f"Training dauerte:   {dauer_min:.1f} Minuten")


#5. Schnellvergleich 

def _episode(env, policy=None) -> dict:
    """Führt eine vollständige Episode durch; policy=None → Zufallsaktionen."""
    obs, _ = env.reset()
    total_reward = 0.0
    delivered = stairs = 0
    wartezeit_summe = 0.0
    wartezeit_anz   = 0
    steps = 0
    while True:
        if policy is None:
            action = env.action_space.sample()
        else:
            action, _ = policy.predict(obs, deterministic=True)
        obs, reward, terminated, truncated, info = env.step(action)
        total_reward    += reward
        delivered       += info["delivered"]
        stairs          += info["stairs"]
        wartezeit_summe += info["wartezeit_summe"]
        wartezeit_anz   += info["wartezeit_anz"]
        steps           += 1
        if terminated or truncated:
            break
    avg_wartezeit = wartezeit_summe / wartezeit_anz if wartezeit_anz > 0 else 0.0
    return {"reward": total_reward, "delivered": delivered,
            "stairs": stairs, "steps": steps, "avg_wartezeit": avg_wartezeit}


def evaluiere(policy, label: str, n: int = 2) -> None:
    env = gymnasium.make("ElevatorEnv-v0")
    ergebnisse = [_episode(env, policy) for _ in range(n)]
    env.close()
    r  = np.mean([e["reward"]        for e in ergebnisse])
    d  = np.mean([e["delivered"]     for e in ergebnisse])
    s  = np.mean([e["stairs"]        for e in ergebnisse])
    w  = np.mean([e["avg_wartezeit"] for e in ergebnisse])
    print(f"  {label:<22s}  Ø Reward {r:8.1f}  |  "
          f"Aufzug {d:6.1f}  |  Treppe {s:5.1f}  |  Ø Wartezeit {w:6.1f}s")
    print(f"Anteil Treppe:  {s / (d + s)}")


best_zip = os.path.join(OUTPUT_DIR, "best_model.zip")
print("\n─── Vergleich (je 2 Episoden in der Gym-Umgebung) ───")
if os.path.exists(best_zip):
    evaluiere(PPO.load(os.path.join(OUTPUT_DIR, "best_model")), "RL  (bestes Modell)")
evaluiere(PPO.load(final_path), "RL  (letztes Modell)")
evaluiere(None,                 "Zufallsstrategie   ")

# ── 6. Verwendung in der echten Simulation ─────────────────────────────
best_oder_final = (
    os.path.join(OUTPUT_DIR, "best_model")
    if os.path.exists(best_zip)
    else final_path
)
