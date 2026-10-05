---
description: |
  Daily commute-focused weather outlook for Chino Hills <-> Rosemead, CA.
  Pulls hourly forecasts from Open-Meteo and publishes a single issue.

on:
  schedule:
    - cron: "0 13 * * *" # 6 AM PDT / 5 AM PST
  workflow_dispatch:

engine:
  id: copilot
  args: ["--allow-all-urls"]

permissions: read-all

network:
  allowed:
    - defaults
    - api.open-meteo.com

safe-outputs:
  create-issue:
    title-prefix: "Commute Weather - "
    labels: [automation, weather]
    close-older-issues: true
    max: 1

tools:
  web-fetch:
  bash: [":*"]

timeout-minutes: 10
---

# Chino Hills <-> Rosemead Commute Weather

Use curl via bash to fetch the hourly forecast for the next 48 hours from Open-Meteo for both ends of the commute.
Use `temperature_unit=fahrenheit`, `wind_speed_unit=kn`, `timezone=America/Los_Angeles` and these hourly variables:
`temperature_2m,apparent_temperature,precipitation_probability,precipitation,cloud_cover,wind_speed_10m,wind_gusts_10m,visibility`.

- Chino Hills: `https://api.open-meteo.com/v1/forecast?latitude=33.99&longitude=-117.73&...`
- Rosemead: `https://api.open-meteo.com/v1/forecast?latitude=34.08&longitude=-118.07&...`

Create one issue containing:

1. A 2-line summary at the top (overall conditions, best departure/return window).
2. A table for today and tomorrow: morning commute (7-9 AM) and evening commute (4-7 PM), both locations, with temp, rain chance, wind and gusts.
3. Daily peak temperature and the hour it occurs, for each location.
4. Flags, only when they apply: heat (>= 95F), gusts >= 15 kt, rain chance >= 30%, visibility < 4828 m (the API returns visibility in metres; 3 mi).
5. A short practical note (e.g. leave before 9 AM, return after 6 PM).

Be terse. No filler. Use only data returned by the API; if a fetch fails, say so instead of guessing.
