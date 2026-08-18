# Schedule Sweep Comparison (Temperature & Stagger)

Generated: 2026-06-21T08:53:12.665776+00:00

**Sweep ID:** `sched_r10_bo` at N=10.

**Stack:** P1 cache + early stop + hybrid schema prune (no P2 discovery, no P3 semantic store).

**Scenarios:** uniform/ladder temperature; linear stagger (seconds or turn polls).

50-task BIRD mini-dev smoke subset; `best_of_n` coordination.

## DeepSeek V3.2

| Scenario | EX % | Redundancy % | Overhead × | Tokens | Δ tok vs t0 | Δ EX vs t0 |
|----------|-------:|-------------:|-----------:|-------:|------------:|-----------:|
| t03_stag2s | 64.0 | 45.8 | 3.86 | 5,532,575 | -22.3% | +0pp |
| stag2s | 64.0 | 48.4 | 3.30 | 5,814,115 | -18.3% | +0pp |
| stag1t | 64.0 | 59.8 | 5.15 | 6,225,627 | -12.5% | +0pp |
| ladder | 68.0 | 50.9 | 11.96 | 6,941,153 | -2.5% | +4pp |
| t07 | 64.0 | 58.0 | 11.51 | 7,015,363 | -1.4% | +0pp |
| t03 | 64.0 | 65.1 | 11.36 | 6,862,305 | -3.6% | +0pp |
| t0 | 64.0 | 71.1 | 10.82 | 7,117,031 | — | — |

**Best on subset:** `ladder` — EX **68.0%**, 6,941,153 tokens, redundancy 50.87%.

**Best schedule vs P2 full stack+prune:** EX +4 pp, tokens +32.2%.

| | P2+prune | Best schedule (`ladder`) |
|---|--:|--:|
| EX % | 64.0 | 68.0 |
| Tokens | 5,251,285 | 6,941,153 |
| Redundancy % | 75.65 | 50.87 |

### Recommendations vs t0

- **t03_stag2s:** **Adopt** — EX +0 pp and tokens -22.3% vs t0.
- **stag2s:** **Adopt** — EX +0 pp and tokens -18.3% vs t0.
- **stag1t:** **Adopt** — EX +0 pp and tokens -12.5% vs t0.
- **ladder:** **Adopt** — EX +4 pp with modest token cost (-2.5%).
- **t07:** **Mixed** — EX +0 pp, tokens -1.4%, redundancy -13 pp vs t0.
- **t03:** **Mixed** — EX +0 pp, tokens -3.6%, redundancy -6 pp vs t0.

## Gemini 2.5 Flash

| Scenario | EX % | Redundancy % | Overhead × | Tokens | Δ tok vs t0 | Δ EX vs t0 |
|----------|-------:|-------------:|-----------:|-------:|------------:|-----------:|
| t03_stag2s | 82.0 | 16.3 | 2.28 | 483,807 | -55.7% | +2pp |
| stag2s | 78.0 | 27.1 | 2.43 | 513,575 | -53.0% | -2pp |
| stag1t | 76.0 | 44.5 | 3.42 | 646,068 | -40.8% | -4pp |
| ladder | 80.0 | 29.9 | 10.41 | 1,008,806 | -7.6% | +0pp |
| t07 | 82.0 | 35.1 | 10.56 | 1,063,070 | -2.6% | +2pp |
| t03 | 82.0 | 42.3 | 10.70 | 1,016,996 | -6.8% | +2pp |
| t0 | 80.0 | 65.5 | 10.59 | 1,091,821 | — | — |

**Best on subset:** `t03_stag2s` — EX **82.0%**, 483,807 tokens, redundancy 16.31%.

**Best schedule vs P2 full stack+prune:** EX +6 pp, tokens -57.0%.

| | P2+prune | Best schedule (`t03_stag2s`) |
|---|--:|--:|
| EX % | 76.0 | 82.0 |
| Tokens | 1,124,009 | 483,807 |
| Redundancy % | 69.9 | 16.31 |

### Recommendations vs t0

- **t03_stag2s:** **Adopt** — EX +2 pp and tokens -55.7% vs t0.
- **stag2s:** **Adopt** — Tokens -53.0% and redundancy -38 pp vs t0; EX -2 pp.
- **stag1t:** **Mixed** — EX -4 pp, tokens -40.8%, redundancy -21 pp vs t0.
- **ladder:** **Adopt** — EX +0 pp and tokens -7.6% vs t0.
- **t07:** **Adopt** — EX +2 pp with modest token cost (-2.6%).
- **t03:** **Adopt** — EX +2 pp and tokens -6.9% vs t0.

## GPT-4o mini

| Scenario | EX % | Redundancy % | Overhead × | Tokens | Δ tok vs t0 | Δ EX vs t0 |
|----------|-------:|-------------:|-----------:|-------:|------------:|-----------:|
| t03_stag2s | 64.0 | 39.0 | 2.64 | 2,262,297 | -26.8% | +4pp |
| stag2s | 58.0 | 44.6 | 1.93 | 3,223,211 | +4.4% | -2pp |
| stag1t | 62.0 | 56.0 | 3.50 | 3,021,434 | -2.2% | +2pp |
| ladder | 64.0 | 43.3 | 11.20 | 3,288,992 | +6.5% | +4pp |
| t07 | 60.0 | 50.3 | 11.31 | 2,211,451 | -28.4% | +0pp |
| t03 | 62.0 | 69.4 | 10.44 | 2,619,506 | -15.2% | +2pp |
| t0 | 60.0 | 82.2 | 10.18 | 3,088,340 | — | — |

**Best on subset:** `t03_stag2s` — EX **64.0%**, 2,262,297 tokens, redundancy 38.99%.

**Best schedule vs P2 full stack+prune:** EX +8 pp, tokens +22.5%.

| | P2+prune | Best schedule (`t03_stag2s`) |
|---|--:|--:|
| EX % | 56.0 | 64.0 |
| Tokens | 1,847,079 | 2,262,297 |
| Redundancy % | 79.87 | 38.99 |

### Recommendations vs t0

- **t03_stag2s:** **Adopt** — EX +4 pp and tokens -26.7% vs t0.
- **stag2s:** **Mixed** — EX -2 pp, tokens +4.4%, redundancy -38 pp vs t0.
- **stag1t:** **Adopt** — EX +2 pp with modest token cost (-2.2%).
- **ladder:** **Mixed** — EX +4 pp, tokens +6.5%, redundancy -39 pp vs t0.
- **t07:** **Adopt** — EX +0 pp and tokens -28.4% vs t0.
- **t03:** **Adopt** — EX +2 pp and tokens -15.2% vs t0.

## Cross-model summary

| Model | Best scenario | EX % | Tokens | vs t0 EX | vs t0 tokens |
|-------|---------------|-----:|-------:|---------:|-------------:|
| DeepSeek V3.2 | ladder | 68.0 | 6,941,153 | +4pp | -2.5% |
| Gemini 2.5 Flash | t03_stag2s | 82.0 | 483,807 | +2pp | -55.7% |
| GPT-4o mini | t03_stag2s | 64.0 | 2,262,297 | +4pp | -26.8% |
