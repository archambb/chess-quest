# intro_screen.py
import pygame
import os
import config
import math

class BeginningScreens:
    def __init__(self):
        pygame.init()
        pygame.mixer.init()
        self.screen = pygame.display.set_mode((config.WIDTH, config.HEIGHT))
        pygame.display.set_caption("Chess Quest Intro")

    def intro_screen(self):
        # Load intro image
        try:
            intro_img = pygame.image.load(os.path.join("assets", "GFX", "UI", "intro_screen.png")).convert()
            intro_img = pygame.transform.scale(intro_img, (config.WIDTH, config.HEIGHT))
        except (pygame.error, FileNotFoundError):
            print("Warning: Could not load 'intro_screen.png'. Using blank background.")
            intro_img = pygame.Surface((config.WIDTH, config.HEIGHT))
            intro_img.fill((0, 0, 0))  # fallback black background


        # Load and play looping intro sound
        try:
            game_start_sound = pygame.mixer.Sound(os.path.join("assets", "SFX", "music", "game_start.wav"))
            game_start_sound.play(-1)
        except pygame.error:
            print("Warning: Could not load 'game_start.wav'. Sound will be skipped.")
            game_start_sound = None

        waiting = True
        clock = pygame.time.Clock()

        while waiting:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    pygame.quit()
                    exit()
                elif event.type == pygame.KEYDOWN or event.type == pygame.JOYBUTTONDOWN or event.type == pygame.MOUSEBUTTONDOWN:
                    waiting = False

            self.screen.blit(intro_img, (0, 0))
            pygame.display.flip()
            clock.tick(config.FPS)

        # # Stop the sound
        # game_start_sound.stop()
        # self.show_main_menu()
 
    def show_main_menu(self):
        try:
            game_start_img = pygame.image.load(os.path.join("assets", "GFX", "UI", "main_menu.png")).convert()
            game_start_img = pygame.transform.scale(game_start_img, (config.WIDTH, config.HEIGHT))
        except (pygame.error, FileNotFoundError):
            print("Warning: Could not load 'main_menu.png'. Using blank background.")
            game_start_img = pygame.Surface((config.WIDTH, config.HEIGHT))
            game_start_img.fill((0, 0, 0))  # fallback black background


        VERTICAL_SPACING = 70
        Y_OFFSET = 300
        BUTTON_WIDTH = 280
        BUTTON_HEIGHT = 50

        menu_items = [
            "CONTINUE",
            "NEW GAME",
            "OPTIONS",
            "LIBRARY",
            "CREDITS"
        ]

        button_boxes = {}
        for index, item in enumerate(menu_items):
            x = (config.WIDTH - BUTTON_WIDTH) // 2  # center horizontally
            y = Y_OFFSET + index * VERTICAL_SPACING
            button_boxes[item] = pygame.Rect(x, y, BUTTON_WIDTH, BUTTON_HEIGHT)


        running = True
        clock = pygame.time.Clock()
        font = pygame.font.SysFont(None, 48)

        hover_timer = 0

        # Colors for shimmer
        gold = (255, 215, 0)
        bronze = (205, 127, 50)
        dark_red = (120, 0, 0)
        bright_red = (255, 0, 0)

        return_value = None
        
        while running:
            hover_timer += 0.03  # slow down the shimmer animation

            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    pygame.quit()
                    exit()
                elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                    mx, my = pygame.mouse.get_pos()
                    for name, rect in button_boxes.items():
                        if rect.collidepoint(mx, my):
                            if name == "CONTINUE":
                                self.game_start_continue()
                            elif name == "NEW GAME":
                                return_value = self.game_start_new_game()
                            elif name == "OPTIONS":
                                self.options_menu()
                            elif name == "LIBRARY":
                                self.show_library()
                            elif name == "CREDITS":
                                self.show_credits()
                            running = False

            self.screen.blit(game_start_img, (0, 0))

            mx, my = pygame.mouse.get_pos()
            for name, rect in button_boxes.items():
                hovering = rect.collidepoint(mx, my)

                # Create smooth shimmer across button
                box_surface = pygame.Surface((rect.width, rect.height), pygame.SRCALPHA)
                for x in range(rect.width):
                    t = (math.sin(hover_timer + x * 0.02) + 1) / 2  # 0-1 smooth shimmer
                    if hovering:
                        color = (
                            int(dark_red[0] * (1 - t) + bright_red[0] * t),
                            int(dark_red[1] * (1 - t) + bright_red[1] * t),
                            int(dark_red[2] * (1 - t) + bright_red[2] * t),
                            255
                        )
                    else:
                        color = (
                            int(gold[0] * (1 - t) + bronze[0] * t),
                            int(gold[1] * (1 - t) + bronze[1] * t),
                            int(gold[2] * (1 - t) + bronze[2] * t),
                            255
                        )
                    pygame.draw.line(box_surface, color, (x, 0), (x, rect.height))

                self.screen.blit(box_surface, rect.topleft)

                # Draw black text on top
                text_surf = font.render(name, True, (0,0,0))
                text_rect = text_surf.get_rect(center=rect.center)
                self.screen.blit(text_surf, text_rect)

            pygame.display.flip()
            clock.tick(config.FPS)

        if return_value is not None:
            return return_value


    def game_start_new_game(self):
        # Load background
        try:
            game_new_img = pygame.image.load(os.path.join("assets", "GFX", "UI", "new_game.png")).convert()
            game_new_img = pygame.transform.scale(game_new_img, (config.WIDTH, config.HEIGHT))
        except (pygame.error, FileNotFoundError):
            print("Warning: Could not load 'new_game.png'. Using blank background.")
            game_new_img = pygame.Surface((config.WIDTH, config.HEIGHT))  # fallback blank surface
            game_new_img.fill((0, 0, 0))  # black fallback background


        # Layout variables
        PADDING_X = 50
        VERTICAL_SPACING = 70
        Y_OFFSET = 50
        BUTTON_WIDTH = 280
        BUTTON_HEIGHT = 50

        # Difficulty ranks & descriptions
        difficulty_ranks = [
            "VERY EASY", "EASY", "NORMAL", "CHALLENGING",
            "ADVANCED", "EXPERT", "MASTER", "GRANDMASTER"
        ]

        difficulty_descriptions = [
            "Soldiers cost 0 gold each to maintain. Very low enemy AI. A child may accidentally beat the g.",
            "Soldiers cost 1 gold each to maintain. Very low enemy AI.",
            "Soldiers cost 1 gold each to maintain. Enemy AI starts at a competent level and gradually becomes more difficult.",
            "Soldiers cost 1 gold each to maintain. Enemy AI starts fairly hard and gradually becomes more difficult.",
            "Soldiers cost 1 gold each to maintain. Enemy AI starts hard and grows rather quickly.",
            "Soldiers cost 2 gold each to maintain. Enemy AI starts hard and grows quickly.",
            "Soldiers cost 2 gold each to maintain. Enemy AI starts hard and grows quickly.",
            "Soldiers cost 3 gold each to maintain. Enemy AI starts hard and grows very quickly."
        ]

        # Buttons & images
        button_boxes = {}
        difficulty_images = []

        for index, rank in enumerate(difficulty_ranks):
            x = PADDING_X
            y = Y_OFFSET + index * VERTICAL_SPACING
            button_boxes[rank] = pygame.Rect(x, y, BUTTON_WIDTH, BUTTON_HEIGHT)

            # Load the corresponding image with error handling
            img_path = os.path.join("assets", "GFX", "UI", f"difficulty_{index}.png")
            try:
                img = pygame.image.load(img_path).convert_alpha()
                difficulty_images.append(img)
            except (pygame.error, FileNotFoundError):
                print(f"Warning: Could not load {img_path}. Using blank fallback image.")
                blank_img = pygame.Surface((400, 400), pygame.SRCALPHA)  # transparent fallback
                difficulty_images.append(blank_img)



        running = True
        clock = pygame.time.Clock()
        font = pygame.font.SysFont(None, 48)

        hover_timer = 0
        gold = (255, 215, 0)
        bronze = (205, 127, 50)
        dark_red = (120, 0, 0)
        bright_red = (255, 0, 0)

        hovered_index = None

        while running:
            hover_timer += 0.03

            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    pygame.quit()
                    exit()
                elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                    mx, my = pygame.mouse.get_pos()
                    for index, (name, rect) in enumerate(button_boxes.items()):
                        if rect.collidepoint(mx, my):
                            config.difficulty = index
                            print(f"Difficulty set to: {config.difficulty} ({name})")

                            # ---- NEW: Set soldier upkeep based on difficulty ----
                            if index == 0:
                                config.gold_per_unit = 0
                            elif 1 <= index <= 4:
                                config.gold_per_unit = 1
                            elif 5 <= index <= 6:
                                config.gold_per_unit = 2
                            else:
                                config.gold_per_unit = 3

                            print(f"Army upkeep cost set to: {config.gold_per_unit} gold per unit")

                            running = False
                            return "New Game"

                elif event.type == pygame.KEYDOWN:
                            if event.key == pygame.K_ESCAPE:
                                running = False
                                return

            # Draw background
            self.screen.blit(game_new_img, (0, 0))

            mx, my = pygame.mouse.get_pos()
            hovered_index = None
            for index, (name, rect) in enumerate(button_boxes.items()):
                hovering = rect.collidepoint(mx, my)
                if hovering:
                    hovered_index = index

                # Shimmering effect
                box_surface = pygame.Surface((rect.width, rect.height), pygame.SRCALPHA)
                for x in range(rect.width):
                    t = (math.sin(hover_timer + x * 0.02) + 1) / 2
                    if hovering:
                        color = (
                            int(dark_red[0] * (1 - t) + bright_red[0] * t),
                            int(dark_red[1] * (1 - t) + bright_red[1] * t),
                            int(dark_red[2] * (1 - t) + bright_red[2] * t),
                            255
                        )
                    else:
                        color = (
                            int(gold[0] * (1 - t) + bronze[0] * t),
                            int(gold[1] * (1 - t) + bronze[1] * t),
                            int(gold[2] * (1 - t) + bronze[2] * t),
                            255
                        )
                    pygame.draw.line(box_surface, color, (x, 0), (x, rect.height))

                self.screen.blit(box_surface, rect.topleft)

                # Draw black text
                text_surf = font.render(name, True, (0, 0, 0))
                text_rect = text_surf.get_rect(center=rect.center)
                self.screen.blit(text_surf, text_rect)

                # Determine the target zone for the images
                # Example: position (config.WIDTH - 400, 250), size 256x256
                TARGET_X = config.WIDTH - 600
                TARGET_Y = config.HEIGHT // 2
                TARGET_SIZE = 400  # since all images are square

                # During drawing, scale and blit the image
                if hovered_index is not None:
                    difficulty_img = difficulty_images[hovered_index]
                    if difficulty_img:
                        # Crop out 5 pixels from each edge
                        cropped_rect = pygame.Rect(5, 5, difficulty_img.get_width() - 10, difficulty_img.get_height() - 10)
                        cropped_img = difficulty_img.subsurface(cropped_rect).copy()  # copy to a new Surface

                        # Scale the cropped image to the target size
                        scaled_img = pygame.transform.smoothscale(cropped_img, (TARGET_SIZE, TARGET_SIZE))
                        self.screen.blit(scaled_img, (TARGET_X, TARGET_Y - TARGET_SIZE // 2))

                        # Draw centered description text
                        description = difficulty_descriptions[hovered_index]
                        desc_font = pygame.font.SysFont(None, 32)
                        desc_surf = desc_font.render(description, True, (255, 255, 255))
                        desc_rect = desc_surf.get_rect(center=(config.WIDTH // 2, config.HEIGHT - 50))
                        self.screen.blit(desc_surf, desc_rect)



            pygame.display.flip()
            clock.tick(config.FPS)

        return None



    def game_start_continue(self):
        print("Continue selected.")


    def options_menu(self):
        print("Options menu selected.")

    def show_library(self):
        print("Library selected.")

    def show_credits(self):
        print("Credits selected.")

if __name__ == "__main__":
    beginning_screen = BeginningScreens()
    beginning_screen.intro_screen()
