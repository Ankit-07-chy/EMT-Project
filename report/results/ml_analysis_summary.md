# ML / NN analysis tables (2026-11-06 05:33)

Mixed simulated test set: 6000 traces, 4513 with a fault (SNR 10–40 dB, rise 2–10 ns, 0.5–20 m, all fault types). Bundle trained 2026-11-06T04:49:28 on 20000 traces. Best regressor (fair MAE): **ET-B**; best classifier (macro-F1): **CNN-A**.

## Localization: every trace each method gave a distance for

| method | n | coverage | MAE_m | RMSE_m | MedAE_m | P90_m | P95_m | max_m | bias_m | within_0_25m | within_0_5m | gross_gt_1m |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| Baseline | 3828 | 84.8% | 0.261 | 0.756 | 0.146 | 0.471 | 0.605 | 15.594 | 0.096 | 69.5% | 91.2% | 1.4% |
| RF-A | 4511 | 100.0% | 0.526 | 1.321 | 0.171 | 1.154 | 2.680 | 11.871 | -0.008 | 63.5% | 82.5% | 10.7% |
| RF-B | 4511 | 100.0% | 0.370 | 1.035 | 0.160 | 0.552 | 1.268 | 17.284 | -0.020 | 67.2% | 88.2% | 5.7% |
| ET-A | 4511 | 100.0% | 0.471 | 1.223 | 0.163 | 0.900 | 2.134 | 12.119 | -0.009 | 65.6% | 84.9% | 9.2% |
| ET-B | 4511 | 100.0% | 0.369 | 1.060 | 0.156 | 0.526 | 1.234 | 17.106 | -0.017 | 68.3% | 89.1% | 5.7% |
| KNN-A | 4511 | 100.0% | 0.482 | 1.322 | 0.169 | 0.748 | 2.047 | 15.779 | 0.004 | 64.3% | 85.1% | 8.3% |
| KNN-B | 4511 | 100.0% | 0.752 | 1.705 | 0.277 | 1.582 | 3.779 | 13.900 | 0.008 | 46.2% | 70.0% | 14.9% |
| MLP-A | 4511 | 100.0% | 0.439 | 1.049 | 0.200 | 0.774 | 1.466 | 12.293 | -0.029 | 58.0% | 82.0% | 7.6% |
| MLP-B | 4511 | 100.0% | 0.508 | 1.284 | 0.197 | 0.862 | 2.074 | 16.291 | 0.009 | 58.8% | 81.8% | 8.8% |
| CNN-A | 4511 | 100.0% | 0.315 | 0.830 | 0.188 | 0.509 | 0.697 | 17.252 | -0.044 | 65.1% | 89.6% | 2.9% |

## Localization: faults the baseline located (same traces for every method)

| method | n | MAE_m | MedAE_m | P95_m | max_m | within_0_25m |
|---|---|---|---|---|---|---|
| Baseline | 3828 | 0.261 | 0.146 | 0.605 | 15.594 | 69.5% |
| RF-A | 3828 | 0.287 | 0.145 | 0.844 | 11.484 | 70.7% |
| RF-B | 3828 | 0.190 | 0.136 | 0.471 | 9.114 | 74.5% |
| ET-A | 3828 | 0.249 | 0.141 | 0.631 | 10.750 | 73.0% |
| ET-B | 3828 | 0.187 | 0.135 | 0.462 | 13.357 | 75.6% |
| KNN-A | 3828 | 0.256 | 0.143 | 0.621 | 12.073 | 70.6% |
| KNN-B | 3828 | 0.365 | 0.233 | 1.047 | 13.752 | 52.9% |
| MLP-A | 3828 | 0.265 | 0.175 | 0.692 | 8.223 | 64.5% |
| MLP-B | 3828 | 0.240 | 0.169 | 0.637 | 12.477 | 66.2% |
| CNN-A | 3828 | 0.214 | 0.178 | 0.537 | 4.240 | 68.9% |

### MAE (m) by fault type: faults the baseline located (same traces for all)

