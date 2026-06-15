# Hosting the dashboard on Cloudflare Pages (auto-updating link)

Cloudflare Pages only *serves* the finished `dashboard.html`. The model is Python (scipy),
which Pages can't run — so the rebuild happens in **GitHub Actions** (free), which then
deploys the fresh file to Cloudflare Pages. Result: a shareable link that refreshes itself
each matchday.

```
ESPN data ──> GitHub Actions (runs build_site.sh on a schedule) ──> Cloudflare Pages ──> https://<project>.pages.dev
```

## One-time setup

1. **Push this folder to a GitHub repo.** `.gitignore` already excludes the huge
   Transfermarkt zip and the secret key files. The *derived* CSVs
   (`club_rates.csv`, `ref_club_rates.csv`, `calibration.json`, `team_matches.csv`,
   `referee_matches.csv`, `data/raw/`) are committed, so the build is incremental and
   doesn't need the 200 MB dump.
2. **Create a Cloudflare Pages project** named `wc26-dashboard` (Direct Upload / "use a
   build action"). Note your **Account ID**.
3. **Create a Cloudflare API token** (My Profile → API Tokens → "Edit Cloudflare Pages").
4. **Add two GitHub repo secrets** (Settings → Secrets → Actions):
   - `CLOUDFLARE_API_TOKEN`
   - `CLOUDFLARE_ACCOUNT_ID`
5. Done. The workflow (`.github/workflows/deploy.yml`) runs **every 6 hours**, on **push**,
   and via the manual **Run workflow** button. Your link: `https://wc26-dashboard.pages.dev`.

## What the build does (`build_site.sh`)

Pulls new ESPN matches + Elo/results, runs `harvest → build_referees → build_tempo →
export_dashboard`, then stages `public/index.html` for Pages. (It skips the
Transfermarkt-zip steps; re-run `build_club.py` / `build_ref_club.py` locally and commit
their CSV outputs only when you refresh that dump.)

## Updating "whenever"

- **Automatic:** every 6 hours (edit the `cron` in `deploy.yml` to taste).
- **On demand:** GitHub → Actions → "Build & deploy" → **Run workflow**.
- **On code change:** any push to `main` rebuilds and redeploys.

## Not included yet (needs paid keys)

The **news / availability** layer (read team news on update) needs a search API + an LLM
key. When ready, add them as GitHub secrets and a `news_scan` step before
`export_dashboard` — the data auto-update above is fully free without it.

## Note
I can prepare all of this, but **deploying needs your GitHub + Cloudflare login**, so the
one-time setup above is yours to run (same as you'd do for spunt.mt).
