"""
Training des PPO-Agenten für die Fahrstuhlsimulation.

Ablauf
------
1. Trainingsumgebungen erstellen (echte SimPy-Simulation)
2. PPO-Modell konfigurieren und trainieren
3. Bestes Modell speichern
4. Schnellvergleich: RL-Agent vs. Zufallsstrategie in der Gym-Umgebung

Ausführen
---------
    conda run -n sim_reinforce_fg python ReinforcementLearning/train.py

TensorBoard (während oder nach dem Training)
--------------------------------------------
    tensorboard --logdir ReinforcementLearning/rl_training_output/tb_logs
"""

import os
import subprocess
import sys
import time

# Verhindert OpenMP-Konflikt zwischen Intel-MKL (Conda) und PyTorch auf Windows.
# Muss vor dem ersten numpy/torch-Import gesetzt werden.
os.environ.setdefault("KMP_DUPLICATE_LIB_OK", "TRUE")

# SB3/torch muss vor numpy importiert werden, damit PyTorch-DLLs zuerst geladen
# werden – andernfalls lädt Intel-MKL (über numpy) libiomp5md.dll und blockiert
# anschließend das Laden von torch/lib/shm.dll (WinError 127, Windows/Conda).
import torch as th
from sb3_contrib import MaskablePPO
from sb3_contrib.common.maskable.callbacks import MaskableEvalCallback
from sb3_contrib.common.maskable.utils import get_action_masks
from stable_baselines3.common.callbacks import CheckpointCallback
from stable_baselines3.common.env_util import make_vec_env
from stable_baselines3.common.monitor import Monitor
from stable_baselines3.common.vec_env import DummyVecEnv, VecNormalize

import numpy as np

_RL_DIR      = os.path.dirname(os.path.abspath(__file__))   # .../ReinforcementLearning
_PROJECT_ROOT = os.path.dirname(_RL_DIR)                     # .../SimReinforce
sys.path.insert(0, _PROJECT_ROOT)  # für Model.* in elevator_env.py
sys.path.insert(0, _RL_DIR)        # für Env-Paket
import Env  # noqa: F401 – registriert "ElevatorEnv-v0" bei Gymnasium

import gymnasium

# Konfiguration
OUTPUT_DIR   = os.path.join(_RL_DIR, "rl_training_output")
N_ENVS          = 4          # Parallele Trainingsumgebungen
TOTAL_TIMESTEPS = 10_000_000
SEED            = 42

os.makedirs(OUTPUT_DIR, exist_ok=True)

# 1. Umgebungen 
print("Erstelle Umgebungen …")
train_env = make_vec_env("ElevatorEnv-v0", n_envs=N_ENVS, seed=SEED)
train_env = VecNormalize(train_env, norm_obs=False, norm_reward=True, clip_reward=10.0)
eval_env  = DummyVecEnv([lambda: Monitor(gymnasium.make("ElevatorEnv-v0"))])
eval_env  = VecNormalize(eval_env, norm_obs=False, norm_reward=False, training=False)

# 2. Modell
model = MaskablePPO(
    "MlpPolicy",
    train_env,
    verbose=1,
    seed=SEED,
    policy_kwargs=dict(net_arch=[128, 256, 128], activation_fn=th.nn.ReLU),
    # Hyperparameter
    learning_rate=lambda progress: 3e-4 * progress,
    n_steps=4096,      # Schritte je Update-Zyklus pro Env
    batch_size=512,
    n_epochs=10,
    gamma=0.995,       # Hoher Discount-Faktor: Episoden sind ~8 000 Schritte lang
    gae_lambda=0.95,
    ent_coef=0.04,     # Entropie-Bonus hält Exploration aufrecht
    vf_coef=0.2,
    clip_range=0.3,
    tensorboard_log=os.path.join(OUTPUT_DIR, "tb_logs"),
)

# 3. Callbacks
eval_callback = MaskableEvalCallback(
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
subprocess.Popen(
    [sys.executable, "-m", "tensorboard", "--logdir", os.path.join(OUTPUT_DIR, "tb_logs")],
)
print(f"\nStarte Training: {TOTAL_TIMESTEPS:,} Schritte | {N_ENVS} parallele Envs")
print(f"TensorBoard:      http://localhost:6006\n")

t0 = time.time()
model.learn(
    total_timesteps=TOTAL_TIMESTEPS,
    callback=[eval_callback, checkpoint_callback],
)
dauer_min = (time.time() - t0) / 60

final_path = os.path.join(OUTPUT_DIR, "elevator_ppo_final")
model.save(final_path)
vec_norm_path = os.path.join(OUTPUT_DIR, "vec_normalize.pkl")
train_env.save(vec_norm_path)
print(f"\nModell gespeichert:      {final_path}.zip")
print(f"VecNormalize gespeichert: {vec_norm_path}")
print(f"Training dauerte:        {dauer_min:.1f} Minuten")


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
            masks = get_action_masks(env)
            action, _ = policy.predict(obs, deterministic=True, action_masks=masks)
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
    evaluiere(MaskablePPO.load(os.path.join(OUTPUT_DIR, "best_model")), "RL  (bestes Modell)")
evaluiere(MaskablePPO.load(final_path), "RL  (letztes Modell)")
evaluiere(None,                 "Zufallsstrategie   ")