| level | baseline finds | Baseline | RF-A | RF-B | ET-A | ET-B | KNN-A | KNN-B | MLP-A | MLP-B | CNN-A |
|---|---|---|---|---|---|---|---|---|---|---|---|
| end: open | 95.4% | 0.240 | 0.218 | 0.168 | 0.186 | 0.170 | 0.169 | 0.293 | 0.212 | 0.215 | 0.199 |
| end: partial | 64.5% | 0.254 | 0.283 | 0.215 | 0.266 | 0.214 | 0.320 | 0.569 | 0.287 | 0.305 | 0.216 |
| end: short | 94.9% | 0.237 | 0.240 | 0.161 | 0.196 | 0.161 | 0.174 | 0.272 | 0.223 | 0.193 | 0.215 |
| impedance step | 64.2% | 0.457 | 0.286 | 0.288 | 0.282 | 0.310 | 0.344 | 0.691 | 0.309 | 0.406 | 0.211 |
| open stub | 64.5% | 0.769 | 2.586 | 0.742 | 2.280 | 0.554 | 2.461 | 1.017 | 1.585 | 0.736 | 0.502 |
| series resistor | 58.3% | 0.282 | 0.209 | 0.212 | 0.226 | 0.207 | 0.365 | 0.577 | 0.317 | 0.322 | 0.191 |
| shunt resistor | 63.2% | 0.290 | 0.277 | 0.205 | 0.239 | 0.203 | 0.357 | 0.558 | 0.343 | 0.291 | 0.220 |

### MAE (m) by fault type: every fault each method gave a distance for

| level | baseline finds | Baseline | RF-A | RF-B | ET-A | ET-B | KNN-A | KNN-B | MLP-A | MLP-B | CNN-A |
|---|---|---|---|---|---|---|---|---|---|---|---|
| end: open | 95.4% | 0.240 | 0.246 | 0.183 | 0.201 | 0.179 | 0.175 | 0.320 | 0.222 | 0.231 | 0.204 |
| end: partial | 64.5% | 0.254 | 0.910 | 0.741 | 0.861 | 0.743 | 0.917 | 1.577 | 0.785 | 1.013 | 0.492 |
| end: short | 94.9% | 0.237 | 0.268 | 0.176 | 0.212 | 0.170 | 0.185 | 0.309 | 0.233 | 0.211 | 0.217 |
| impedance step | 64.2% | 0.457 | 0.871 | 0.628 | 0.806 | 0.692 | 0.788 | 1.626 | 0.729 | 1.040 | 0.434 |
| open stub | 64.5% | 0.769 | 3.315 | 1.742 | 3.093 | 1.691 | 3.515 | 2.205 | 2.323 | 2.044 | 1.310 |
| series resistor | 58.3% | 0.282 | 0.857 | 0.582 | 0.798 | 0.573 | 0.801 | 1.758 | 0.723 | 1.037 | 0.416 |
| shunt resistor | 63.2% | 0.290 | 0.803 | 0.586 | 0.778 | 0.616 | 0.965 | 1.592 | 0.661 | 1.001 | 0.420 |

### MAE (m) by distance (m): faults the baseline located (same traces for all)

| level | baseline finds | Baseline | RF-A | RF-B | ET-A | ET-B | KNN-A | KNN-B | MLP-A | MLP-B | CNN-A |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 0.5-2 | 82.9% | 0.237 | 0.288 | 0.169 | 0.237 | 0.133 | 0.191 | 0.343 | 0.235 | 0.189 | 0.215 |
| 10-15 | 83.5% | 0.288 | 0.240 | 0.207 | 0.226 | 0.211 | 0.268 | 0.339 | 0.269 | 0.240 | 0.220 |
| 15-20 | 83.5% | 0.405 | 0.491 | 0.282 | 0.399 | 0.290 | 0.372 | 0.491 | 0.380 | 0.347 | 0.303 |
| 2-5 | 86.9% | 0.115 | 0.197 | 0.102 | 0.167 | 0.092 | 0.158 | 0.298 | 0.188 | 0.176 | 0.164 |
| 5-10 | 87.0% | 0.184 | 0.185 | 0.139 | 0.175 | 0.132 | 0.205 | 0.311 | 0.201 | 0.189 | 0.149 |

### MAE (m) by distance (m): every fault each method gave a distance for

