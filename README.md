# SimReinforce
An Elevator simulation coupled with reinforcemant learning to get an optimal elevator strategy

## Setup

### Voraussetzungen
- [Anaconda](https://www.anaconda.com/) oder [Miniconda](https://docs.conda.io/en/latest/miniconda.html)
- Windows 64-bit (die `environment.yml` enthält plattformspezifische Pakete für win-64)

### Umgebung einrichten

```bash
conda env create -f environment.yml
conda activate sim_reinforce_fg
```

Falls das nicht funktioniert, wurden folgende Bibliotheken und Versionen verwendet:

| Paket             | Version      |
|-------------------|--------------|
| Python            | 3.12.13      |
| numpy             | 2.4.3        |
| simpy             | 4.1.1        |
| matplotlib        | 3.10.9       |
| pygame            | 2.6.1        |
| gymnasium         | 1.2.3        |
| sb3-contrib       | 2.8.0        |
| stable-baselines3 | 2.8.0        |
| tensorboard       | 2.20.0       |
| torch             | 2.12.0(+cpu) |


### Simulation starten

```bash
python simulation.py
```
