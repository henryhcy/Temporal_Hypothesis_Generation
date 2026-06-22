# Part C: Validation Sample (gold-label correctness guard)

Each entry records the cohort, the per-report leveled orders entering the denominator, the numerator/denominator under the locked rule, and the computed gold. Recompute by hand to confirm before trusting Part A.

## 1. P-V1 (dir_bool) -- BOOL
- claim: "After Pfizer, Headache typically occurs before Abdominal pain upper."
- events: ['Headache', 'Abdominal pain upper']  vaccines: ['Pfizer']
- locked rule: precedes denom = reports with both, ordered; supported if frac>0.5
- denominator (n): 10   numerator (k): 2
- gold proportion: 0.8   gold verdict: **supported**
- 95% CI: [0.4902, 0.9433]  (width 0.4532, tag low)
- sample reports entering the denominator (vaers_id -> relevant levels):
    - 1811070: {'Headache': 0, 'Abdominal pain upper': 3}
    - 1141282: {'Headache': 1, 'Abdominal pain upper': 2}
    - 1280111: {'Headache': 0, 'Abdominal pain upper': 1}
    - 1932347: {'Headache': 0, 'Abdominal pain upper': 2}
    - 1149335: {'Headache': 0, 'Abdominal pain upper': 1}

## 2. P-V2 (prop_precedes) -- PROP
- claim: "In about 20% of Pfizer reports, Abdominal pain upper precedes Headache."
- events: ['Abdominal pain upper', 'Headache']  vaccines: ['Pfizer']
- locked rule: precedes frac; claim supported if |p-actual|<=5pp
- denominator (n): 10   numerator (k): 2
- gold proportion: 0.2   gold verdict: **supported**
- 95% CI: [0.0567, 0.5098]  (width 0.4532, tag low)
- sample reports entering the denominator (vaers_id -> relevant levels):
    - 1811070: {'Abdominal pain upper': 3, 'Headache': 0}
    - 1141282: {'Abdominal pain upper': 2, 'Headache': 1}
    - 1280111: {'Abdominal pain upper': 1, 'Headache': 0}
    - 1932347: {'Abdominal pain upper': 2, 'Headache': 0}
    - 1149335: {'Abdominal pain upper': 1, 'Headache': 0}

## 3. P-V3 (dir_choice) -- CHOICE
- claim: "After Pfizer, Headache usually comes before Abdominal pain upper."
- events: ['Headache', 'Abdominal pain upper']  vaccines: ['Pfizer']
- locked rule: precedes frac on ordered-pair denom; names higher-frac event
- denominator (n): 10   numerator (k): 2
- gold proportion: 0.8   gold verdict: **supported**
- 95% CI: [0.4902, 0.9433]  (width 0.4532, tag low)
- sample reports entering the denominator (vaers_id -> relevant levels):
    - 1811070: {'Headache': 0, 'Abdominal pain upper': 3}
    - 1141282: {'Headache': 1, 'Abdominal pain upper': 2}
    - 1280111: {'Headache': 0, 'Abdominal pain upper': 1}
    - 1932347: {'Headache': 0, 'Abdominal pain upper': 2}
    - 1149335: {'Headache': 0, 'Abdominal pain upper': 1}

## 4. C-V1 (sym_bool_cooccurs) -- BOOL
- claim: "After Pfizer, Abdominal pain upper and Fatigue typically co-occur."
- events: ['Abdominal pain upper', 'Fatigue']  vaccines: ['Pfizer']
- locked rule: co-occurs frac (both-present denom); supported if >0.5
- denominator (n): 13   numerator (k): 4
- gold proportion: 0.3077   gold verdict: **refuted**
- 95% CI: [0.1268, 0.5763]  (width 0.4495, tag low)
- sample reports entering the denominator (vaers_id -> relevant levels):
    - 1944016: {'Abdominal pain upper': 3, 'Fatigue': 0}
    - 1587341: {'Abdominal pain upper': 2, 'Fatigue': 0}
    - 1280111: {'Abdominal pain upper': 1, 'Fatigue': 0}
    - 1413308: {'Abdominal pain upper': 1, 'Fatigue': 1}
    - 1149335: {'Abdominal pain upper': 1, 'Fatigue': 1}

