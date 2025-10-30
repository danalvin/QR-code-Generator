#!/usr/bin/env python3
"""
Wedding QR Code Generator - Interactive Version

Create a stylish QR code that links to a Google Photos album (or any URL).

Features
- High error correction (for reliability when printed)
- Custom colors (foreground + background)
- Optional centered logo (PNG/JPG with automatic rounding mask)
- Optional caption strip (e.g., names + date)
- Auto-detect dominant colors from logo and apply to QR code
- Export both PNG and PDF

Dependencies
    pip install qrcode[pil] pillow

Usage
    python main.py

Tip: Print at 300 DPI. For an A6 card (105×148 mm), export at ~1240×1748 px or higher.
"""

from __future__ import annotations

import sys
from typing import Tuple, Optional
from pathlib import Path

try:
    import qrcode
    from qrcode.constants import ERROR_CORRECT_H
except Exception as e:
    sys.stderr.write(
        "\nThis script requires the 'qrcode' package with Pillow support.\n"
        "Install with:  pip install qrcode[pil] pillow\n\n"
    )
    raise

from PIL import Image, ImageDraw, ImageFont


def parse_color(c: str) -> Tuple[int, int, int]:
    """Convert hex or rgb string to RGB tuple."""
    c = c.strip()
    if c.startswith("#"):
        c = c[1:]
        if len(c) == 3:
            c = "".join(ch * 2 for ch in c)
        if len(c) != 6:
            raise ValueError("Invalid hex color")
        return tuple(int(c[i:i + 2], 16) for i in (0, 2, 4))
    if "," in c:
        parts = [int(x) for x in c.split(",")]
        if len(parts) != 3:
            raise ValueError("RGB must have 3 comma-separated numbers")
        return tuple(parts)
    raise ValueError("Use #RRGGBB or R,G,B format for colors")


def color_brightness(color: Tuple[int, int, int]) -> float:
    """Calculate perceived brightness of a color (0-255)."""
    r, g, b = color
    return (0.299 * r + 0.587 * g + 0.114 * b)


def color_contrast(color1: Tuple[int, int, int], color2: Tuple[int, int, int]) -> float:
    """Calculate contrast ratio between two colors."""
    l1 = color_brightness(color1) / 255
    l2 = color_brightness(color2) / 255
    if l1 > l2:
        l1, l2 = l2, l1
    return (l2 + 0.05) / (l1 + 0.05)


def get_dominant_colors(img: Image.Image, num_colors: int = 5):
    """Return top N dominant colors from image, including dark colors."""
    small = img.resize((150, 150))
    result = small.convert("RGBA").quantize(colors=num_colors * 2, method=2)
    palette = result.getpalette()
    color_counts = sorted(result.getcolors(), reverse=True)

    colors = []
    for count, idx in color_counts:
        r, g, b = palette[idx * 3:idx * 3 + 3]
        brightness = color_brightness((r, g, b))

        if brightness < 240:
            colors.append((r, g, b))

        if len(colors) >= num_colors:
            break

    return colors[:num_colors]


def select_best_qr_colors(logo_colors: list) -> Tuple[Tuple[int, int, int], Tuple[int, int, int]]:
    """Select the best foreground and background colors from logo colors for QR code."""
    if len(logo_colors) < 1:
        return (0, 0, 0), (255, 255, 255)

    avg_brightness = sum(color_brightness(color) for color in logo_colors) / len(logo_colors)

    if avg_brightness < 80:
        print("Dark logo detected - using black foreground")
        darkest_color = min(logo_colors, key=color_brightness)
        if color_brightness(darkest_color) < 50:
            fg = (0, 0, 0)
        else:
            fg = darkest_color

        if len(logo_colors) > 1:
            bg = max(logo_colors, key=color_brightness)
            if color_brightness(bg) < 200:
                bg = (255, 255, 255)
        else:
            bg = (255, 255, 255)

        return fg, bg

    if len(logo_colors) < 2:
        color = logo_colors[0]
        if color_brightness(color) > 127:
            return (0, 0, 0), color
        else:
            return color, (255, 255, 255)

    best_contrast = 0
    best_fg = logo_colors[0]
    best_bg = logo_colors[1]

    for i, fg_candidate in enumerate(logo_colors):
        for j, bg_candidate in enumerate(logo_colors):
            if i != j:
                contrast = color_contrast(fg_candidate, bg_candidate)
                if contrast > best_contrast:
                    best_contrast = contrast
                    if color_brightness(fg_candidate) < color_brightness(bg_candidate):
                        best_fg, best_bg = fg_candidate, bg_candidate
                    else:
                        best_fg, best_bg = bg_candidate, fg_candidate

    if best_contrast < 3.0:
        print(f"Warning: Low contrast ratio ({best_contrast:.1f}). Consider manual color adjustment.")

    return best_fg, best_bg


