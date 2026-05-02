# play_story.py

import os
import pygame
import random
import json
import config
import math

class StoryPlayer:
    def __init__(self, screen):
        self.screen = screen
        self.current_music = None
        self.clock = pygame.time.Clock()
        self.last_rewards = None  # holds rewards for the last return_choice

        # Load frames data from JSON
        try:
            with open("data/frames.json", "r") as f:
                self.frames_data = json.load(f)
        except Exception as e:
            print(f"[Error] Could not load frames.json: {e}")
            self.frames_data = {}

        # Load the stories, too!
        try:
            with open("data/stories.json", "r") as f:
                self.stories_data = json.load(f)
        except Exception as e:
            print(f"[Error] Could not load stories.json: {e}")
            self.stories_data = {}

    def play_story(self, story_name):
        self.last_rewards = None
        frames_to_play = self.get_frames_for_story(story_name)
        index = 0

        while 0 <= index < len(frames_to_play):
            frame_num = frames_to_play[index]
            next_action = self.play_frame(frame_num)  # play_frame might return a branch!

            # If play_frame returned an action (like 'Tutorial', 'continue', 'kill', 'free', etc.)
            if next_action:
                return next_action

            waiting = True
            while waiting:
                for event in pygame.event.get():
                    if event.type == pygame.QUIT:
                        pygame.quit()
                        exit()
                    elif event.type == pygame.KEYDOWN:
                        if event.key in (pygame.K_RIGHT, pygame.K_SPACE, pygame.K_RETURN):
                            direction = "forward"
                            waiting = False
                        elif event.key == pygame.K_LEFT:
                            direction = "backward"
                            waiting = False
                        elif event.key == pygame.K_ESCAPE:
                            index = len(frames_to_play) - 1
                            waiting = False
                    elif event.type == pygame.MOUSEBUTTONDOWN:
                        direction = "forward"
                        waiting = False
                self.clock.tick(30)

            # Adjust index
            if direction == "forward":
                index += 1
            elif direction == "backward":
                index -= 1

        # If the whole story played without an option branch, just return None
        return None

    def get_frames_for_story(self, story_name):
        # Lowercase keys for case-insensitive lookup
        normalized_stories_data = {k.lower(): v for k, v in self.stories_data.items()}
        frames = normalized_stories_data.get(story_name.lower())
        if frames is None:
            print(f"[Error] Story '{story_name}' not found. Using empty frame list.")
            return []
        return frames

    def play_frame(self, frame_num):
        frame_data = self.frames_data.get(str(frame_num), {})
        text = frame_data.get("text", "")

        # Decide options for this frame first (new JSON structure or legacy)
        options = self.get_options(frame_data)
        has_options = bool(options)

        # Layout bands (text / image / options)
        margin = 20
        H = config.HEIGHT
        W = config.WIDTH

        # Top band: text (about 25% of height)
        text_top = margin
        text_bottom = int(H * 0.25)

        # Bottom band: options (if any)
        if has_options:
            options_top = int(H * 0.65)
            options_bottom = H - margin
            options_area = pygame.Rect(
                margin,
                options_top,
                W - 2 * margin,
                options_bottom - options_top,
            )
        else:
            options_area = None

        # Middle band: image fills between text and options (or to bottom if no options)
        image_band_top = text_bottom + margin
        image_band_bottom = options_area.top - margin if options_area else H - margin
        if image_band_bottom <= image_band_top:
            # Safety: if bands collapse for some reason, just give image a minimal band
            image_band_top = int(H * 0.3)
            image_band_bottom = int(H * 0.6)

        image_band = pygame.Rect(
            margin,
            image_band_top,
            W - 2 * margin,
            image_band_bottom - image_band_top,
        )

        # Load graphics and fit into image_band
        graphic_path = self.get_random_asset("assets/GFX/frame", f"frame_{frame_num}")
        graphic = None
        image_rect = pygame.Rect(0, 0, 0, 0)
        if graphic_path:
            try:
                raw = pygame.image.load(graphic_path).convert_alpha()
                graphic, image_rect = self.fit_graphic_into_band(raw, image_band)
            except Exception as e:
                print(f"[Error] Could not load graphic {graphic_path}: {e}")

        # Load and play music
        music_path = self.get_random_asset("assets/SFX/music/frame", f"frame_music_{frame_num}")
        if music_path:
            self.fade_music(music_path)

        # Load and play voiceover
        voice_path = self.get_random_asset("assets/SFX/voice/frame", f"frame_voice_{frame_num}")
        if voice_path:
            try:
                voiceover = pygame.mixer.Sound(voice_path)
                voiceover.play()
            except Exception as e:
                print(f"[Error] Could not load or play voiceover {voice_path}: {e}")

        # Fade in graphic
        if graphic:
            self.fade_in_graphic(graphic, (image_rect.x, image_rect.y, image_rect.w, image_rect.h, "fixed"))

        # Draw final frame (image + centered text)
        text_center_x = self.display_text(
            text=text,
            graphic=graphic,
            image_rect=image_rect,
            text_top=text_top,
            text_bottom=text_bottom,
            options_area=options_area,
        )

        # Options
        if options and options_area:
            choice_key = self.present_options(options, options_area)
            chosen = options[choice_key]
            next_target = chosen.get("target")

            # If the chosen option is flagged as a return_choice,
            # bubble the target back to the caller (Intro choices, Stone kill/free, etc.).
            if chosen.get("return_choice"):
                # Stash rewards for external use (if any)
                self.last_rewards = frame_data.get("return_rewards")
                return next_target

            # Otherwise, treat target as another story name and branch into it.
            if next_target:
                return self.play_story(next_target)

        if frame_data.get("return_rewards"):
            self.last_rewards = frame_data.get("return_rewards")

        return None

    def fit_graphic_into_band(self, graphic, band_rect):
        """Scale and center a graphic inside the given vertical band."""
        gw, gh = graphic.get_size()
        max_w = band_rect.width
        max_h = band_rect.height

        scale = min(max_w / gw, max_h / gh, 1.0)
        new_w = int(gw * scale)
        new_h = int(gh * scale)
        scaled = pygame.transform.smoothscale(graphic, (new_w, new_h))

        x = band_rect.left + (band_rect.width - new_w) // 2
        y = band_rect.top + (band_rect.height - new_h) // 2
        return scaled, pygame.Rect(x, y, new_w, new_h)

    def get_random_asset(self, folder, prefix):
        try:
            matches = []
            for file in os.listdir(folder):
                if file.startswith(f"{prefix}.") or file.startswith(f"{prefix}_"):
                    matches.append(os.path.join(folder, file))
            if matches:
                return random.choice(matches)
        except Exception as e:
            print(f"[Error] Could not access {folder} for {prefix}: {e}")
        return None

    def fade_music(self, new_music_path):
        try:
            if self.current_music:
                pygame.mixer.music.fadeout(1000)
            pygame.mixer.music.load(new_music_path)
            pygame.mixer.music.play(-1)
            self.current_music = new_music_path
        except Exception as e:
            print(f"[Error] Could not load or play music {new_music_path}: {e}")

    def scale_graphic(self, graphic, pos_choice):
        w, h = graphic.get_size()

        if pos_choice in ["center-top", "center-bottom"]:
            max_width = config.WIDTH * 0.8
            max_height = config.HEIGHT * 0.4
        else:  # left/right
            max_width = config.WIDTH * 0.4
            max_height = config.HEIGHT * 0.8

        scale = min(max_width / w, max_height / h, 1)
        new_size = (int(w * scale), int(h * scale))
        return pygame.transform.smoothscale(graphic, new_size)

    def fade_in_graphic(self, graphic, position):
        x, y, _, _, _ = position
        alpha = 0
        while alpha < 255:
            self.screen.fill((0, 0, 0))
            graphic.set_alpha(alpha)
            self.screen.blit(graphic, (x, y))
            pygame.display.flip()
            alpha += 15
            self.clock.tick(config.FPS)

    def get_graphic_position(self, graphic, frame_data):
        w, h = graphic.get_size()
        margin = 20

        if w == h:
            pos_choice = random.choice(["center-left", "center-right", "center-top", "center-bottom"])
        elif h > w:
            pos_choice = random.choice(["center-left", "center-right"])
        else:
            pos_choice = random.choice(["center-top", "center-bottom"])

        # Half-screen boxes WITH margins
        if pos_choice == "center-left":
            box = pygame.Rect(margin, margin, config.WIDTH // 2 - 2 * margin, config.HEIGHT - 2 * margin)
        elif pos_choice == "center-right":
            box = pygame.Rect(config.WIDTH // 2 + margin, margin, config.WIDTH // 2 - 2 * margin, config.HEIGHT - 2 * margin)
        elif pos_choice == "center-top":
            box = pygame.Rect(margin, margin, config.WIDTH - 2 * margin, config.HEIGHT // 2 - 2 * margin)
        elif pos_choice == "center-bottom":
            box = pygame.Rect(margin, config.HEIGHT // 2 + margin, config.WIDTH - 2 * margin, config.HEIGHT // 2 - 2 * margin)
        else:
            box = pygame.Rect(margin, margin, config.WIDTH - 2 * margin, config.HEIGHT - 2 * margin)

        # Scale graphic to fit within the box
        scale = min(box.width / w, box.height / h, 1)
        new_w, new_h = int(w * scale), int(h * scale)

        # Center graphic in box
        x = box.left + (box.width - new_w) // 2
        y = box.top + (box.height - new_h) // 2

        return (x, y, new_w, new_h, pos_choice)

    def display_text(self, text, graphic, image_rect, text_top, text_bottom, options_area):
        """
        Draws the story text and image in a clean vertical stack:

        [ Top edge ]
        ┌───────────────────────────────┐
        │           TEXT (centered)    │  -> text_top .. text_bottom
        ├───────────────────────────────┤
        │             IMAGE            │  -> image_rect (middle band)
        ├───────────────────────────────┤
        │           OPTIONS            │  -> options_area (bottom band)
        └───────────────────────────────┘
        [ Bottom edge ]
        """
        margin = 20
        base_font_size = 32
        min_font_size = 16
        color = (255, 255, 255)

        W = config.WIDTH
        H = config.HEIGHT

        # Full wipe
        self.screen.fill((0, 0, 0))

        # Draw image if we have one
        if graphic and image_rect.width > 0 and image_rect.height > 0:
            self.screen.blit(graphic, image_rect.topleft)

        # Text box spans full width, only in the top band
        text_box = pygame.Rect(
            margin,
            text_top,
            W - 2 * margin,
            max(40, text_bottom - text_top),
        )

        # Helper: word-wrap with \n support
        def build_lines(font_obj):
            lines = []
            paragraphs = text.split("\n") if text else [""]
            for idx, para in enumerate(paragraphs):
                if para.strip() == "":
                    lines.append("")
                    continue
                words = para.split(" ")
                line = ""
                for word in words:
                    test_line = (line + " " + word).strip()
                    if font_obj.size(test_line)[0] <= text_box.width:
                        line = test_line
                    else:
                        if line:
                            lines.append(line)
                        line = word
                if line:
                    lines.append(line)
                if idx != len(paragraphs) - 1:
                    lines.append("")
            return lines

        # Find a font size that fits vertically
        font_size = base_font_size
        while font_size >= min_font_size:
            font = pygame.font.SysFont(None, font_size)
            lines = build_lines(font)
            total_height = len(lines) * font.get_linesize()
            if total_height <= text_box.height:
                break
            font_size -= 2

        if font_size < min_font_size:
            font_size = min_font_size
            font = pygame.font.SysFont(None, font_size)
            lines = build_lines(font)
            total_height = len(lines) * font.get_linesize()

        # Vertically center lines inside the text box
        y = text_box.top + (text_box.height - total_height) // 2
        for line in lines:
            surf = font.render(line, True, color)
            rect = surf.get_rect()
            rect.centerx = text_box.left + text_box.width // 2
            rect.top = y
            self.screen.blit(surf, rect)
            y += font.get_linesize()

        pygame.display.flip()

        return text_box.left + text_box.width // 2

    def get_options(self, frame_data):
        """
        Build an options dict keyed by "1", "2", ... with:
        {
          "text": str,
          "target": str or None,
          "return_choice": bool
        }

        Supports:
          - NEW style:
              "options": [
                { "text": "...", "target": "Tutorial", "return_choice": true },
                ...
              ]

          - LEGACY style:
              "option_1": "Text",
              "story_1": "StoryName",
              "return_choice": true/false (frame-level)
        """
        # New style
        if "options" in frame_data and isinstance(frame_data["options"], list):
            options = {}
            for idx, opt in enumerate(frame_data["options"], start=1):
                options[str(idx)] = {
                    "text": opt.get("text", f"Option {idx}"),
                    "target": opt.get("target"),
                    "return_choice": opt.get("return_choice", False),
                }
            return options if options else None

        # Legacy style fallback
        options = {}
        index = 1
        frame_return_choice = frame_data.get("return_choice", False)
        while True:
            option_key = f"option_{index}"
            story_key = f"story_{index}"
            if option_key in frame_data and story_key in frame_data:
                options[str(index)] = {
                    "text": frame_data[option_key],
                    "target": frame_data[story_key],
                    "return_choice": frame_return_choice,
                }
                index += 1
            else:
                break

        return options if options else None

    def present_options(self, options, options_area):
        """
        Draws animated option buttons inside the given options_area rect.
        """
        base_font_size = 28
        MIN_FONT_SIZE = 12

        BUTTON_PADDING_X = 16
        BUTTON_PADDING_Y = 8
        BUTTON_SPACING = 10

        hover_timer = 0
        clock = pygame.time.Clock()

        # Colors
        gold = (255, 215, 0)
        bronze = (205, 127, 50)
        dark_red = (120, 0, 0)
        bright_red = (255, 0, 0)

        # First pass: approximate button width from longest text
        temp_font = pygame.font.SysFont(None, base_font_size)
        max_text_width = 0
        for opt in options.values():
            surf = temp_font.render(opt["text"], True, (0, 0, 0))
            max_text_width = max(max_text_width, surf.get_width())

        BUTTON_WIDTH = min(
            max_text_width + 2 * BUTTON_PADDING_X,
            options_area.width,
        )
        BUTTON_HEIGHT = temp_font.get_linesize() + 2 * BUTTON_PADDING_Y

        num_options = len(options)
        max_rows = max(1, options_area.height // (BUTTON_HEIGHT + BUTTON_SPACING))
        num_columns = max(1, math.ceil(num_options / max_rows))

        # If too wide, increase rows until it fits
        while num_columns * (BUTTON_WIDTH + BUTTON_SPACING) - BUTTON_SPACING > options_area.width and max_rows < num_options:
            max_rows += 1
            num_columns = math.ceil(num_options / max_rows)

        total_width = num_columns * (BUTTON_WIDTH + BUTTON_SPACING) - BUTTON_SPACING
        start_x = options_area.left + (options_area.width - total_width) // 2

        # Position buttons
        button_boxes = {}
        option_keys = list(options.keys())
        for idx, key in enumerate(option_keys):
            col = idx // max_rows
            row = idx % max_rows
            x = start_x + col * (BUTTON_WIDTH + BUTTON_SPACING)
            y = options_area.top + row * (BUTTON_HEIGHT + BUTTON_SPACING)
            button_boxes[key] = pygame.Rect(x, y, BUTTON_WIDTH, BUTTON_HEIGHT)

        def render_wrapped_text(surface, text, rect):
            font_size = base_font_size
            while font_size >= MIN_FONT_SIZE:
                font = pygame.font.SysFont(None, font_size)
                words = text.split(" ")
                lines = []
                line = ""
                for word in words:
                    test_line = (line + " " + word).strip()
                    if font.size(test_line)[0] <= rect.width - 2 * BUTTON_PADDING_X:
                        line = test_line
                    else:
                        if line:
                            lines.append(line)
                        line = word
                if line:
                    lines.append(line)

                total_height = len(lines) * font.get_linesize()
                if total_height <= rect.height - 2 * BUTTON_PADDING_Y:
                    y = rect.top + (rect.height - total_height) // 2
                    for ln in lines:
                        s = font.render(ln, True, (0, 0, 0))
                        sx = rect.left + (rect.width - s.get_width()) // 2
                        surface.blit(s, (sx, y))
                        y += font.get_linesize()
                    return
                font_size -= 2

            # Fallback
            font = pygame.font.SysFont(None, MIN_FONT_SIZE)
            s = font.render(text, True, (0, 0, 0))
            sx = rect.left + (rect.width - s.get_width()) // 2
            sy = rect.top + (rect.height - s.get_height()) // 2
            surface.blit(s, (sx, sy))

        while True:
            hover_timer += 0.03
            mx, my = pygame.mouse.get_pos()

            # Clear options band only
            pygame.draw.rect(self.screen, (0, 0, 0), options_area)

            for key, rect in button_boxes.items():
                hovering = rect.collidepoint(mx, my)
                box_surface = pygame.Surface((rect.width, rect.height), pygame.SRCALPHA)

                for x_line in range(rect.width):
                    t = (math.sin(hover_timer + x_line * 0.02) + 1) / 2
                    if hovering:
                        color = (
                            int(dark_red[0] * (1 - t) + bright_red[0] * t),
                            int(dark_red[1] * (1 - t) + bright_red[1] * t),
                            int(dark_red[2] * (1 - t) + bright_red[2] * t),
                            255,
                        )
                    else:
                        color = (
                            int(gold[0] * (1 - t) + bronze[0] * t),
                            int(gold[1] * (1 - t) + bronze[1] * t),
                            int(gold[2] * (1 - t) + bronze[2] * t),
                            255,
                        )
                    pygame.draw.line(box_surface, color, (x_line, 0), (x_line, rect.height))

                self.screen.blit(box_surface, rect.topleft)
                render_wrapped_text(self.screen, options[key]["text"], rect)

            pygame.display.flip()
            clock.tick(config.FPS)

            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    pygame.quit()
                    exit()
                elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                    for key, rect in button_boxes.items():
                        if rect.collidepoint(mx, my):
                            return key


# Usage example
if __name__ == "__main__":
    pygame.init()
    screen = pygame.display.set_mode((config.WIDTH, config.HEIGHT))
    player = StoryPlayer(screen)
    r = player.play_story("Intro")
    print(f"Story ended with: {r}, rewards: {player.last_rewards}")

    if r == "Tutorial":
        r2 = player.play_story("Tutorial")
        print(f"Tutorial ended with: {r2}, rewards: {player.last_rewards}")

    player.play_story("Intro_return")