## 5. C-V2 (prop_cooccurs) -- PROP
- claim: "In about 31% of Pfizer reports, Abdominal pain upper and Fatigue occur together."
- events: ['Abdominal pain upper', 'Fatigue']  vaccines: ['Pfizer']
- locked rule: co-occurs frac (both-present denom); 5pp tolerance
- denominator (n): 13   numerator (k): 4
- gold proportion: 0.3077   gold verdict: **supported**
- 95% CI: [0.1268, 0.5763]  (width 0.4495, tag low)
- sample reports entering the denominator (vaers_id -> relevant levels):
    - 1944016: {'Abdominal pain upper': 3, 'Fatigue': 0}
    - 1587341: {'Abdominal pain upper': 2, 'Fatigue': 0}
    - 1280111: {'Abdominal pain upper': 1, 'Fatigue': 0}
    - 1413308: {'Abdominal pain upper': 1, 'Fatigue': 1}
    - 1149335: {'Abdominal pain upper': 1, 'Fatigue': 1}

## 6. C-V3 (sym_bool_cooccurs) -- BOOL
- claim: "After Pfizer, co-occurrence is the dominant relation for Abdominal pain upper and Fatigue."
- events: ['Abdominal pain upper', 'Fatigue']  vaccines: ['Pfizer']
- locked rule: co-occurs frac (both-present denom); supported if >0.5
- denominator (n): 13   numerator (k): 4
- gold proportion: 0.3077   gold verdict: **refuted**
- 95% CI: [0.1268, 0.5763]  (width 0.4495, tag low)
- sample reports entering the denominator (vaers_id -> relevant levels):
    - 1944016: {'Abdominal pain upper': 3, 'Fatigue': 0}
    - 1587341: {'Abdominal pain upper': 2, 'Fatigue': 0}
    - 1280111: {'Abdominal pain upper': 1, 'Fatigue': 0}
    - 1413308: {'Abdominal pain upper': 1, 'Fatigue': 1}
    - 1149335: {'Abdominal pain upper': 1, 'Fatigue': 1}

## 7. S-V2 (prop_sequence) -- PROP
- claim: "In about 0% of Pfizer reports, the sequence is Arthralgia → Chills → Fatigue."
- events: ['Arthralgia', 'Chills', 'Fatigue']  vaccines: ['Pfizer']
- locked rule: sequence frac (all-three denom); 5pp tolerance
- denominator (n): 18   numerator (k): 0
- gold proportion: 0.0   gold verdict: **supported**
- 95% CI: [0.0, 0.1759]  (width 0.1759, tag moderate)
- sample reports entering the denominator (vaers_id -> relevant levels):
    - 944881: {'Arthralgia': 0, 'Chills': 0, 'Fatigue': 1}
    - 938335: {'Arthralgia': 1, 'Chills': 1, 'Fatigue': 1}
    - 953508: {'Arthralgia': 0, 'Chills': 1, 'Fatigue': 1}
    - 1256881: {'Arthralgia': 0, 'Chills': 0, 'Fatigue': 1}
    - 1114370: {'Arthralgia': 1, 'Chills': 2, 'Fatigue': 0}

