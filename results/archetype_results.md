## Experiment 1, Structure (M_STA, deterministic)

| Condition | Nodes reached (of 24) |
|---|---|
| S1_flat | 24 |
| S2_segmented | 8 |
| S3_isolated_critical | 16 |
| S4_redundant_channel | 16 |

Signature (reached set differs, S1 vs S2): True

## Experiment 2, Time (M_STA, deterministic, latency 2)

| Condition | Fraction reached before first observation | First observation step |
|---|---|---|
| T1_immediate | 1.00 | 5 |
| T2_staged | 0.10 | 5 |

Temporal ablation (T2, interval sweep):

| Interval | Fraction before observation | First observation step |
|---|---|---|
| 0 | 1.00 | 5 |
| 1 | 1.00 | 5 |
| 2 | 1.00 | 5 |
| 3 | 1.00 | 5 |
| 4 | 0.10 | 5 |
| 6 | 0.10 | 5 |
| 8 | 0.10 | 5 |

Signature (T2 < T1): True

## Experiment 3, Adaptation (M_STA, stochastic, 30 paired seeds)

| Condition | Mean final extent | Mean remediations | Mean revocations |
|---|---|---|---|
| open_loop | 1.000 | 0.0 | 0.0 |
| closed_remediate_only | 0.998 | 5.0 | 0.0 |
| closed_loop | 0.484 | 4.7 | 1.0 |

Median paired difference (open - closed, revoke trust): 0.533; closed lower in 93% of seeds. Signature: True
Median paired difference (open - closed, remediation only): 0.000 (secondary: state restoration alone under a persistent trusted source)

## Ablation matrix: signature present?

| Model | Structure | Time | Adaptation |
|---|---|---|---|
| M_STA | True | True | True |
| M_ST | True | True | False |
| M_SA | True | False | True |
| M_S | True | False | False |
| M_TA | False | False | False |

H4 (all three signatures present under M_STA): True
H5 (each dimension's removal loses its signature: TA/Structure, SA/Time, ST/Adaptation): True
