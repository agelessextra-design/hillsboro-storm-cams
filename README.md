# Hillsboro Road Cameras - live storm tool

A web page plus a small collector that runs on GitHub every 5 minutes during a storm window you schedule.

## How it works
- `schedule.json` lists storm windows (`start`, `hours`, `label`). The page edits it.
- `.github/workflows/collect.yml` wakes about every 5 minutes. `gate.py` checks the schedule; outside a window it exits in seconds.
- Inside a window `collect.py` pulls the 30 TripCheck camera images, road-weather stations, KHIO observations, NWS alerts and the radar loop, keeps the last 3 hours per camera, and publishes everything to the `gh-pages` branch.
- The page (`web/index.html`, published as `index.html`) reads `feed.json` and refreshes itself every 5 minutes.

## Setup (one time)
1. Create a PUBLIC repository (Pages on a free account needs public). Push this folder to `main`.
2. Settings > Pages > Source: Deploy from a branch > `gh-pages` / root. (The branch appears after the first run: Actions > Collect > Run workflow.)
3. Make a fine-grained personal access token: Settings > Developer settings > Fine-grained tokens. Repository access: only this repo. Permissions: Contents = Read and write, Actions = Read and write. Paste it in the page's Schedule tab on your own computer. It is stored in that browser only.

## Using it
- Schedule tab > Right now, or a set time (Pacific), 1-168 hours, Start collecting.
- Stop now ends a running window. Cancel removes an upcoming one.
- "One snapshot an hour" keeps a light picture when no window is open.

## Things to know
- GitHub's 5-minute timer can run several minutes late at busy times. Treat it as "about 5 minutes".
- GitHub turns off scheduled workflows in a public repo after 60 days with no repo activity. Saving a schedule from the page counts as activity. If the timer stops, re-enable it in the Actions tab.
- Radar shows reflectivity only. It cannot tell rain from snow.
- Camera images belong to ODOT and partner agencies. ODOT's published pages state no limits on automated use. Its official route is the free TripCheck Data API (key from apiportal.odot.state.or.us); consider registering. This tool makes about 360 image requests per hour while a window is open.
- The page is public. It shows only public camera images and weather.