## 8. S-V3 (modal_choice) -- CHOICE
- claim: "After Pfizer, the most common ordering of Arthralgia, Chills, Fatigue is Arthralgia → Chills → Fatigue."
- events: ['Arthralgia', 'Chills', 'Fatigue']  vaccines: ['Pfizer']
- locked rule: argmax strict ordering over all-three denom; modal != tie
- denominator (n): 18   numerator (k): 2
- gold proportion: 0.1111   gold verdict: **insufficient**
- 95% CI: [0.031, 0.328]  (width 0.297, tag moderate)
- sample reports entering the denominator (vaers_id -> relevant levels):
    - 944881: {'Arthralgia': 0, 'Chills': 0, 'Fatigue': 1}
    - 938335: {'Arthralgia': 1, 'Chills': 1, 'Fatigue': 1}
    - 953508: {'Arthralgia': 0, 'Chills': 1, 'Fatigue': 1}
    - 1256881: {'Arthralgia': 0, 'Chills': 0, 'Fatigue': 1}
    - 1114370: {'Arthralgia': 1, 'Chills': 2, 'Fatigue': 0}

## 9. F-V1 (first_choice) -- CHOICE
- claim: "After Pfizer, Arthralgia typically occurs first among Arthralgia, Chills, Fatigue."
- events: ['Arthralgia', 'Chills', 'Fatigue']  vaccines: ['Pfizer']
- locked rule: first_among frac (all-candidates denom); argmax term
- denominator (n): 18   numerator (k): 4
- gold proportion: 0.2222   gold verdict: **supported**
- 95% CI: [0.09, 0.4521]  (width 0.3621, tag low)
- sample reports entering the denominator (vaers_id -> relevant levels):
    - 944881: {'Arthralgia': 0, 'Chills': 0, 'Fatigue': 1}
    - 938335: {'Arthralgia': 1, 'Chills': 1, 'Fatigue': 1}
    - 953508: {'Arthralgia': 0, 'Chills': 1, 'Fatigue': 1}
    - 1256881: {'Arthralgia': 0, 'Chills': 0, 'Fatigue': 1}
    - 1114370: {'Arthralgia': 1, 'Chills': 2, 'Fatigue': 0}

## 10. F-V2 (last_choice) -- CHOICE
- claim: "After Pfizer, Chills typically occurs last among Fatigue, Arthralgia, Chills."
- events: ['Fatigue', 'Arthralgia', 'Chills']  vaccines: ['Pfizer']
- locked rule: last_among frac (all-candidates denom); argmax term
- denominator (n): 18   numerator (k): 5
- gold proportion: 0.2778   gold verdict: **supported**
- 95% CI: [0.125, 0.5087]  (width 0.3837, tag low)
- sample reports entering the denominator (vaers_id -> relevant levels):
    - 944881: {'Fatigue': 1, 'Arthralgia': 0, 'Chills': 0}
    - 938335: {'Fatigue': 1, 'Arthralgia': 1, 'Chills': 1}
    - 953508: {'Fatigue': 1, 'Arthralgia': 0, 'Chills': 1}
    - 1256881: {'Fatigue': 1, 'Arthralgia': 0, 'Chills': 0}
    - 1114370: {'Fatigue': 0, 'Arthralgia': 1, 'Chills': 2}

## 11. F-V3 (first_bool) -- BOOL
- claim: "After Pfizer, Chills is usually the first of Chills, Arthralgia, Fatigue."
- events: ['Chills', 'Arthralgia', 'Fatigue']  vaccines: ['Pfizer']
- locked rule: first_among frac for named event; >0.5
- denominator (n): 18   numerator (k): 4
- gold proportion: 0.1667   gold verdict: **refuted**
- 95% CI: [0.0584, 0.3922]  (width 0.3339, tag low)
- sample reports entering the denominator (vaers_id -> relevant levels):
    - 944881: {'Chills': 0, 'Arthralgia': 0, 'Fatigue': 1}
    - 938335: {'Chills': 1, 'Arthralgia': 1, 'Fatigue': 1}
    - 953508: {'Chills': 1, 'Arthralgia': 0, 'Fatigue': 1}
    - 1256881: {'Chills': 0, 'Arthralgia': 0, 'Fatigue': 1}
    - 1114370: {'Chills': 2, 'Arthralgia': 1, 'Fatigue': 0}

