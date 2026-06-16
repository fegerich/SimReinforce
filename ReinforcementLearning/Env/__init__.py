"""
Registriert ElevatorEnv-v0 bei Gymnasium, sodass die Umgebung per
gymnasium.make("ElevatorEnv-v0") erstellt werden kann.
"""
from gymnasium.envs.registration import register

register(
    id="ElevatorEnv-v0",
    entry_point="Env.elevator_env:ElevatorEnv",
    max_episode_steps=None,  # Episodenende wird intern über EPISODE_DURATION gesteuert
)
