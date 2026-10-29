
from math import ceil
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


def create_contact_sheet(
    photos: list[Path],
    output_path: Path,
    columns: int = 3,
    thumbnail_size: tuple[int, int] = (320, 420),
) -> Path:
    if not photos:
        raise ValueError("No photographs supplied.")

    if columns < 1:
        raise ValueError("Columns must be positive.")

    cell_width = thumbnail_size[0] + 30
    cell_height = thumbnail_size[1] + 60
    rows = ceil(len(photos) / columns)

    sheet = Image.new(
        "RGB",
        (columns * cell_width, rows * cell_height),
        "#f2f2f2",
    )

    draw = ImageDraw.Draw(sheet)

    try:
        font = ImageFont.truetype("arial.ttf", 24)
    except OSError:
        font = ImageFont.load_default()

    for index, photo_path in enumerate(photos):
        row = index // columns
        column = index % columns

        x = column * cell_width + 15
        y = row * cell_height + 15

        with Image.open(photo_path) as source:
            image = source.convert("RGB")
            image.thumbnail(thumbnail_size)

        image_x = x + (thumbnail_size[0] - image.width) // 2
        image_y = y + (thumbnail_size[1] - image.height) // 2

        sheet.paste(image, (image_x, image_y))

        draw.text(
            (x, y + thumbnail_size[1] + 8),
            f"Photo {index + 1:02d} — {photo_path.name}",
            fill="#202020",
            font=font,
        )

    output_path = Path(output_path)
    output_path.parent.mkdir(
        parents=True, exist_ok=True
    )

    sheet.save(output_path, quality=90)
    return output_path