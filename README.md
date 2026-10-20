# Matt Blair Photography

Portfolio site for landscape, aerial and night-sky photography. A single static page (`site/index.html`) served by a small Flask app on Railway.

## Layout
- `site/index.html` is the whole page: styles, markup and script.
- `site/photos.json` lists every photo: collection, region, aspect ratio, and the camera data read from the original files. Edit it to add titles (`cap`) or reorder photos.
- `site/p/` holds two sizes of each photo: `<id>-s.jpg` (760 px, gallery) and `<id>-l.jpg` (1600 px, lightbox and hero).
- `app.py` serves `site/`, a `/healthz` check for Railway, and `/api/contact` for the enquiry form.

## Adding photos
Export JPEGs (full size is fine; iPhone HEIC files need exporting as JPEG first), then:
```bash
pip install pillow
python tools/add_photos.py "Okanagan" ~/Pictures/export/*.jpg
python tools/add_photos.py "Utah" watchman.jpg --title "The Watchman at last light"
```
The script makes the two web sizes in `site/p/`, reads camera, lens, settings, date and GPS from each file, and adds the photos to the front of that collection in `site/photos.json`. Collections with filters on the page: Utah, Nevada, Okanagan, Vancouver Island, Canadian Rockies, Maui, Drone Landscapes, Astrophotography, Wildlife.

Commit and push to `main`; Railway redeploys in about a minute.

To remove a photo, delete its entry from `site/photos.json` and its two files from `site/p/`. To retitle one, set its `cap` field.

## Run locally
```bash
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
python app.py   # http://localhost:5000
```

## Deploy on Railway
New Project → Deploy from GitHub repo → this repo. Nixpacks detects Python and uses `railway.json`.

### Contact form
The form emails enquiries once these variables are set on the Railway service (until then it asks visitors to phone instead):

| Variable | Example |
|---|---|
| `SMTP_HOST` | `smtp.gmail.com` |
| `SMTP_PORT` | `587` (default) |
| `SMTP_USER` | the sending address |
| `SMTP_PASS` | an app password, not your normal password |
| `CONTACT_TO` | where enquiries should arrive |

### Custom domain
Railway service → Settings → Networking → Custom Domain → `mattblairphotography.ca`, then add the CNAME record Railway shows at your domain registrar.