| level | baseline finds | Baseline | RF-A | RF-B | ET-A | ET-B | KNN-A | KNN-B | MLP-A | MLP-B | CNN-A |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 0.5-2 | 82.9% | 0.237 | 0.826 | 0.452 | 0.706 | 0.456 | 0.422 | 1.273 | 0.551 | 0.622 | 0.374 |
| 10-15 | 83.5% | 0.288 | 0.320 | 0.346 | 0.313 | 0.345 | 0.455 | 0.542 | 0.382 | 0.392 | 0.298 |
| 15-20 | 83.5% | 0.405 | 0.811 | 0.533 | 0.724 | 0.535 | 0.667 | 0.972 | 0.635 | 0.708 | 0.444 |
| 2-5 | 86.9% | 0.115 | 0.514 | 0.284 | 0.445 | 0.294 | 0.400 | 0.805 | 0.357 | 0.496 | 0.264 |
| 5-10 | 87.0% | 0.184 | 0.346 | 0.249 | 0.305 | 0.236 | 0.386 | 0.532 | 0.306 | 0.387 | 0.209 |

### MAE (m) by SNR (dB): faults the baseline located (same traces for all)

| level | baseline finds | Baseline | RF-A | RF-B | ET-A | ET-B | KNN-A | KNN-B | MLP-A | MLP-B | CNN-A |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 10-15 | 59.6% | 0.340 | 0.628 | 0.230 | 0.446 | 0.218 | 0.306 | 0.547 | 0.405 | 0.309 | 0.262 |
| 15-20 | 77.5% | 0.326 | 0.305 | 0.206 | 0.261 | 0.213 | 0.215 | 0.389 | 0.280 | 0.270 | 0.222 |
| 20-30 | 90.0% | 0.267 | 0.230 | 0.179 | 0.218 | 0.186 | 0.234 | 0.349 | 0.238 | 0.230 | 0.209 |
| 30-40 | 96.9% | 0.203 | 0.220 | 0.179 | 0.208 | 0.166 | 0.276 | 0.309 | 0.237 | 0.215 | 0.200 |

### MAE (m) by SNR (dB): every fault each method gave a distance for

| level | baseline finds | Baseline | RF-A | RF-B | ET-A | ET-B | KNN-A | KNN-B | MLP-A | MLP-B | CNN-A |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 10-15 | 59.6% | 0.340 | 1.170 | 0.738 | 0.988 | 0.720 | 0.903 | 1.313 | 0.865 | 0.904 | 0.588 |
| 15-20 | 77.5% | 0.326 | 0.643 | 0.464 | 0.596 | 0.481 | 0.561 | 0.989 | 0.540 | 0.644 | 0.367 |
| 20-30 | 90.0% | 0.267 | 0.396 | 0.292 | 0.371 | 0.304 | 0.385 | 0.652 | 0.347 | 0.438 | 0.253 |
| 30-40 | 96.9% | 0.203 | 0.249 | 0.203 | 0.229 | 0.189 | 0.312 | 0.431 | 0.252 | 0.296 | 0.203 |

### MAE (m) by rise time (ns): faults the baseline located (same traces for all)

| level | baseline finds | Baseline | RF-A | RF-B | ET-A | ET-B | KNN-A | KNN-B | MLP-A | MLP-B | CNN-A |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 2-4 | 84.0% | 0.241 | 0.257 | 0.171 | 0.222 | 0.172 | 0.240 | 0.338 | 0.254 | 0.224 | 0.208 |
| 4-6 | 85.2% | 0.257 | 0.304 | 0.198 | 0.265 | 0.203 | 0.253 | 0.369 | 0.270 | 0.251 | 0.224 |
| 6-8 | 85.3% | 0.247 | 0.280 | 0.177 | 0.239 | 0.171 | 0.246 | 0.373 | 0.249 | 0.232 | 0.212 |
| 8-10 | 84.7% | 0.297 | 0.307 | 0.211 | 0.269 | 0.199 | 0.283 | 0.378 | 0.285 | 0.253 | 0.212 |

### MAE (m) by rise time (ns): every fault each method gave a distance for

| level | baseline finds | Baseline | RF-A | RF-B | ET-A | ET-B | KNN-A | KNN-B | MLP-A | MLP-B | CNN-A |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 2-4 | 84.0% | 0.241 | 0.511 | 0.345 | 0.452 | 0.346 | 0.468 | 0.695 | 0.427 | 0.455 | 0.310 |
| 4-6 | 85.2% | 0.257 | 0.541 | 0.394 | 0.496 | 0.401 | 0.459 | 0.779 | 0.444 | 0.534 | 0.314 |
| 6-8 | 85.3% | 0.247 | 0.504 | 0.353 | 0.447 | 0.346 | 0.485 | 0.745 | 0.433 | 0.474 | 0.320 |
| 8-10 | 84.7% | 0.297 | 0.546 | 0.388 | 0.487 | 0.382 | 0.512 | 0.787 | 0.452 | 0.564 | 0.316 |

