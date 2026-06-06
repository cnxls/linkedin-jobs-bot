"""Generate bot assets: welcome banner and profile picture."""

from PIL import Image, ImageDraw, ImageFont
from pathlib import Path

ASSETS = Path(__file__).parent / "assets"
ASSETS.mkdir(exist_ok=True)

BEIGE = (235, 225, 210)
CREAM = (245, 238, 228)
BROWN = (62, 44, 32)
BROWN_MID = (120, 90, 68)
BROWN_LIGHT = (180, 158, 138)
ACCENT = (200, 178, 155)


def get_font(size):
    for name in ["segoeui.ttf", "arial.ttf", "DejaVuSans.ttf"]:
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            continue
    return ImageFont.load_default()


def get_bold_font(size):
    for name in ["segoeuib.ttf", "arialbd.ttf", "DejaVuSans-Bold.ttf"]:
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            continue
    return get_font(size)


def generate_welcome():
    W, H = 800, 400
    img = Image.new("RGB", (W, H), CREAM)
    draw = ImageDraw.Draw(img)

    draw.rectangle([0, 0, W, 6], fill=BROWN)

    draw.line([(60, 340), (W - 60, 340)], fill=ACCENT, width=1)

    title_font = get_bold_font(38)
    body_font = get_font(20)
    small_font = get_font(16)

    draw.text((60, 40), "Jobs Radar", fill=BROWN, font=title_font)

    draw.line([(60, 95), (180, 95)], fill=BROWN_MID, width=2)

    draw.text((60, 115), "Your LinkedIn job search assistant.", fill=BROWN_MID, font=body_font)

    features = [
        "Search by keywords",
        "Browse offers one by one",
        "Scheduled auto-checks",
        "Smart deduplication",
    ]
    for i, feat in enumerate(features):
        y = 175 + i * 36
        draw.text((80, y), "—", fill=BROWN_LIGHT, font=body_font)
        draw.text((110, y), feat, fill=BROWN, font=body_font)

    draw.text((60, 355), "tap below to start", fill=BROWN_LIGHT, font=small_font)

    cx, cy = 640, 180
    for i in range(3):
        r = 30 + i * 28
        draw.arc([cx - r, cy - r, cx + r, cy + r], 210, 330,
                 fill=BROWN if i == 0 else BROWN_MID if i == 1 else BROWN_LIGHT, width=3)
    draw.ellipse([cx - 5, cy - 5, cx + 5, cy + 5], fill=BROWN)

    img.save(ASSETS / "welcome.png", "PNG")
    print(f"Saved welcome.png")


def generate_pfp():
    S = 512
    img = Image.new("RGB", (S, S), BEIGE)
    draw = ImageDraw.Draw(img)

    cx, cy = S // 2, S // 2 - 20

    for i in range(3):
        r = 55 + i * 45
        w = 5 - i
        color = BROWN if i == 0 else BROWN_MID if i == 1 else BROWN_LIGHT
        draw.arc([cx - r, cy - r, cx + r, cy + r], 210, 330, fill=color, width=w)

    draw.ellipse([cx - 10, cy - 10, cx + 10, cy + 10], fill=BROWN)

    font = get_bold_font(48)
    label = "JR"
    bbox = draw.textbbox((0, 0), label, font=font)
    tw = bbox[2] - bbox[0]
    draw.text((cx - tw // 2, cy + 120), label, fill=BROWN, font=font)

    img.save(ASSETS / "pfp.png", "PNG")
    print(f"Saved pfp.png")


if __name__ == "__main__":
    generate_welcome()
    generate_pfp()
