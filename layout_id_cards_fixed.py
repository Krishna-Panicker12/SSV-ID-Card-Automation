
"""
Layout the ID card.png images into a printable PDF grid with specified page dimensions and card sizes.
"""
import argparse
import os
from pathlib import Path
from reportlab.lib.pagesizes import letter, A4, landscape, portrait
from reportlab.pdfgen import canvas
from reportlab.lib.units import inch
from reportlab.lib.utils import ImageReader
from PIL import Image

IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".webp", ".tif", ".tiff"}

def parse_args():
    p = argparse.ArgumentParser(description="Layout ID card images into printable PDFs.")
    p.add_argument("--input", required=True, help="Folder of ID card images")
    p.add_argument("--output", required=True, help="Output PDF path")
    p.add_argument("--page", choices=["letter", "a4", "custom"], default="letter", help="Page size")
    p.add_argument("--landscape", action="store_true", help="Rotate page to landscape")

    # If page=custom, these are in centimeters
    p.add_argument("--page-width", type=float, help="Custom page width in cm (required if --page custom)")
    p.add_argument("--page-height", type=float, help="Custom page height in cm (required if --page custom)")

    # Card size in centimeters (CR80 by default)
    p.add_argument("--card-width", type=float, default=8.57, help="Card width in cm (default 8.57)")
    p.add_argument("--card-height", type=float, default=5.40, help="Card height in cm (default 5.40)")

    # Margins/spacing in centimeters
    p.add_argument("--margin", type=float, default=0.64, help="Page margin on all sides in cm (default 0.64 ≈ 0.25\")")
    p.add_argument("--spacing", type=float, default=0.32, help="Gap between cards in cm (default 0.32 ≈ 1/8\")")

    grid = p.add_mutually_exclusive_group()
    grid.add_argument("--auto-grid", action="store_true", help="Automatically compute max rows/cols that fit")
    grid.add_argument("--rows", type=int, help="Rows per page")
    p.add_argument("--cols", type=int, help="Columns per page (required if --rows is set)")

    p.add_argument("--order", choices=["row-major", "col-major"], default="row-major",
                   help="Fill order across the grid")

    p.add_argument("--fit", choices=["contain", "cover", "stretch"], default="contain",
                   help="contain=no crop, cover=crop to fill, stretch=distort")

    p.add_argument("--include-filenames", action="store_true",
                   help="Stamp small filenames below each card (for QA)")

    return p.parse_args()

def cm_to_points(x_cm: float) -> float:
    return (x_cm / 2.54) * inch

def get_page_size(args):
    if args.page == "letter":
        ps = letter
    elif args.page == "a4":
        ps = A4
    else:
        if args.page_width is None or args.page_height is None:
            raise SystemExit("--page custom requires --page-width and --page-height (in cm).")
        ps = (cm_to_points(args.page_width), cm_to_points(args.page_height))
    return landscape(ps) if args.landscape else portrait(ps)

def list_images(folder):
    paths = [p for p in sorted(Path(folder).iterdir())
             if p.is_file() and p.suffix.lower() in IMAGE_EXTS]
    if not paths:
        raise SystemExit(f"No image files found in {folder}")
    return paths

def compute_auto_grid(page_w, page_h, margin_pts, card_w_pts, card_h_pts, spacing_pts):
    usable_w = page_w - 2 * margin_pts
    usable_h = page_h - 2 * margin_pts

    def max_fit(space, item):
        n = 0
        while True:
            needed = n * item + max(0, n - 1) * spacing_pts
            if needed <= space + 1e-6:
                n += 1
                continue
            return max(1, n - 1)

    cols = max_fit(usable_w, card_w_pts)
    rows = max_fit(usable_h, card_h_pts)
    return rows, cols