### MAE (m) by |Gamma|: faults the baseline located (same traces for all)

| level | baseline finds | Baseline | RF-A | RF-B | ET-A | ET-B | KNN-A | KNN-B | MLP-A | MLP-B | CNN-A |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 0.1-0.3 | 43.9% | 0.384 | 0.396 | 0.326 | 0.349 | 0.331 | 0.571 | 0.786 | 0.387 | 0.391 | 0.230 |
| 0.3-0.6 | 75.4% | 0.322 | 0.544 | 0.258 | 0.510 | 0.235 | 0.553 | 0.602 | 0.445 | 0.352 | 0.242 |
| <0.1 | 13.7% | 0.578 | 1.271 | 0.855 | 1.009 | 0.640 | 1.957 | 1.552 | 1.401 | 1.254 | 0.557 |
| >=0.6 | 94.5% | 0.241 | 0.229 | 0.166 | 0.191 | 0.167 | 0.174 | 0.290 | 0.219 | 0.206 | 0.206 |

### MAE (m) by |Gamma|: every fault each method gave a distance for

| level | baseline finds | Baseline | RF-A | RF-B | ET-A | ET-B | KNN-A | KNN-B | MLP-A | MLP-B | CNN-A |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 0.1-0.3 | 43.9% | 0.384 | 1.429 | 0.995 | 1.295 | 1.044 | 1.350 | 2.533 | 1.076 | 1.479 | 0.538 |
| 0.3-0.6 | 75.4% | 0.322 | 0.842 | 0.557 | 0.819 | 0.550 | 0.909 | 1.084 | 0.714 | 0.731 | 0.435 |
| <0.1 | 13.7% | 0.578 | 3.032 | 2.483 | 2.902 | 2.405 | 3.281 | 4.549 | 2.526 | 3.944 | 1.903 |
| >=0.6 | 94.5% | 0.241 | 0.259 | 0.182 | 0.210 | 0.178 | 0.185 | 0.329 | 0.230 | 0.227 | 0.211 |

## 15 worst predictions of ET-B

| true_d_m | pred_d_m | error_m | fault | gamma_true | snr_db | rise_ns | baseline_d_m | baseline_found |
|---|---|---|---|---|---|---|---|---|
| 19.353 | 2.246 | -17.106 | end: partial | 0.382 | 11.582 | 5.475 | nan | False |
| 0.886 | 14.244 | 13.357 | impedance step | 0.254 | 26.978 | 4.335 | 16.480 | True |
| 1.055 | 13.059 | 12.005 | open stub | -0.333 | 10.079 | 2.192 | nan | False |
| 3.242 | 14.378 | 11.136 | open stub | -0.333 | 16.931 | 8.667 | nan | False |
| 19.689 | 8.554 | -11.135 | end: partial | -0.139 | 29.718 | 4.752 | nan | False |
| 19.419 | 8.734 | -10.685 | end: partial | 0.094 | 15.863 | 3.134 | nan | False |
| 19.866 | 9.331 | -10.535 | open stub | -0.333 | 21.208 | 4.238 | nan | False |
| 0.538 | 10.741 | 10.203 | open stub | -0.333 | 23.580 | 8.756 | nan | False |
| 1.630 | 11.797 | 10.167 | end: partial | -0.145 | 12.234 | 4.154 | nan | False |
| 14.880 | 4.755 | -10.125 | end: partial | 0.231 | 17.125 | 9.102 | nan | False |
| 0.790 | 10.591 | 9.801 | shunt resistor | -0.072 | 10.408 | 9.161 | nan | False |
| 17.205 | 7.788 | -9.417 | end: partial | -0.254 | 10.651 | 3.673 | nan | False |
| 3.489 | 12.901 | 9.412 | open stub | -0.333 | 23.528 | 6.026 | nan | False |
| 18.426 | 9.427 | -8.999 | end: partial | -0.315 | 10.056 | 7.444 | nan | False |
| 2.899 | 11.611 | 8.712 | shunt resistor | -0.088 | 29.277 | 9.371 | nan | False |

