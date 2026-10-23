"""Add photos to the site.

    python tools/add_photos.py "Okanagan" ~/Pictures/export/*.jpg
    python tools/add_photos.py "Utah" sunset.jpg --title "The Watchman at last light"

For each JPEG this makes the three web sizes in site/p/ and adds an entry to
site/photos.json, with camera, lens, settings, date and GPS read from the
file's EXIF. New photos go first in their collection. Re-adding a file that
is already on the site is skipped.

Needs Pillow:  pip install pillow
"""
import argparse
import hashlib
import io
import json
import os
import sys

from PIL import Image, ImageCms, ImageOps
from PIL.ExifTags import GPSTAGS, TAGS

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SITE = os.path.join(ROOT, "site")
PHOTOS = os.path.join(SITE, "photos.json")
# Long-edge sizes: s for the gallery grid, l and x for the slideshow and full-screen view.
SIZES = (("s", (760, 1000), 78), ("l", (1600, 1600), 82), ("x", (2880, 2880), 84))
SRGB = ImageCms.ImageCmsProfile(ImageCms.createProfile("sRGB"))
Image.MAX_IMAGE_PIXELS = None

# Collections the page already has filters for. A new name works too, but
# only shows under "All work" until the page gets a filter chip for it.
REGION = {"Utah": "sw", "Nevada": "sw", "Okanagan": "ca", "Vancouver Island": "ca",
          "Canadian Rockies": "ca", "Maui": "hi"}
SUBJECTS = {"Drone Landscapes", "Astrophotography", "Wildlife"}
DRONES = {"FC8482": "DJI Mini 4 Pro", "FC3682": "DJI Mini 3"}
CAMERAS = {"ILCE-6300": "Sony a6300", "NIKON D3500": "Nikon D3500", "NIKON D80": "Nikon D80"}


def num(v):
    try:
        return float(v)
    except (TypeError, ValueError, ZeroDivisionError):
        return None


def read_exif(im):
    ex = im.getexif()
    base = {TAGS.get(k, k): v for k, v in ex.items()}
    sub = {TAGS.get(k, k): v for k, v in ex.get_ifd(0x8769).items()}
    gps = {GPSTAGS.get(k, k): v for k, v in ex.get_ifd(0x8825).items()}
    clean = lambda v: str(v or "").strip("\x00 ")
    e = {"model": clean(base.get("Model")), "lens": clean(sub.get("LensModel")),
         "date": clean(sub.get("DateTimeOriginal") or base.get("DateTime"))[:10].replace(":", "-"),
         "fl": num(sub.get("FocalLength")), "fl35": sub.get("FocalLengthIn35mmFilm"),
         "f": num(sub.get("FNumber")), "t": num(sub.get("ExposureTime")),
         "iso": sub.get("ISOSpeedRatings") or sub.get("PhotographicSensitivity")}
    if gps.get("GPSLatitude") and gps.get("GPSLongitude"):
        def deg(v, ref):
            d = float(v[0]) + float(v[1]) / 60 + float(v[2]) / 3600
            return -d if ref in ("S", "W") else d
        e["lat"] = deg(gps["GPSLatitude"], gps.get("GPSLatitudeRef", "N"))
        e["lon"] = deg(gps["GPSLongitude"], gps.get("GPSLongitudeRef", "E"))
        e["alt"] = num(gps.get("GPSAltitude"))
    return e


def region_for(col, e):
    if col in REGION:
        return REGION[col]
    if "lat" in e:
        if e["lat"] < 23:
            return "hi"
        return "sw" if e["lat"] < 42 and e["lon"] < -100 else "ca"
    return None


def to_srgb(src, im):
    """Convert Adobe RGB and other wide-gamut files so colours show correctly in browsers."""
    icc = src.info.get("icc_profile")
    if not icc:
        return im
    prof = ImageCms.ImageCmsProfile(io.BytesIO(icc))
    if "sRGB" in ImageCms.getProfileDescription(prof):
        return im
    return ImageCms.profileToProfile(im, prof, SRGB, renderingIntent=0, outputMode="RGB")


def entry(pid, col, im, e, title, widths):
    aerial = e["model"] in DRONES or col == "Drone Landscapes"
    t = e["t"]
    shutter = (f"1/{round(1 / t)} s" if t < 1 else f"{t:g} s") if t else None
    focal = None
    if e["fl"]:
        focal = f"{e['fl']:g} mm" + (f" ({e['fl35']} mm eq)" if e["fl35"] and aerial else "")
    settings = " · ".join(x for x in [focal, f"f/{e['f']:g}" if e["f"] else None, shutter,
                                       f"ISO {e['iso']}" if e["iso"] else None] if x)
    rec = {"id": pid, "col": col, "r": region_for(col, e), "a": 1 if aerial else 0,
           "ar": round(im.width / im.height, 4), "w": widths,
           "cam": DRONES.get(e["model"]) or CAMERAS.get(e["model"]) or e["model"],
           "lens": e["lens"], "set": settings, "date": e["date"],
           "gps": [round(e["lat"], 4), round(e["lon"], 4)] if "lat" in e else None,
           "alt": round(e["alt"]) if e.get("alt") else None, "cap": title}
    return {k: v for k, v in rec.items() if v not in (None, "")}


def main():
    ap = argparse.ArgumentParser(description="Add photos to the site.")
    ap.add_argument("collection", help='e.g. "Okanagan", "Utah", "Drone Landscapes"')
    ap.add_argument("files", nargs="+", help="JPEG files to add")
    ap.add_argument("--title", help="caption for the photo (only with a single file)")
    args = ap.parse_args()
    if args.title and len(args.files) > 1:
        sys.exit("--title only works when adding one photo at a time")

    photos = json.load(open(PHOTOS))
    have = {p["id"] for p in photos}
    known = {p["col"] for p in photos}
    if args.collection not in known:
        print(f'Note: "{args.collection}" is a new collection; it shows under "All work" '
              "until the page gets a filter for it.")

    added = []
    for path in args.files:
        with open(path, "rb") as fh:
            pid = hashlib.sha1(fh.read()).hexdigest()[:12]
        if pid in have:
            print(f"skip  {path} (already on the site)")
            continue
        try:
            src = Image.open(path)
            e = read_exif(src)
            im = to_srgb(src, ImageOps.exif_transpose(src).convert("RGB"))
        except OSError as err:
            print(f"skip  {path} ({err}; export it as a JPEG)")
            continue
        widths = []
        for suffix, box, q in SIZES:
            out = im.copy()
            out.thumbnail(box, Image.LANCZOS)
            out.save(os.path.join(SITE, "p", f"{pid}-{suffix}.jpg"), quality=q, optimize=True,
                     progressive=True, icc_profile=SRGB.tobytes())
            widths.append(out.width)
        rec = entry(pid, args.collection, im, e, args.title, widths)
        added.append(rec)
        have.add(pid)
        print(f"added {path} -> {pid} ({rec.get('cam', 'unknown camera')}, {rec.get('date', 'no date')})")

    if not added:
        return
    # Newest first within the collection; a new collection goes at the end.
    first = next((i for i, p in enumerate(photos) if p["col"] == args.collection), len(photos))
    photos[first:first] = added
    with open(PHOTOS, "w") as fh:
        json.dump(photos, fh, separators=(",", ":"), ensure_ascii=False)
    print(f"{len(added)} photo(s) added to {args.collection}; {len(photos)} on the site.")


if __name__ == "__main__":
    main()