## 12. P-M1 (multi_differ_precedes) -- BOOL
- claim: "The Arthralgia-before-Chills rate differs between Pfizer and Moderna."
- events: ['Arthralgia', 'Chills']  vaccines: ['Pfizer', 'Moderna']
- locked rule: two precedes fracs; |p1-p2|>10pp
- denominator (n): 17   numerator (k): 6
- gold proportion: 0.3529   gold verdict: **supported**
- cohort 2: proportion=0.5714 n=14 k=8
- 95% CI: [-0.4986, 0.1207]  (width 0.6193, tag low)
- sample reports entering the denominator (vaers_id -> relevant levels):
    - 935855: {'Arthralgia': 0, 'Chills': 0}
    - 1137786: {'Arthralgia': 1, 'Chills': 1}
    - 944881: {'Arthralgia': 0, 'Chills': 0}
    - 938335: {'Arthralgia': 1, 'Chills': 1}
    - 1002916: {'Arthralgia': 2, 'Chills': 0}

## 13. P-M2 (multi_dir_precedes) -- CHOICE
- claim: "Arthralgia precedes Chills more often after Moderna than after Pfizer."
- events: ['Arthralgia', 'Chills']  vaccines: ['Moderna', 'Pfizer']
- locked rule: two precedes fracs; names higher cohort
- denominator (n): 14   numerator (k): 6
- gold proportion: 0.5714   gold verdict: **supported**
- cohort 2: proportion=0.5714 n=14 k=8
- 95% CI: [-0.1207, 0.4986]  (width 0.6193, tag low)
- sample reports entering the denominator (vaers_id -> relevant levels):
    - 935855: {'Arthralgia': 0, 'Chills': 0}
    - 1137786: {'Arthralgia': 1, 'Chills': 1}
    - 944881: {'Arthralgia': 0, 'Chills': 0}
    - 938335: {'Arthralgia': 1, 'Chills': 1}
    - 1002916: {'Arthralgia': 2, 'Chills': 0}

## 14. C-M1 (multi_differ_cooccurs) -- BOOL
- claim: "The Abdominal pain upper-Fatigue co-occurrence rate differs between Pfizer and Moderna."
- events: ['Abdominal pain upper', 'Fatigue']  vaccines: ['Pfizer', 'Moderna']
- locked rule: two co-occurs fracs; |p1-p2|>10pp
- denominator (n): 13   numerator (k): 4
- gold proportion: 0.3077   gold verdict: **refuted**
- cohort 2: proportion=0.3636 n=11 k=4
- 95% CI: [-0.3914, 0.2862]  (width 0.6777, tag low)
- sample reports entering the denominator (vaers_id -> relevant levels):
    - 1944016: {'Abdominal pain upper': 3, 'Fatigue': 0}
    - 1587341: {'Abdominal pain upper': 2, 'Fatigue': 0}
    - 1280111: {'Abdominal pain upper': 1, 'Fatigue': 0}
    - 1413308: {'Abdominal pain upper': 1, 'Fatigue': 1}
    - 1149335: {'Abdominal pain upper': 1, 'Fatigue': 1}

## 15. C-M2 (multi_dir_cooccurs) -- CHOICE
- claim: "Abdominal pain upper and Fatigue co-occur more often after Moderna than after Pfizer."
- events: ['Abdominal pain upper', 'Fatigue']  vaccines: ['Moderna', 'Pfizer']
- locked rule: two co-occurs fracs; names higher cohort
- denominator (n): 11   numerator (k): 4
- gold proportion: 0.3636   gold verdict: **supported**
- cohort 2: proportion=0.3636 n=11 k=4
- 95% CI: [-0.2862, 0.3914]  (width 0.6777, tag low)
- sample reports entering the denominator (vaers_id -> relevant levels):
    - 1944016: {'Abdominal pain upper': 3, 'Fatigue': 0}
    - 1587341: {'Abdominal pain upper': 2, 'Fatigue': 0}
    - 1280111: {'Abdominal pain upper': 1, 'Fatigue': 0}
    - 1413308: {'Abdominal pain upper': 1, 'Fatigue': 1}
    - 1149335: {'Abdominal pain upper': 1, 'Fatigue': 1}