## Detection: is there a fault? (matched = no fault)

| method | TP | FP | FN | TN | precision | recall | F1 | false_alarm_rate | miss_rate | accuracy |
|---|---|---|---|---|---|---|---|---|---|---|
| Baseline | 3820 | 22 | 693 | 1465 | 0.994 | 0.846 | 0.914 | 1.5% | 15.4% | 0.881 |
| RF-A | 4369 | 36 | 144 | 1451 | 0.992 | 0.968 | 0.980 | 2.4% | 3.2% | 0.970 |
| RF-B | 4412 | 36 | 101 | 1451 | 0.992 | 0.978 | 0.985 | 2.4% | 2.2% | 0.977 |
| ET-A | 4349 | 23 | 164 | 1464 | 0.995 | 0.964 | 0.979 | 1.5% | 3.6% | 0.969 |
| ET-B | 4409 | 26 | 104 | 1461 | 0.994 | 0.977 | 0.985 | 1.7% | 2.3% | 0.978 |
| KNN-A | 4268 | 22 | 245 | 1465 | 0.995 | 0.946 | 0.970 | 1.5% | 5.4% | 0.956 |
| KNN-B | 4291 | 72 | 222 | 1415 | 0.983 | 0.951 | 0.967 | 4.8% | 4.9% | 0.951 |
| MLP-A | 4407 | 57 | 106 | 1430 | 0.987 | 0.977 | 0.982 | 3.8% | 2.3% | 0.973 |
| MLP-B | 4388 | 58 | 125 | 1429 | 0.987 | 0.972 | 0.980 | 3.9% | 2.8% | 0.970 |
| CNN-A | 4429 | 18 | 84 | 1469 | 0.996 | 0.981 | 0.989 | 1.2% | 1.9% | 0.983 |

## Detection: per class

F1 per class:

| method | open | short | matched | partial |
|---|---|---|---|---|
| Baseline | 0.958 | 0.947 | 0.804 | 0.730 |
| CNN-A | 1.000 | 0.999 | 0.967 | 0.964 |
| ET-A | 0.999 | 0.999 | 0.941 | 0.932 |
| ET-B | 0.999 | 0.999 | 0.958 | 0.954 |
| KNN-A | 0.999 | 0.999 | 0.917 | 0.900 |
| KNN-B | 0.996 | 0.996 | 0.906 | 0.887 |
| MLP-A | 0.996 | 0.998 | 0.947 | 0.939 |
| MLP-B | 0.998 | 0.999 | 0.940 | 0.934 |
| RF-A | 0.997 | 0.998 | 0.942 | 0.933 |
| RF-B | 0.998 | 0.999 | 0.956 | 0.951 |

## Misses and false alarms (Baseline vs CNN-A)

| method | kind | factor | level | n | rate |
|---|---|---|---|---|---|
| Baseline | miss rate (fault called matched) | |Gamma| | 0.1-0.3 | 426 | 56.1% |
| Baseline | miss rate (fault called matched) | |Gamma| | 0.3-0.6 | 755 | 24.9% |
| Baseline | miss rate (fault called matched) | |Gamma| | <0.1 | 95 | 87.4% |
| Baseline | miss rate (fault called matched) | |Gamma| | >=0.6 | 3237 | 5.7% |
| Baseline | miss rate (fault called matched) | SNR (dB) | 10-15 | 802 | 40.4% |
| Baseline | miss rate (fault called matched) | SNR (dB) | 15-20 | 741 | 22.7% |
| Baseline | miss rate (fault called matched) | SNR (dB) | 20-30 | 1484 | 10.0% |
| Baseline | miss rate (fault called matched) | SNR (dB) | 30-40 | 1486 | 3.5% |
| Baseline | false-alarm rate (matched called fault) | SNR (dB) | 10-15 | 248 | 1.6% |
| Baseline | false-alarm rate (matched called fault) | SNR (dB) | 15-20 | 255 | 0.8% |
| Baseline | false-alarm rate (matched called fault) | SNR (dB) | 20-30 | 507 | 2.6% |
| Baseline | false-alarm rate (matched called fault) | SNR (dB) | 30-40 | 477 | 0.6% |
| CNN-A | miss rate (fault called matched) | |Gamma| | 0.1-0.3 | 426 | 4.2% |
| CNN-A | miss rate (fault called matched) | |Gamma| | 0.3-0.6 | 755 | 4.2% |
| CNN-A | miss rate (fault called matched) | |Gamma| | <0.1 | 95 | 33.7% |
| CNN-A | miss rate (fault called matched) | |Gamma| | >=0.6 | 3237 | 0.1% |
| CNN-A | miss rate (fault called matched) | SNR (dB) | 10-15 | 802 | 5.5% |
| CNN-A | miss rate (fault called matched) | SNR (dB) | 15-20 | 741 | 2.4% |
| CNN-A | miss rate (fault called matched) | SNR (dB) | 20-30 | 1484 | 1.1% |
| CNN-A | miss rate (fault called matched) | SNR (dB) | 30-40 | 1486 | 0.3% |
| CNN-A | false-alarm rate (matched called fault) | SNR (dB) | 10-15 | 248 | 5.2% |
| CNN-A | false-alarm rate (matched called fault) | SNR (dB) | 15-20 | 255 | 0.8% |
| CNN-A | false-alarm rate (matched called fault) | SNR (dB) | 20-30 | 507 | 0.6% |
| CNN-A | false-alarm rate (matched called fault) | SNR (dB) | 30-40 | 477 | 0.0% |

