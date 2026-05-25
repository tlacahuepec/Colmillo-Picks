# MLB Markets Reference

## Supported Markets (v1)

| Market Key | Display Name | Player Type | Line Type | Settlement |
|------------|-------------|-------------|-----------|------------|
| `hits` | Hits | Batter | Over/Under | Actual vs. line |
| `total_bases` | Total Bases | Batter | Over/Under | Actual vs. line |
| `runs` | Runs Scored | Batter | Over/Under | Actual vs. line |
| `rbi` | RBIs | Batter | Over/Under | Actual vs. line |
| `home_runs` | Home Runs | Batter | Over/Under | Actual vs. line |
| `strikeouts` | Strikeouts | Batter | Over/Under | Actual vs. line |
| `walks` | Walks | Batter | Over/Under | Actual vs. line |
| `pitcher_outs` | Pitcher Outs | Pitcher | Over/Under | Actual vs. line |

## Settlement Rules

### Over/Under Props

- **Win**: Actual > line (for over) or Actual < line (for under)
- **Loss**: Actual < line (for over) or Actual > line (for under)
- **Push**: Actual == line (whole-number lines only; half-lines cannot push)

### Moneyline

- **Win**: Selected team wins the game
- **Loss**: Selected team loses

### Run Line

- **Win**: Team margin + spread > 0
- **Loss**: Team margin + spread < 0
- **Push**: Team margin + spread == 0

### Void Conditions

A pick is voided (refunded) when:

| Condition | Rule |
|-----------|------|
| Rain-shortened game | Fewer than 5 complete innings |
| Suspended game | Game not completed on scheduled date |
| Pitcher pulled early | Pitcher prop voided if designated as early exit |
| Missing data | Player actuals not available in box score |

Rain-shortened games with 5+ complete innings are graded normally.

## Market Mapping

Internal market keys map directly to box score stat columns. No translation layer is needed for v1 providers.
