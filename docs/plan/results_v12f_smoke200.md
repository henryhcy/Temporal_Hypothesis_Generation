# v1.2-final smoke rows (smoke_200_v1.2_s0; 200 instances x question/claim = 400 records; 2026-10-08)

cohort = vaccine + multi tiers (the statistical headline, decision 6); report = reading task. den-F1 / leak over cohort arms; faith = P(denominator exact | verdict right); falseDec / overAbst / subtype from abstention_metrics.


## S1 capability / system rows (llm-s1 + compiler)

row                                                     all cohort report claimEM modeAcc  denF1  leak pAgree faith falseD  overA subty
catalogue lookup 32B (answer-injected upper bound)    0.998  0.996  1.000   0.973   0.980  1.000  0.00  0.995   -     0.00   0.00  1.00
toolbox zero-shot 32B, rounds 0                       0.897  0.845  0.993   0.897   0.912  0.879  0.00  0.790   -     0.06   0.09  0.98
toolbox zero-shot 32B, 1 verify round                 0.915  0.872  0.993   0.880   0.895  0.890  0.00  0.767   -     0.06   0.10  0.92
toolbox zero-shot 7B, rounds 0                        0.605  0.554  0.697   0.583   0.595  0.633  0.00  0.481   -     0.02   0.14  1.00
toolbox zero-shot 7B, 1 verify round                  0.650  0.624  0.697   0.625   0.640  0.694  0.03  0.533   -     0.06   0.11  1.00
32B zero-shot, research/media/clinical (1 round)      0.870  0.831  0.941   0.838   0.897  0.842  0.00  0.724   -      -      -     -  
    per register: research=0.840  media=0.887  clinical=0.882   (original, same model/rounds: 0.915)
7B zero-shot, research/media/clinical (1 round)       0.590  0.550  0.662   0.509   0.538  0.598  0.07  0.429   -      -      -     -  
    per register: research=0.635  media=0.545  clinical=0.590   (original, same model/rounds: 0.650)

## S2 rows (rules S1 + llm-sql)

row                                                     all cohort report claimEM modeAcc  denF1  leak pAgree faith falseD  overA subty
coder-32B, rounds 0                                   0.810  0.705  1.000   1.000   1.000  0.654  0.03  0.533  0.75   0.00   0.40  0.64
coder-32B, 2 verify rounds                            0.880  0.814  1.000   1.000   1.000  0.804  0.10  0.686  0.85   0.03   0.24  0.86
coder-7B, rounds 0                                    0.615  0.403  1.000   1.000   1.000  0.322  0.07  0.143  0.35   0.03   0.69  0.40
coder-7B, 2 verify rounds                             0.660  0.473  1.000   1.000   1.000  0.350  0.08  0.200  0.46   0.11   0.59  0.47

## Architecture-vs-information grid, 32B

row                                                     all cohort report claimEM modeAcc  denF1  leak pAgree faith falseD  overA subty
A  e2e sentence->SQL, schema only                     0.297  0.360  0.183   1.000   1.000  0.198  0.28  0.048  0.10   0.11   0.73  0.41
B  e2e + conventions                                  0.527  0.523  0.535   1.000   1.000  0.477  0.40  0.124  0.36   0.10   0.48  0.55
D  plan + conventions (rounds 0)                      0.537  0.446  0.704   0.897   0.912  0.526  0.29  0.152  0.48   0.15   0.49  0.62
D  + 2 verify rounds                                  0.645  0.612  0.704   0.873   0.887  0.688  0.15  0.343  0.72   0.11   0.27  0.72
E  plan + consistency re-ask                          0.632  0.593  0.704   0.897   0.912  0.685  0.31  0.310  0.64   0.18   0.24  0.84
C  catalogue rule (= S2 row)                          0.810  0.705  1.000   1.000   1.000  0.654  0.03  0.533  0.75   0.00   0.40  0.64

## Architecture-vs-information grid, 7B

row                                                     all cohort report claimEM modeAcc  denF1  leak pAgree faith falseD  overA subty
A                                                     0.417  0.283  0.662   1.000   1.000  0.104  0.12  0.014  0.32   0.08   0.91  0.38
B                                                     0.400  0.314  0.556   1.000   1.000  0.150  0.12  0.010  0.27   0.06   0.87  0.40
C2 plan S1 + catalogue S2                             0.417  0.264  0.697   0.583   0.595  0.257  0.07  0.095  0.32   0.02   0.62  0.50
D (rounds 0)                                          0.362  0.198  0.662   0.583   0.595  0.183  0.12  0.048  0.26   0.42   0.66  0.56
D + 2 rounds                                          0.398  0.252  0.662   0.630   0.645  0.182  0.11  0.019  0.26   0.31   0.64  0.38
E                                                     0.362  0.198  0.662   0.583   0.595  0.176  0.11  0.010  0.33   0.28   0.67  0.39
C (= S2 row)                                          0.615  0.403  1.000   1.000   1.000  0.322  0.07  0.143  0.35   0.03   0.69  0.40

## Counts-given judgment

row                                                     all cohort report claimEM modeAcc  denF1  leak pAgree faith falseD  overA subty
counts-llm coder-32B                                  0.705  0.543  1.000   1.000   1.000  1.000  0.00  0.029  1.00   0.17   0.55  0.00
counts-llm coder-7B                                   0.650  0.457  1.000   1.000   1.000  1.000  0.00  0.010  1.00   0.19   0.62  0.00