## Detection vs SNR (E1 sets)

Miss rate:

| snr_db | Baseline | CNN-A | ET-A | ET-B | KNN-A | KNN-B | MLP-A | MLP-B | RF-A | RF-B |
|---|---|---|---|---|---|---|---|---|---|---|
| 10 | 0.560 | 0.079 | 0.082 | 0.060 | 0.125 | 0.132 | 0.072 | 0.065 | 0.059 | 0.053 |
| 15 | 0.295 | 0.028 | 0.054 | 0.033 | 0.068 | 0.072 | 0.036 | 0.049 | 0.045 | 0.035 |
| 20 | 0.143 | 0.011 | 0.038 | 0.026 | 0.041 | 0.058 | 0.014 | 0.025 | 0.035 | 0.025 |
| 25 | 0.107 | 0.005 | 0.023 | 0.014 | 0.041 | 0.039 | 0.016 | 0.016 | 0.024 | 0.010 |
| 30 | 0.040 | 0.002 | 0.022 | 0.007 | 0.035 | 0.015 | 0.009 | 0.013 | 0.020 | 0.005 |
| 35 | 0.020 | 0.006 | 0.009 | 0.006 | 0.025 | 0.012 | 0.008 | 0.008 | 0.010 | 0.006 |
| 40 | 0.009 | 0.006 | 0.011 | 0.004 | 0.029 | 0.011 | 0.008 | 0.006 | 0.012 | 0.003 |

False-alarm rate:

| snr_db | Baseline | CNN-A | ET-A | ET-B | KNN-A | KNN-B | MLP-A | MLP-B | RF-A | RF-B |
|---|---|---|---|---|---|---|---|---|---|---|
| 10 | 0.030 | 0.051 | 0.148 | 0.152 | 0.121 | 0.165 | 0.145 | 0.263 | 0.283 | 0.209 |
| 15 | 0.037 | 0.031 | 0.037 | 0.048 | 0.041 | 0.082 | 0.133 | 0.044 | 0.058 | 0.065 |
| 20 | 0.021 | 0.021 | 0.010 | 0.024 | 0.003 | 0.031 | 0.052 | 0.059 | 0.017 | 0.028 |
| 25 | 0.010 | 0.007 | 0.000 | 0.007 | 0.000 | 0.035 | 0.014 | 0.014 | 0.000 | 0.007 |
| 30 | 0.011 | 0.004 | 0.004 | 0.007 | 0.000 | 0.007 | 0.007 | 0.000 | 0.000 | 0.014 |
| 35 | 0.003 | 0.000 | 0.000 | 0.003 | 0.000 | 0.013 | 0.006 | 0.000 | 0.000 | 0.000 |
| 40 | 0.000 | 0.000 | 0.000 | 0.003 | 0.000 | 0.007 | 0.000 | 0.000 | 0.003 | 0.003 |

## Latency (ms per trace, this laptop)

