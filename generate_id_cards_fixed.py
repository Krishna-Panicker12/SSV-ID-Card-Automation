
"""
Generate ID cards pngs from a CSV file containing the name, year and cabin number of the campers.
"""

import argparse
import os
import re
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
import pandas as pd

HERE = Path(__file__).resolve().parent

def load_font(ttf_path: Path, size: int):
    try:
        return ImageFont.truetype(str(ttf_path), size)
    except Exception:
        # Fallback to a common built-in if Alice isn't found
        try:
            return ImageFont.truetype("DejaVuSans.ttf", size)
        except Exception:
            return ImageFont.load_default()

def draw_bold_text(draw, position, text, font, fill="black", offset=1):
    x, y = position
    for dx in (-offset, 0, offset):
        for dy in (-offset, 0, offset):
            draw.text((x + dx, y + dy), text, font=font, fill=fill)

def draw_bold_centered(draw, text, y, font, image_width, fill="black"):
    bbox = draw.textbbox((0, 0), text, font=font)
    text_width = bbox[2] - bbox[0]
    x = int((image_width - text_width) // 2)
    draw_bold_text(draw, (x, int(y)), text, font, fill=fill)

def shrink_to_fit(draw, text, font_path: Path, max_width: int, start_size: int, min_size: int = 22):
    size = start_size
    while size >= min_size:
        f = load_font(font_path, size)
        w = draw.textbbox((0, 0), text, font=f)[2]
        if w <= max_width:
            return f
        size -= 2
    return load_font(font_path, min_size)

def safe_filename(s: str) -> str:
    # Keep letters, digits, underscores, hyphens; replace spaces with underscores
    s = s.replace(" ", "_")
    return re.sub(r"[^\w\-\.]", "", s)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--csv", default=str(HERE / "testNames.csv"))
    ap.add_argument("--template", default=str(HERE / "ssv2025_ID_card_updated.png"))
    ap.add_argument("--font", default=str(HERE / "Alice-Regular.ttf"))
    ap.add_argument("--outdir", default=str(HERE / "test_ID"))
    ap.add_argument("--name_y", type=float, default=289)
    ap.add_argument("--year_y", type=float, default=397)
    ap.add_argument("--cabin_y", type=float, default=477)
    ap.add_argument("--name_size", type=int, default=70)
    ap.add_argument("--year_size", type=int, default=50)
    ap.add_argument("--cabin_size", type=int, default=50)
    args = ap.parse_args()

    df = pd.read_csv(args.csv)
    template = Image.open(args.template).convert("RGBA")
    font_path = Path(args.font)

    Path(args.outdir).mkdir(parents=True, exist_ok=True)

    made = 0
    for _, row in df.iterrows():
        name = str(row["Name"])
        year = str(row["Year"])
        cabin = str(row["Cabin"])

        card = template.copy()
        draw = ImageDraw.Draw(card)
        W = card.width

        # Auto shrink long name to fit within 90% of card width
        max_name_width = int(W * 0.9)
        name_font = shrink_to_fit(draw, name, font_path, max_name_width, args.name_size)
        year_font = load_font(font_path, args.year_size)
        cabin_font = load_font(font_path, args.cabin_size)

        draw_bold_centered(draw, name, y=args.name_y, font=name_font, image_width=W)
        draw_bold_centered(draw, year, y=args.year_y, font=year_font, image_width=W)
        draw_bold_centered(draw, f"Cabin: {cabin}", y=args.cabin_y, font=cabin_font, image_width=W)

        out = Path(args.outdir) / f"{safe_filename(name)}_ID.png"
        card.save(out)
        made += 1
        print(f"✓ Wrote {out.name}")

    print(f"Done. Generated {made} card(s) into {args.outdir}")

if __name__ == "__main__":
    main()
