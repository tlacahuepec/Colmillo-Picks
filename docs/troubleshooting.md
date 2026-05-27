# Troubleshooting

Common issues and fixes when running Colmillo-Picks locally.

## Rebuild from Scratch

When the container is returning stale or unexpected results, rebuild from the
current branch:

```powershell
# PowerShell (Windows)
docker compose down; docker compose build; docker compose up -d
```

```bash
# Bash (macOS / Linux / WSL)
docker compose down && docker compose build && docker compose up -d
```

## Container Shows Stale Data After Code Change

Docker Compose `up -d` reuses existing images. After switching branches or
pulling new commits, always rebuild:

```powershell
docker compose build
docker compose up -d
```

## Baseball Returns Placeholder Data (Aaron Judge)

The `BaseballModule` falls back to hardcoded placeholder data when:

1. **No collection service** — `_build_baseball_module()` in `sport_module.py`
   failed silently at import time. Check container startup logs for import
   errors.
2. **Schedule not found** — the MLB StatsAPI didn't return games for the
   requested date. Verify the date is correct (today in `YYYY-MM-DD` format).
3. **Game not matched** — team names or abbreviations didn't resolve. Use full
   city names (e.g., "Los Angeles Dodgers") or standard abbreviations ("lad",
   "nyy", "phi").
4. **All providers failed** — lineups, pitchers, and weather all returned
   unavailable. Check network connectivity from inside the container.

### Diagnosing Provider Failures

Check logs for MLB collection warnings:

```powershell
docker logs colmillo-api 2>&1 | Select-String "MLB|baseball|Pitchers|Lineups|Weather|fallback"
```

```bash
docker logs colmillo-api 2>&1 | grep -i "mlb\|baseball\|pitchers\|lineups\|weather\|fallback"
```

## API Returns 429 (Rate Limit)

Default rate limit is 300 requests/hour per API key. The History page makes
multiple calls per render. If hitting limits during development:

```powershell
$env:COLMILLO_RATE_LIMIT_PER_HOUR = "0"  # disables limiter
docker compose up -d
```

Or set in `docker-compose.yml` environment section:

```yaml
environment:
  COLMILLO_RATE_LIMIT_PER_HOUR: "0"
```

## Checking Container Health

```powershell
# Verify API is running
curl http://localhost:8000/healthz

# Check which image is running
docker compose ps

# Tail logs in real time
docker compose logs -f colmillo-api
```

## Network Issues Inside Container

If MLB StatsAPI calls fail from inside the container but work locally:

```powershell
# Test DNS resolution from inside container
docker exec colmillo-api nslookup statsapi.mlb.com

# Test HTTP connectivity
docker exec colmillo-api curl -s https://statsapi.mlb.com/api/v1/schedule?sportId=1
```

## Resetting Everything

Nuclear option — removes containers, images, and volumes:

```powershell
docker compose down -v --rmi local; docker compose build --no-cache; docker compose up -d
```

```bash
docker compose down -v --rmi local && docker compose build --no-cache && docker compose up -d
```