def place_image(c, img_path, x, y, box_w, box_h, fit_mode):
    try:
        img = Image.open(img_path)
    except Exception as e:
        print(f"Warning: failed to open {img_path}: {e}")
        return

    iw, ih = img.size
    if iw == 0 or ih == 0:
        return

    if fit_mode == "stretch":
        c.drawImage(ImageReader(img), x, y, width=box_w, height=box_h, preserveAspectRatio=False, mask='auto')
        return

    box_ar = box_w / box_h
    img_ar = iw / ih

    if fit_mode == "contain":
        if img_ar > box_ar:
            draw_w = box_w
            draw_h = box_w / img_ar
        else:
            draw_h = box_h
            draw_w = box_h * img_ar
        x_off = x + (box_w - draw_w) / 2.0
        y_off = y + (box_h - draw_h) / 2.0
        c.drawImage(ImageReader(img), x_off, y_off, width=draw_w, height=draw_h, preserveAspectRatio=True, mask='auto')
    else:  # cover (crop to fill)
        if img_ar > box_ar:
            draw_h = box_h
            draw_w = box_h * img_ar
        else:
            draw_w = box_w
            draw_h = box_w / img_ar
        x_off = x + (box_w - draw_w) / 2.0
        y_off = y + (box_h - draw_h) / 2.0

        # Proper clipping path
        path = c.beginPath()
        path.rect(x, y, box_w, box_h)
        c.saveState()
        c.clipPath(path, stroke=0, fill=0)
        c.drawImage(ImageReader(img), x_off, y_off, width=draw_w, height=draw_h, preserveAspectRatio=True, mask='auto')
        c.restoreState()

def layout_pdf(args):
    page_w, page_h = get_page_size(args)
    margin_pts = cm_to_points(args.margin)
    spacing_pts = cm_to_points(args.spacing)
    card_w_pts = cm_to_points(args.card_width)
    card_h_pts = cm_to_points(args.card_height)

    if args.auto_grid:
        rows, cols = compute_auto_grid(page_w, page_h, margin_pts, card_w_pts, card_h_pts, spacing_pts)
    else:
        if args.rows is None or args.cols is None:
            raise SystemExit("Provide --rows and --cols, or use --auto-grid.")
        rows, cols = args.rows, args.cols

    usable_w = page_w - 2 * margin_pts
    usable_h = page_h - 2 * margin_pts

    total_grid_w = cols * card_w_pts + (cols - 1) * spacing_pts
    total_grid_h = rows * card_h_pts + (rows - 1) * spacing_pts

    if total_grid_w > usable_w + 1e-6 or total_grid_h > usable_h + 1e-6:
        print("Warning: grid too large with current margins; switching to auto-fit.")
        rows, cols = compute_auto_grid(page_w, page_h, margin_pts, card_w_pts, card_h_pts, spacing_pts)
        total_grid_w = cols * card_w_pts + (cols - 1) * spacing_pts
        total_grid_h = rows * card_h_pts + (rows - 1) * spacing_pts

    start_x = (page_w - total_grid_w) / 2.0
    start_y_top = page_h - ((page_h - total_grid_h) / 2.0)  # top of grid

    images = list_images(args.input)
    c = canvas.Canvas(args.output, pagesize=(page_w, page_h))

    if args.include_filenames:
        try:
            c.setFont("Helvetica", 6)
        except Exception:
            pass

    per_page = rows * cols
    n = len(images)
    page_index = 0

    while page_index * per_page < n:
        for r in range(rows):
            y = start_y_top - r * (card_h_pts + spacing_pts) - card_h_pts
            for col in range(cols):
                x = start_x + col * (card_w_pts + spacing_pts)
                cell_index = r * cols + col if args.order == "row-major" else col * rows + r
                img_index = page_index * per_page + cell_index
                if img_index >= n:
                    continue

                place_image(c, images[img_index], x, y, card_w_pts, card_h_pts, args.fit)

                if args.include_filenames:
                    name = images[img_index].stem[:40]
                    c.drawCentredString(x + card_w_pts / 2.0, y - 6, name)
        page_index += 1
        c.showPage()

    c.setAuthor("layout_id_cards_fixed.py")
    c.setTitle("Laid out ID cards")
    c.save()

def main():
    args = parse_args()
    layout_pdf(args)

if __name__ == "__main__":
    main()
