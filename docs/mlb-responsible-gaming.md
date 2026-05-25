# MLB Responsible Gaming Rules

## Banned Language

The following words and phrases are **prohibited** in all generated explanations, reports, and user-facing output:

| Banned Term | Reason |
|-------------|--------|
| guaranteed | Implies certainty of outcome |
| certain | Implies certainty |
| sure thing | Implies certainty |
| lock | Gambling slang implying certainty |
| can't lose | Implies certainty |
| free money | Implies certainty of profit |
| easy money | Implies certainty of profit |
| no-brainer | Implies no risk |
| slam dunk | Implies certainty |
| mortal lock | Implies certainty |

The hallucination guard (`baseball_explainer.py: validate_explanation_against_inputs`) rejects any explanation containing these terms using word-boundary matching.

## Required Disclaimer

Every MLB report includes this disclaimer in the responsible gaming section:

> This is a projection, not a prediction of outcome. Past performance does not predict future results.

Additionally, every report footer includes:

> If you or someone you know has a gambling problem, call 1-800-522-4700 (NCPG) or visit ncpgambling.org.

## Implementation

- `render_baseball_report.py` — Appends the NCPG disclaimer to every report
- `baseball_explainer.py` — `BANNED_GUARANTEE_WORDS` frozenset + `validate_explanation_against_inputs()` function
- `baseball_trace.py` — `no_guarantee_flag` field is always `True` in trace records

## Compliance Checks

The test suite verifies:
- No banned words appear in generated explanations (`test_baseball_explainer.py`)
- Report always includes NCPG contact info (`test_render_baseball_report.py`)
- Trace schema enforces `no_guarantee_flag=True` (`test_baseball_trace.py`)