## 16. S-M1 (multi_differ_sequence) -- BOOL
- claim: "The Arthralgia → Chills → Fatigue rate differs between Pfizer and Moderna."
- events: ['Arthralgia', 'Chills', 'Fatigue']  vaccines: ['Pfizer', 'Moderna']
- locked rule: two sequence fracs; |p1-p2|>10pp
- denominator (n): 18   numerator (k): 0
- gold proportion: 0.0   gold verdict: **refuted**
- cohort 2: proportion=0.0625 n=16 k=1
- 95% CI: [-0.2833, 0.1207]  (width 0.404, tag low)
- sample reports entering the denominator (vaers_id -> relevant levels):
    - 944881: {'Arthralgia': 0, 'Chills': 0, 'Fatigue': 1}
    - 938335: {'Arthralgia': 1, 'Chills': 1, 'Fatigue': 1}
    - 953508: {'Arthralgia': 0, 'Chills': 1, 'Fatigue': 1}
    - 1256881: {'Arthralgia': 0, 'Chills': 0, 'Fatigue': 1}
    - 1114370: {'Arthralgia': 1, 'Chills': 2, 'Fatigue': 0}

## 17. S-M2 (multi_dir_sequence) -- CHOICE
- claim: "The sequence Arthralgia → Chills → Fatigue is more common after Moderna than Pfizer."
- events: ['Arthralgia', 'Chills', 'Fatigue']  vaccines: ['Moderna', 'Pfizer']
- locked rule: two sequence fracs; names higher cohort
- denominator (n): 16   numerator (k): 0
- gold proportion: 0.0625   gold verdict: **supported**
- cohort 2: proportion=0.0625 n=16 k=1
- 95% CI: [-0.1207, 0.2833]  (width 0.404, tag low)
- sample reports entering the denominator (vaers_id -> relevant levels):
    - 944881: {'Arthralgia': 0, 'Chills': 0, 'Fatigue': 1}
    - 938335: {'Arthralgia': 1, 'Chills': 1, 'Fatigue': 1}
    - 953508: {'Arthralgia': 0, 'Chills': 1, 'Fatigue': 1}
    - 1256881: {'Arthralgia': 0, 'Chills': 0, 'Fatigue': 1}
    - 1114370: {'Arthralgia': 1, 'Chills': 2, 'Fatigue': 0}

## 18. S-M3 (multi_same_modal_order) -- BOOL
- claim: "The typical ordering of Arthralgia, Chills, Fatigue is the same after Pfizer and Moderna."
- events: ['Arthralgia', 'Chills', 'Fatigue']  vaccines: ['Pfizer', 'Moderna']
- locked rule: modal ordering in each cohort; same?
- denominator (n): None   numerator (k): 2
- gold proportion: None   gold verdict: **refuted**
- cohort 2: proportion=0.0625 n=16 k=1
- sample reports entering the denominator (vaers_id -> relevant levels):
    - 944881: {'Arthralgia': 0, 'Chills': 0, 'Fatigue': 1}
    - 938335: {'Arthralgia': 1, 'Chills': 1, 'Fatigue': 1}
    - 953508: {'Arthralgia': 0, 'Chills': 1, 'Fatigue': 1}
    - 1256881: {'Arthralgia': 0, 'Chills': 0, 'Fatigue': 1}
    - 1114370: {'Arthralgia': 1, 'Chills': 2, 'Fatigue': 0}

