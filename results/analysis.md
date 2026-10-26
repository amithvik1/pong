# Experiment Results

Source: `results/summary.csv`

## Aggregate (mean ± std over repeats)

| mode | bg | players | metric | mean | std | n |
|---|---|---|---|---|---|---|
| baseline | none | 2 | delay_mean_ms | 0.182 | 0.000 | 1 |
| baseline | none | 2 | delay_p95_ms | 0.411 | 0.000 | 1 |
| baseline | none | 2 | jitter_ms | 0.111 | 0.000 | 1 |
| baseline | none | 2 | loss_pct | 0.000 | 0.000 | 1 |
| baseline | none | 2 | rtt_mean_ms | 0.234 | 0.000 | 1 |
| baseline | none | 2 | rtt_p95_ms | 0.700 | 0.000 | 1 |
| baseline | none | 2 | server_delay_mean_ms | 0.127 | 0.000 | 1 |
| baseline | none | 2 | server_delay_p95_ms | 0.350 | 0.000 | 1 |
| baseline | none | 2 | server_jitter_ms | 0.072 | 0.000 | 1 |
| baseline | none | 2 | server_loss_pct | 0.000 | 0.000 | 1 |
| priority | none | 2 | delay_mean_ms | 0.132 | 0.000 | 1 |
| priority | none | 2 | delay_p95_ms | 0.200 | 0.000 | 1 |
| priority | none | 2 | jitter_ms | 0.057 | 0.000 | 1 |
| priority | none | 2 | loss_pct | 0.000 | 0.000 | 1 |
| priority | none | 2 | rtt_mean_ms | 0.203 | 0.000 | 1 |
| priority | none | 2 | rtt_p95_ms | 0.444 | 0.000 | 1 |
| priority | none | 2 | server_delay_mean_ms | 0.092 | 0.000 | 1 |
| priority | none | 2 | server_delay_p95_ms | 0.129 | 0.000 | 1 |
| priority | none | 2 | server_jitter_ms | 0.044 | 0.000 | 1 |
| priority | none | 2 | server_loss_pct | 0.000 | 0.000 | 1 |

## Baseline vs Priority — delay improvement

| bg | players | baseline mean | priority mean | factor |
|---|---|---|---|---|
| none | 2 | 0.182 | 0.132 | 1.38x |
