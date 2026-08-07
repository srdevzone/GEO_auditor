# How the score is calculated

The headline number is **not** an LLM guess. The LLM proposes findings and measures
presence; the score itself is deterministic arithmetic that the report exposes line by
line.

## Dimensions and weights

| Dimension | Weight | What it measures | How it's scored |
|---|---|---|---|
| AI presence | 35% | Is the domain actually inside AI answers for the questions customers ask | **Measured**: fraction of probe queries where the domain surfaced |
| Answerability | 30% | Can AI engines lift crisp, quotable answers out of the content | Start 100, subtract points per finding |
| Entity & foundation | 20% | Does the AI know who you are and can it read you | Start 100, subtract points per finding |
| Authority & trust | 15% | Trust signals: dates, authorship, primary sources, brand recognition | Start 100, subtract points per finding |

Weights are the *product decision*: presence is the thing nobody else measures directly,
so it gets the biggest slice; answerability is the mechanism by which content becomes
quotable; entity and authority are the foundations.

## Finding severity → fixed deduction

| Severity | Points off that dimension |
|---|---|
| critical | 25 |
| major | 12 |
| minor | 5 |
| info | 1 |

The LLM chooses the severity; the points table is code, not judgment. A dimension can't
go below 0.

## Overall score

```
overall = (Σ dimension_score × weight) / (Σ weight of non-skipped dimensions)
```

A dimension is **skipped** only when it couldn't be measured at all (e.g. every presence
probe failed) — its weight is redistributed across the others and the skip reason is
shown. This is why the total is always out of 100 even when presence couldn't run.

## Worked example

Say the audit measures:

- presence: **2 of 5** queries surfaced the domain → score = 40
- answerability: one major finding (−12) → 88
- entity: no findings → 100
- authority: one critical finding (−25) → 75

```
overall = (40×0.35 + 88×0.30 + 100×0.20 + 75×0.15) / 1.0
        = (14.0 + 26.4 + 20.0 + 11.25)
        = 71.65  → 71.7
```

The report's "Score breakdown" table shows exactly these rows: weight, score, weighted
contribution, the measurement line, and a collapsible list of every deduction.

## Grades

| Score | Grade | Meaning |
|---|---|---|
| 85+ | A | Strong AI visibility — showing up in AI answers |
| 70–84 | B | Good — visible in places, missing in others |
| 55–69 | C | Mediocre — findable but rarely quoted |
| 40–54 | D | Weak — mostly invisible inside AI answers |
| <40 | F | Invisible — AI engines can't find or quote the site |

## Fix priority (impact × effort)

Every finding carries `impact` (1–5, how much fixing it raises AI visibility) and
`effort` (1–5, how hard for a small business owner). Priority is:

```
priority = impact / effort
```

Sorted descending (ties broken by impact). Then bucketed for the Monday-morning owner:

| Bucket | Rule |
|---|---|
| **Do this week** | impact ≥ 4 and effort ≤ 2 |
| **Do this month** | priority ≥ 1.5 |
| **Plan next quarter** | everything else |

## Why this design

- **Traceable** — every point on the scale maps to a measured query or an evidence-backed
  finding. There is no "magic 73/100".
- **Deterministic** — re-running the scorer on the same findings always gives the same
  number, which is testable (see `backend/tests/test_scoring.py`).
- **Honest about gaps** — unmeasurable dimensions are skipped with a reason, never
  silently guessed at a default.