def generate_qr(
        url: str,
        size: int = 1200,
        border: int = 4,
        fg: Tuple[int, int, int] = (0, 0, 0),
        bg: Tuple[int, int, int] = (255, 255, 255),
) -> Image.Image:
    """Generate a QR code image with given settings."""
    qr = qrcode.QRCode(
        version=None,
        error_correction=ERROR_CORRECT_H,
        box_size=1,
        border=border,
    )
    qr.add_data(url)
    qr.make(fit=True)

    modules = qr.modules_count + (2 * border)
    box_size = max(1, size // modules)

    qr = qrcode.QRCode(
        version=qr.version,
        error_correction=ERROR_CORRECT_H,
        box_size=box_size,
        border=border,
    )
    qr.add_data(url)
    qr.make(fit=True)

    img = qr.make_image(fill_color=fg, back_color=bg).convert("RGBA")

    if abs(img.width - size) > size * 0.1:
        img = img.resize((size, size), Image.NEAREST)

    return img


def add_logo(base: Image.Image, logo_path: str, scale: float = 0.2, round_ratio: float = 0.25) -> Image.Image:
    """Overlay a centered logo with rounded corners, no background padding."""
    logo = Image.open(logo_path).convert("RGBA")

    target_w = int(base.width * scale)
    aspect = logo.width / logo.height

    if logo.width > target_w:
        new_w = target_w
        new_h = int(target_w / aspect)
        logo = logo.resize((new_w, new_h), Image.LANCZOS)

    new_w, new_h = logo.size

    radius = int(min(new_w, new_h) * round_ratio)
    if radius > 0:
        mask = Image.new("L", (new_w, new_h), 0)
        draw = ImageDraw.Draw(mask)
        draw.rounded_rectangle((0, 0, new_w, new_h), radius=radius, fill=255)
        logo.putalpha(mask)

    cx = (base.width - new_w) // 2
    cy = (base.height - new_h) // 2

    base.paste(logo, (cx, cy), logo)
    return base


def add_caption_strip(
        base: Image.Image,
        caption: str,
        strip_height_ratio: float = 0.18,
        strip_bg: Tuple[int, int, int] = (255, 255, 255),
        text_color: Tuple[int, int, int] = (0, 0, 0),
) -> Image.Image:
    """Add a caption strip below the QR (names/date)."""
    w, h = base.size
    strip_h = int(h * strip_height_ratio)

    canvas = Image.new("RGBA", (w, h + strip_h), (*strip_bg, 255))
    canvas.paste(base, (0, 0))

    draw = ImageDraw.Draw(canvas)

    font_candidates = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/System/Library/Fonts/Supplemental/Avenir.ttc",
        "/System/Library/Fonts/Supplemental/Helvetica.ttc",
    ]
    font = None
    for path in font_candidates:
        try:
            font = ImageFont.truetype(path, size=int(strip_h * 0.38))
            break
        except Exception:
            continue
    if font is None:
        font = ImageFont.load_default()

    text = caption
    tw, th = draw.textbbox((0, 0), text, font=font)[2:]
    tx = (w - tw) // 2
    ty = h + (strip_h - th) // 2
    draw.line([(int(w * 0.12), h), (int(w * 0.88), h)], fill=(0, 0, 0, 40), width=2)
    draw.text((tx, ty), text, fill=text_color, font=font)

    return canvas


def prompt_input(prompt: str, default: Optional[str] = None) -> str:
    """Prompt user for input with optional default value."""
    if default:
        response = input(f"{prompt} [{default}]: ").strip()
        return response if response else default
    else:
        while True:
            response = input(f"{prompt}: ").strip()
            if response:
                return response
            print("This field is required. Please enter a value.")


def prompt_yes_no(prompt: str, default: bool = False) -> bool:
    """Prompt user for yes/no input."""
    default_str = "Y/n" if default else "y/N"
    while True:
        response = input(f"{prompt} [{default_str}]: ").strip().lower()
        if not response:
            return default
        if response in ('y', 'yes'):
            return True
        if response in ('n', 'no'):
            return False
        print("Please enter 'y' or 'n'.")


