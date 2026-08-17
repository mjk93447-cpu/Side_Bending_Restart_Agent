"""Generate a synthetic table image with many NaN cells for OCR tests."""

from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont


def make_nan_table_image(rows: int = 7, cols: int = 4, cell: int = 48) -> np.ndarray:
    """Return a BGR image whose cells contain the text NaN."""
    width = cols * cell
    height = rows * cell
    image = Image.new("RGB", (width, height), (255, 255, 255))
    draw = ImageDraw.Draw(image)
    try:
        font = ImageFont.truetype("arial.ttf", 18)
    except OSError:
        font = ImageFont.load_default()
    for row in range(rows):
        for col in range(cols):
            x = col * cell + 8
            y = row * cell + 12
            draw.text((x, y), "NaN", fill=(0, 0, 0), font=font)
            draw.rectangle(
                [col * cell, row * cell, (col + 1) * cell - 1, (row + 1) * cell - 1],
                outline=(180, 180, 180),
            )
    rgb = np.array(image)
    return rgb[:, :, ::-1].copy()


def save_fixture(path: Path, rows: int = 7, cols: int = 4) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    bgr = make_nan_table_image(rows=rows, cols=cols)
    Image.fromarray(bgr[:, :, ::-1]).save(path)
    return path


if __name__ == "__main__":
    dest = Path(__file__).parent / "nan_table_28.png"
    save_fixture(dest, rows=7, cols=4)
    print(f"wrote {dest}")
