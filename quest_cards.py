import pygame
import random
import json
import os

def CreateQuestCard(quest_number):
    # Load quest data
    with open("data/quests.json", "r", encoding="utf-8") as f:
        quests = json.load(f)

    quest = next((q for q in quests if q["quest_number"] == quest_number), None)
    if not quest:
        raise ValueError(f"Quest number {quest_number} not found.")

    # Load overlay data
    with open("data/overlays.json", "r", encoding="utf-8") as f:
        overlays = json.load(f)

    overlay_index = random.randint(0, len(overlays) - 1)
    overlay = overlays[overlay_index]

    gfx_dir = f"assets/GFX/quests/img"
    quest_images = [f for f in os.listdir(gfx_dir) if f.startswith(f"{quest_number}_") and f.endswith(".png")]
    if not quest_images:
        raise FileNotFoundError(f"No images found for quest {quest_number}.")
    quest_image_file = random.choice(quest_images)
    overlay_img = pygame.image.load(f"assets/GFX/quests/overlays/{overlay_index}.png").convert_alpha()
    card_width, card_height = overlay_img.get_size()
    card_surface = pygame.Surface((card_width, card_height), pygame.SRCALPHA)

    x1, y1, x2, y2 = overlay["image_box"]
    img_x = x1
    img_y = y1
    img_w = x2 - x1
    img_h = y2 - y1

    # Load and scale the quest image to fill the image box
    quest_img_path = os.path.join(gfx_dir, quest_image_file)
    quest_img_original = pygame.image.load(quest_img_path).convert_alpha()
    # Scale the quest image to fit the requested size
    quest_img_scaled = pygame.transform.smoothscale(quest_img_original, (img_w, img_h))

    # Create a temp surface to hold the scaled image in the right place
    img_container = pygame.Surface((card_width, card_height), pygame.SRCALPHA)
    img_container.blit(quest_img_scaled, (img_x, img_y))  # img_x and img_y might be negative!

    print(f"Quest #{quest_number} → box: {overlay['image_box']} → scale to: ({img_w}, {img_h})")
    print(f"Offset pos: ({img_x}, {img_y})")
    print(f"Scaled image size: {quest_img_scaled.get_size()}")

    # Blit the container onto the card
    card_surface.blit(img_container, (0, 0))


    card_surface.blit(overlay_img, (0, 0))

    def draw_text_wrapped(
        surface,
        text,
        box,
        font_name="arial",
        color=(0, 0, 0),
        bold=False,
        center_vertically=False,
        horizontal_center=False
    ):
        x, y, x2, y2 = box
        max_width = x2 - x
        max_height = y2 - y
        font_size = 64  # Start big

        while font_size > 10:
            font = pygame.font.SysFont(font_name, font_size, bold=bold)
            words = text.split(" ")
            lines = []
            current_line = ""

            for word in words:
                test_line = f"{current_line} {word}".strip()
                if font.size(test_line)[0] <= max_width:
                    current_line = test_line
                else:
                    lines.append(current_line)
                    current_line = word
            if current_line:
                lines.append(current_line)

            total_height = len(lines) * font.get_linesize()
            if total_height <= max_height:
                break  # fits!
            font_size -= 1

        if center_vertically:
            y_offset = y + (max_height - total_height) // 2
        else:
            y_offset = y

        for line in lines:
            rendered = font.render(line, True, color)
            if horizontal_center:
                line_width = rendered.get_width()
                x_offset = x + (max_width - line_width) // 2
            else:
                x_offset = x
            surface.blit(rendered, (x_offset, y_offset))
            y_offset += font.get_linesize()

    draw_text_wrapped(card_surface, quest["title"], overlay["title_box"], font_name='georgia', bold=True, center_vertically=True, horizontal_center=True)
    draw_text_wrapped(card_surface, quest["rules"], overlay["rules_box"], font_name='arial', bold=False, center_vertically=True, horizontal_center=False)

    return card_surface