def main():
    print("=" * 60)
    print("Wedding QR Code Generator - Interactive Mode")
    print("=" * 60)
    print()

    # Get URL
    url = prompt_input("Enter the URL (e.g., Google Photos album link)")
    print()

    # Get output filename
    output = prompt_input("Output filename", "qr_wedding.png")
    print()

    # Get size
    size_str = prompt_input("QR code size in pixels", "1200")
    try:
        size = int(size_str)
    except ValueError:
        print("Invalid size, using default 1200")
        size = 1200
    print()

    # Ask about logo
    use_logo = prompt_yes_no("Do you want to add a logo?", False)
    logo_path = None
    use_logo_colors = False

    if use_logo:
        logo_path = prompt_input("Path to logo image")

        # Validate logo path
        if not Path(logo_path).exists():
            print(f"Warning: Logo file '{logo_path}' not found. Continuing without logo.")
            logo_path = None
        else:
            use_logo_colors = prompt_yes_no("Auto-detect colors from logo?", True)
    print()

    # Get colors (if not using logo colors)
    fg = (34, 34, 34)  # Default #222222
    bg = (255, 255, 255)  # Default white
    strip_bg = (255, 255, 255)
    text_color = (0, 0, 0)

    if not use_logo_colors:
        manual_colors = prompt_yes_no("Do you want to customize colors?", False)
        if manual_colors:
            print()
            fg_str = prompt_input("Foreground color (hex or R,G,B)", "#222222")
            bg_str = prompt_input("Background color (hex or R,G,B)", "#FFFFFF")
            try:
                fg = parse_color(fg_str)
                bg = parse_color(bg_str)
            except Exception as e:
                print(f"Color parsing error: {e}. Using defaults.")
        print()

    # Ask about caption
    use_caption = prompt_yes_no("Do you want to add a caption?", False)
    caption = None

    if use_caption:
        caption = prompt_input("Enter caption text (e.g., 'Nali & Kioni • 18 Aug 2025')")

        if not use_logo_colors:
            custom_caption_colors = prompt_yes_no("Customize caption colors?", False)
            if custom_caption_colors:
                print()
                strip_bg_str = prompt_input("Caption strip background color", "#FFFFFF")
                text_color_str = prompt_input("Caption text color", "#000000")
                try:
                    strip_bg = parse_color(strip_bg_str)
                    text_color = parse_color(text_color_str)
                except Exception as e:
                    print(f"Color parsing error: {e}. Using defaults.")
    print()

    # Process logo colors if requested
    if use_logo_colors and logo_path:
        try:
            print("Analyzing logo colors...")
            logo_img = Image.open(logo_path).convert("RGBA")
            logo_colors = get_dominant_colors(logo_img, 5)
            print(f"Dominant colors: {logo_colors}")

            auto_fg, auto_bg = select_best_qr_colors(logo_colors)
            print(f"Selected QR colors: fg={auto_fg}, bg={auto_bg}")

            fg, bg = auto_fg, auto_bg

            if use_caption:
                strip_bg = max(logo_colors, key=color_brightness)
                text_color = min(logo_colors, key=color_brightness)
                bg = strip_bg
                print(f"Caption colors: strip_bg={strip_bg}, text_color={text_color}")
            print()

        except Exception as e:
            print(f"Warning: Could not extract colors from logo ({e}). Using defaults.")
            print()

    # Generate QR code
    print("Generating QR code...")
    img = generate_qr(url, size=size, border=4, fg=fg, bg=bg)

    if logo_path:
        print("Adding logo...")
        try:
            img = add_logo(img, logo_path, scale=0.20, round_ratio=0.25)
        except Exception as e:
            print(f"Warning: Could not add logo ({e}). Continuing without logo.")

    if caption:
        print("Adding caption...")
        img = add_caption_strip(img, caption, strip_bg=strip_bg, text_color=text_color)

    # Save files
    print(f"Saving PNG to {output}...")
    img.save(output, format='PNG')
    print(f"✓ Saved: {output}")

    pdf_out = output.rsplit('.', 1)[0] + ".pdf"
    print(f"Saving PDF to {pdf_out}...")
    rgb_img = img.convert("RGB")
    rgb_img.save(pdf_out, "PDF", resolution=300.0)
    print(f"✓ Saved PDF: {pdf_out}")

    print()
    print("=" * 60)
    print("Done! Your QR code is ready.")
    print("=" * 60)


if __name__ == '__main__':
    main()