| stage | model | task | single_ms | batch_ms_per_trace |
|---|---|---|---|---|
| front end: preprocess + baseline + 23 features | (all) | - | 0.746 | 0.746 |
| model | RF-A | distance | 7.032 | 0.103 |
| model | ET-A | distance | 7.263 | 0.101 |
| model | KNN-A | distance | 7.401 | 0.120 |
| model | MLP-A | distance | 1.021 | 0.013 |
| model | CNN-A | distance | 1.924 | 0.162 |
| model | RF-B | distance | 8.651 | 0.175 |
| model | ET-B | distance | 6.681 | 0.098 |
| model | KNN-B | distance | 2.383 | 0.048 |
| model | MLP-B | distance | 1.121 | 0.008 |
| model | RF-A | class | 7.840 | 0.144 |
| model | ET-A | class | 6.873 | 0.098 |
| model | KNN-A | class | 8.673 | 0.163 |
| model | MLP-A | class | 0.620 | 0.012 |
| model | CNN-A | class | 2.544 | 0.102 |
| model | RF-B | class | 8.069 | 0.199 |
| model | ET-B | class | 6.738 | 0.092 |
| model | KNN-B | class | 2.527 | 0.049 |
| model | MLP-B | class | 0.800 | 0.008 |

## Selected configuration of every model (validation grid search)

| task | key | params | val_score | size_MB | detail |
|---|---|---|---|---|---|
| reg | RF-A | {'max_features': 'sqrt', 'min_samples_leaf': 2} | 4.789 | 20.264 | 100 trees, 827,092 nodes |
| reg | ET-A | {'max_features': 0.3, 'min_samples_leaf': 2} | 4.018 | 32.561 | 100 trees, 1,309,182 nodes |
| reg | KNN-A | {'n_neighbors': 5, 'weights': 'distance'} | 4.126 | 14.550 | stores 15,035 training traces, k = 5 |
| reg | MLP-A | {'hidden_layer_sizes': (256, 128), 'alpha': 0.0001} | 3.823 | 1.902 | 98,817 weights, layers (256, 128) |
| reg | CNN-A | {'epochs': 40, 'patience': 6} | 2.639 | 0.922 | 245,393 weights (1-D CNN) |
| reg | RF-B | {'max_features': 0.5, 'min_samples_leaf': 2} | 2.776 | 19.636 | 100 trees, 828,246 nodes |
| reg | ET-B | {'max_features': 1.0, 'min_samples_leaf': 2} | 2.781 | 31.552 | 100 trees, 1,303,340 nodes |
| reg | KNN-B | {'n_neighbors': 15, 'weights': 'distance'} | 7.465 | 1.084 | stores 15,035 training traces, k = 15 |
| reg | MLP-B | {'hidden_layer_sizes': (128, 64), 'alpha': 0.0001} | 4.753 | 0.226 | 11,393 weights, layers (128, 64) |
| cls | RF-A | {'max_features': 0.3, 'min_samples_leaf': 1} | 0.967 | 1.660 | 100 trees, 71,988 nodes |
| cls | ET-A | {'max_features': 'sqrt', 'min_samples_leaf': 1} | 0.968 | 4.863 | 100 trees, 257,494 nodes |
| cls | KNN-A | {'n_neighbors': 5, 'weights': 'distance'} | 0.951 | 19.312 | stores 20,000 training traces, k = 5 |
| cls | MLP-A | {'hidden_layer_sizes': (256, 128), 'alpha': 0.0001} | 0.974 | 1.120 | 99,204 weights, layers (256, 128) |
| cls | CNN-A | {'epochs': 40, 'patience': 6} | 0.985 | 0.925 | 245,780 weights (1-D CNN) |
| cls | RF-B | {'max_features': 0.5, 'min_samples_leaf': 1} | 0.979 | 1.439 | 100 trees, 67,676 nodes |
| cls | ET-B | {'max_features': 0.5, 'min_samples_leaf': 1} | 0.979 | 3.695 | 100 trees, 205,776 nodes |
| cls | KNN-B | {'n_neighbors': 5, 'weights': 'distance'} | 0.953 | 1.187 | stores 20,000 training traces, k = 5 |
| cls | MLP-B | {'hidden_layer_sizes': (256, 128), 'alpha': 0.0001} | 0.971 | 0.453 | 39,556 weights, layers (256, 128) |