## 19. F-M1 (multi_same_first) -- BOOL
- claim: "The typical first event among Arthralgia, Chills, Fatigue is the same after Pfizer and Moderna."
- events: ['Arthralgia', 'Chills', 'Fatigue']  vaccines: ['Pfizer', 'Moderna']
- locked rule: modal first event in each cohort; same?
- denominator (n): None   numerator (k): 4
- gold proportion: None   gold verdict: **refuted**
- cohort 2: proportion=0.1875 n=16 k=None
- sample reports entering the denominator (vaers_id -> relevant levels):
    - 944881: {'Arthralgia': 0, 'Chills': 0, 'Fatigue': 1}
    - 938335: {'Arthralgia': 1, 'Chills': 1, 'Fatigue': 1}
    - 953508: {'Arthralgia': 0, 'Chills': 1, 'Fatigue': 1}
    - 1256881: {'Arthralgia': 0, 'Chills': 0, 'Fatigue': 1}
    - 1114370: {'Arthralgia': 1, 'Chills': 2, 'Fatigue': 0}

## 20. F-M3 (multi_dir_first) -- CHOICE
- claim: "Chills is the first event more often after Moderna than Pfizer."
- events: ['Chills', 'Arthralgia', 'Fatigue']  vaccines: ['Moderna', 'Pfizer']
- locked rule: first_among frac of focal event in each cohort; higher cohort
- denominator (n): 16   numerator (k): 3
- gold proportion: 0.1875   gold verdict: **supported**
- cohort 2: proportion=0.1875 n=16 k=3
- 95% CI: [-0.2354, 0.2865]  (width 0.5219, tag low)
- sample reports entering the denominator (vaers_id -> relevant levels):
    - 944881: {'Chills': 0, 'Arthralgia': 0, 'Fatigue': 1}
    - 938335: {'Chills': 1, 'Arthralgia': 1, 'Fatigue': 1}
    - 953508: {'Chills': 1, 'Arthralgia': 0, 'Fatigue': 1}
    - 1256881: {'Chills': 0, 'Arthralgia': 0, 'Fatigue': 1}
    - 1114370: {'Chills': 2, 'Arthralgia': 1, 'Fatigue': 0}

## 21. P-R1 (rep_dir_bool) -- BOOL
- claim: "In report VAERS-916915, Dizziness occurred before Injection site pain."
- events: ['Dizziness', 'Injection site pain']  vaccines: []
- locked rule: per-report relation; before => supported
- denominator (n): None   numerator (k): None
- gold proportion: None   gold verdict: **supported**
- sample reports entering the denominator (vaers_id -> relevant levels):
    - 916915: {'Dizziness': 0, 'Injection site pain': 1}

## 22. C-R1 (rep_sym_bool) -- BOOL
- claim: "In report VAERS-916915, Dizziness and Injection site pain co-occur."
- events: ['Dizziness', 'Injection site pain']  vaccines: []
- locked rule: per-report relation; co_exist => supported
- denominator (n): None   numerator (k): None
- gold proportion: None   gold verdict: **refuted**
- sample reports entering the denominator (vaers_id -> relevant levels):
    - 916915: {'Dizziness': 0, 'Injection site pain': 1}

## 23. S-R1 (rep_seq_bool) -- BOOL
- claim: "In report VAERS-916915, Dizziness, Injection site pain, Asthenia occur in the order Dizziness → Injection site pain → Asthenia."
- events: ['Dizziness', 'Injection site pain', 'Asthenia']  vaccines: []
- locked rule: per-report strict order A<B<C
- denominator (n): None   numerator (k): None
- gold proportion: None   gold verdict: **supported**
- sample reports entering the denominator (vaers_id -> relevant levels):
    - 916915: {'Dizziness': 0, 'Injection site pain': 1, 'Asthenia': 2}

## 24. F-R1 (rep_first_choice) -- CHOICE
- claim: "In report VAERS-916915, Dizziness occurs first among Dizziness, Injection site pain, Asthenia."
- events: ['Dizziness', 'Injection site pain', 'Asthenia']  vaccines: []
- locked rule: per-report first_among single winner
- denominator (n): None   numerator (k): None
- gold proportion: None   gold verdict: **supported**
- sample reports entering the denominator (vaers_id -> relevant levels):
    - 916915: {'Dizziness': 0, 'Injection site pain': 1, 'Asthenia': 2}
