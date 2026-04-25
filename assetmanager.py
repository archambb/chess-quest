# assetmanager.py
import pygame
import os
import re
import glob
import json
import random
import config

class AssetManager:
    def __init__(self, game):
        self.SQUARE = config.SQUARE_SIZE
        self.magic_library = []
        self.power_icons = {}
        self.gear_icons = {}
        self.g = game
        self.stalker_image = None

    def load_stalker_image(self):
        """
        Load assets/GFX/pieces/unique/stalker.png and scale like a normal piece:
        - uniform scale by source *width* to target footprint = SQUARE_SIZE * PIECE_BASE_FRACTION
        - keep aspect ratio
        - compose on a canvas of width = SQUARE_SIZE, height = scaled_h (centered)
        - clamp height if it exceeds draw envelope (SQUARE_SIZE * PIECE_HEIGHT)
        Store on game as `stalker_image`.
        """
        path = os.path.join("assets", "GFX", "pieces", "unique", "stalker.png")
        if not os.path.exists(path):
            print(f"[WARN] Stalker image not found: {path}")
            self.g.stalker_image = None
            return None

        try:
            # 1) Load as 32-bit with alpha (matches piece pipeline)
            raw = pygame.image.load(path).convert_alpha()
            src_w, src_h = raw.get_width(), raw.get_height()

            # 2) Scale by WIDTH to the same on-board footprint as pieces
            target_w = int(round(config.SQUARE_SIZE * float(config.PIECE_BASE_FRACTION)))
            scale    = target_w / float(src_w) if src_w > 0 else 1.0
            new_w    = max(1, int(round(src_w * scale)))
            new_h    = max(1, int(round(src_h * scale)))
            scaled   = pygame.transform.smoothscale(raw, (new_w, new_h)).convert_alpha()

            # 3) Safety: clamp height to the same draw envelope used at render time
            #    (your draw code aligns bottom of sprite using SQUARE_SIZE * PIECE_HEIGHT)
            max_h = int(round(config.SQUARE_SIZE * float(config.PIECE_HEIGHT)))
            if new_h > max_h:
                clamp_scale = max_h / float(new_h)
                new_w = max(1, int(round(new_w * clamp_scale)))
                new_h = max(1, int(round(new_h * clamp_scale)))
                scaled = pygame.transform.smoothscale(scaled, (new_w, new_h)).convert_alpha()

            # 4) Compose on a square-width canvas (centered horizontally)
            canvas = pygame.Surface((config.SQUARE_SIZE, new_h), pygame.SRCALPHA)
            x_off  = (config.SQUARE_SIZE - new_w) // 2
            canvas.blit(scaled, (x_off, 0))

            self.g.stalker_image = canvas

            # Optional sanity log to confirm 32-bit with alpha
            # print("Stalker bits/masks:", canvas.get_bitsize(), canvas.get_masks())

            print("[INFO] Loaded Stalker image (piece-pipeline scale).")
            return canvas

        except Exception as e:
            print(f"[ERROR] Loading Stalker image failed: {e}")
            self.g.stalker_image = None
            return None

    def load_gear_icons(self):
        """
        Load gear icons from assets/GFX/equip/1.png .. 12.png
        and map them onto the logical gear names in GEAR_ORDER.
        Returns a dict: { 'hatchet': Surface, ... }
        """
        icon_dir = os.path.join("assets", "GFX", "equip")
        icon_size = 72  # or whatever looks right next to power icons

        mapping = {}
        for idx, name in enumerate(config.GEAR_ORDER, start=1):
            filename = f"{idx}.png"
            path = os.path.join(icon_dir, filename)

            if not os.path.exists(path):
                print(f"[WARN] Equip icon missing for {name}: {path}")
                continue

            try:
                img = pygame.image.load(path).convert_alpha()
                img = pygame.transform.smoothscale(img, (icon_size, icon_size))
                mapping[name] = img
            except Exception as e:
                print(f"[ERROR] Failed to load equip icon {name} from {path}: {e}")

        self.gear_icons = mapping
        print(f"[INFO] Loaded {len(mapping)} gear icons.")
        return mapping


    def load_gold_coins(self):
        coin_images = []
        i = 0  # Start at zero and count up

        while True:
            coin_path = f"assets/GFX/UI/gold_coin_{i}.png"
            if os.path.exists(coin_path):
                icon = pygame.image.load(coin_path).convert_alpha()
                coin_images.append(icon)
                i += 1  # Keep looking for more
            else:
                # No more coins found
                if i == 0:
                    print("[WARN] No gold coin icons found!")
                else:
                    print(f"[INFO] Loaded {i} gold coin images.")
                break

        return coin_images


    def load_magic_effects(self):
        """
        Load static and animated MFX sprites from assets/GFX/MFX.
        Animated sprites are named like magic_effects_001x4y4.png.

        Note: These are read as a glob, so they need to be in alphabetical order. We do this with the preceding 0's.

        Also, this is what dispays the magic effects:
            def display_magic_effect(self, eid, effect_idx,
                            start_x, start_y,
                            end_x=None, end_y=None,
                            duration=0):

        """
        self.g.magic_library.clear()

        files = sorted(glob.glob("assets/GFX/MFX/magic_effects_*.png"))
        if not files:
            print("[WARN] No MFX GFX found!")
            return

        for path in files:
            # Get base ID number from filename
            match_id = re.search(r"magic_effects_(\d+)", path)
            if not match_id:
                continue  # skip non-matching

            # Parse sheet format
            m = re.search(r"x(\d+)y(\d+)\.png$", path)
            cols, rows = (int(m.group(1)), int(m.group(2))) if m else (1, 1)

            sheet = pygame.image.load(path).convert_alpha()
            w, h = sheet.get_width() // cols, sheet.get_height() // rows

            # Build the frames, modifying the graphics to scale to the size of a chess square
            frames = []
            for r in range(rows):
                for c in range(cols):
                    frame = sheet.subsurface(pygame.Rect(c * w, r * h, w, h))
                    frame = pygame.transform.smoothscale(frame, (config.SQUARE_SIZE, config.SQUARE_SIZE))
                    frames.append(frame)

            self.g.magic_library.append({
                "frames": frames,
                "fps": 12  # default
            })

        print(f"[INFO] Loaded {len(self.g.magic_library)} MFX animations.")
        
        
    def load_power_icons(self):
        icon_images = {}
        icon_dir = "assets/GFX/powers"
        icon_size = 72

        for power in self.g.powerups.keys():
            icon_path = os.path.join(icon_dir, f"{power}.png")
            if os.path.exists(icon_path):
                icon = pygame.image.load(icon_path).convert_alpha()
                icon = pygame.transform.scale(icon, (icon_size, icon_size))
                icon_images[power] = icon
            else:
                print(f"[WARN] Icon not found for power: {power}")

        return icon_images

    def load_spellbook_gfx(self):
        # spell info
        with open(r"data/spell_description.json", "r", encoding="utf-8") as f:
            raw_spell_info = json.load(f)

        self.g.spell_info = self._normalize_spell_info(raw_spell_info)

        self.g.spell_scroll = pygame.image.load(r"assets/GFX/UI/scroll.png").convert_alpha()

        # take care of the quest status scroll here as well
        self.g.quest_status_scroll = pygame.image.load(r"assets/GFX/UI/quest_status_scroll.png").convert_alpha()
        book_icon_path = "assets/GFX/powers/spells_book.png"
        if os.path.exists(book_icon_path):
            book_icon = pygame.image.load(book_icon_path).convert_alpha()
            print("[INFO] Loaded spellbook icon.")
            return book_icon
        else:
            print("[WARN] Spellbook icon not found.")
            return None

    def load_spellbook_background(self):
        path = "assets/GFX/UI/open_book.png"
        if os.path.exists(path):
            return pygame.image.load(path).convert_alpha()
        else:
            print("[WARN] Spellbook background not found.")
            return None

    def load_background_image(self,world_number: int | str) -> pygame.Surface | None:
        # Build the search pattern cross-platform-safe
        pattern = os.path.join("assets", "GFX", "backgrounds", f"{world_number}_*.png")

        # Find all matching files
        candidates = glob.glob(pattern)
        if not candidates:
            print(f"[Warning] No background images found for pattern: {pattern}")
            return None

        # Choose one at random
        path = random.choice(candidates)

        try:
            # Load and convert with alpha for fastest blits
            background = pygame.image.load(path).convert_alpha()
            return background
        except Exception as e:
            print(f"[Error] Could not load background '{path}': {e}")
            return None
        
    def load_piece_images(self):
        
        # Robust stage lookup with default 1 if missing
        wd = self.g.world.world_data
        stage = wd.get(self.g.world.player_pos, {}).get("stage_id", 1)
        if stage == 4:
            self.load_stalker_image()
        def _resolve_piece_path(set_id: str, piece_upper: str, is_white: bool, is_player_set: bool):
            """
            Try multiple filename patterns for a given set/wizard and color.
            piece_upper: 'K','Q','R','B','N','P'
            """
            color_tag = "w" if is_white else "b"
            if is_white:
                pieces = piece_upper
            else:
                pieces = piece_upper.lower() # Likely doesn't matter on Windows, but may on other OSes

            if is_player_set:
                # Preferred: p_{set}_{w|b}_{Piece}.png
                p1 = os.path.join(config.ASSET_PIECES_DIR, f"p_{set_id}_{color_tag}_{pieces}.png")
                return p1
            else:
                # Preferred: {wizard_id#}_{w|b}_{Piece}.png
                p1 = os.path.join(config.ASSET_PIECES_DIR, f"{set_id}_{color_tag}_{pieces}.png")
                return p1

        def _scale_piece_to_square(surface: pygame.Surface) -> pygame.Surface:
            """
            Scale uniformly so the *image width* becomes
            (SQUARE_SIZE * PIECE_BASE_FRACTION). Keep aspect ratio.
            Return a canvas of width SQUARE_SIZE and height = scaled_h,
            with the piece horizontally centered (top aligned in the canvas).
            """
            src_w, src_h = surface.get_width(), surface.get_height()   # ~250×450

            # target footprint width on the board
            target_w = int(round(config.SQUARE_SIZE * float(config.PIECE_BASE_FRACTION)))

            # uniform scale from the known source width
            scale   = target_w / float(src_w)
            new_w   = max(1, int(round(src_w * scale)))
            new_h   = max(1, int(round(src_h * scale)))

            scaled  = pygame.transform.smoothscale(surface, (new_w, new_h))

            # compose on a square-width canvas; we’ll bottom-align at draw time
            canvas  = pygame.Surface((config.SQUARE_SIZE, new_h), pygame.SRCALPHA)
            x_off   = (config.SQUARE_SIZE - new_w) // 2
            canvas.blit(scaled, (x_off, 0))
            return canvas

        # ---------------------------------------
        pieces = ['R','N','B','Q','K','P']
        images = {}

        player_set_id   = str(self.g.player_set)  # player's chosen set
        enemy_wizard_id = str(stage)            # enemy wizard id

        if self.g.player_side == "white":
            player_is_white = True
            enemy_is_white = False
        else:
            player_is_white = False
            enemy_is_white = True
        
        for P in pieces:
            # PLAYER
            player_white_path = _resolve_piece_path(player_set_id, P, is_white=player_is_white,  is_player_set=True)
            if not player_white_path:
                raise FileNotFoundError(
                    f"Missing player asset for {P}: tried p_{player_set_id}_w_{P}.png and legacy variants in {config.ASSET_PIECES_DIR}"
                )
            img_w = pygame.image.load(player_white_path).convert_alpha()
            img_w = _scale_piece_to_square(img_w)
            if player_is_white:
                images[P] = img_w
            else:
                images[P.lower()] = img_w

            # ENEMY
            enemy_black_path = _resolve_piece_path(enemy_wizard_id, P, is_white=enemy_is_white, is_player_set=False)
            if not enemy_black_path:
                raise FileNotFoundError(
                    f"Missing enemy asset for {P}: tried {enemy_wizard_id}_b_{P}.png and legacy variants in {config.ASSET_PIECES_DIR}"
                )
            img_b = pygame.image.load(enemy_black_path).convert_alpha()
            img_b = _scale_piece_to_square(img_b)
            if enemy_is_white:
                images[P] = img_b
            else:
                images[P.lower()] = img_b
        return images

    def load_portrait_image(self, stage):
        # Load enemy (AI) portrait
        enemy_path = f"assets/GFX/portraits/{stage}.png"
        hero_path = f"assets/GFX/portraits/hero/{stage}.png"
        enemy_portrait = pygame.image.load(enemy_path).convert_alpha()
        self.g.hero_portrait = pygame.image.load(hero_path).convert_alpha()
        
        return enemy_portrait
    
    def load_game_state_images(self):
        gamestate_path_check = f"assets/GFX/gamestate/check.png"
        gamestate_path_checkmate = f"assets/GFX/gamestate/checkmate.png"
        gamestate_path_stalemate = f"assets/GFX/gamestate/stalemate.png"
        gamestate_path_ragequit = f"assets/GFX/gamestate/rage_quit.png"

        self.g.gamestate_image_check = pygame.image.load(gamestate_path_check).convert_alpha()
        self.g.gamestate_image_checkmate = pygame.image.load(gamestate_path_checkmate).convert_alpha()
        self.g.gamestate_image_stalemate = pygame.image.load(gamestate_path_stalemate).convert_alpha()
        self.g.gamestate_image_ragequit = pygame.image.load(gamestate_path_ragequit).convert_alpha()

        print("[INFO] Loaded game state images.")

    def load_lock_ui_gfx(self):
        """
        Load chain.png, lock.png, shackle.png from assets/GFX/UI and precompute
        scaled versions and destination rects.

        Chain:
          - centered in box (1078,11) -> (1268,388)
          - stretched to fill that box

        Lock and Shackle:
          - centered in same box
          - scaled to 2/3 of that box width
          - maintain aspect ratio (fit within (2/3 box_w, box_h))
        """
        # Target box
        x1, y1 = 1078, 11
        x2, y2 = 1268, 388
        box_w = x2 - x1
        box_h = y2 - y1

        # Store rect for reference
        self.g.lock_ui_box = pygame.Rect(x1, y1, box_w, box_h)

        # Load raw
        chain_raw   = self._load_ui_image("chain.png")
        lock_raw    = self._load_ui_image("lock.png")
        shackle_raw = self._load_ui_image("shackle.png")

        # Store raw on game (so you can rescale later if needed)
        self.g.chain_raw = chain_raw
        self.g.lock_raw = lock_raw
        self.g.shackle_raw = shackle_raw

        # Chain: stretched to fill box exactly
        chain_scaled = self._scale_stretch(chain_raw, box_w, box_h) if chain_raw else None
        chain_rect = pygame.Rect(x1, y1, box_w, box_h)

        # Lock + shackle: width = 2/3 of box width; fit within that width and box height
        target_w = int(round(box_w * (2.0 / 3.0)))
        target_h = box_h

        lock_scaled = self._scale_fit(lock_raw, target_w, target_h) if lock_raw else None
        shackle_scaled = self._scale_fit(shackle_raw, target_w, target_h) if shackle_raw else None

        # Center lock and shackle within the SAME big box
        lock_rect = None
        if lock_scaled:
            lock_rect = lock_scaled.get_rect(center=(x1 + box_w // 2, y1 + box_h // 2))

        shackle_rect = None
        if shackle_scaled:
            shackle_rect = shackle_scaled.get_rect(center=(x1 + box_w // 2, y1 + box_h // 2))

        # Store scaled + rects
        self.g.chain_image = chain_scaled
        self.g.chain_rect = chain_rect

        self.g.lock_image = lock_scaled
        self.g.lock_rect = lock_rect

        self.g.shackle_image = shackle_scaled
        self.g.shackle_rect = shackle_rect

        print("[INFO] Loaded lock UI gfx (chain/lock/shackle).")
        return {
            "chain": chain_scaled,
            "lock": lock_scaled,
            "shackle": shackle_scaled,
        }

    def _load_ui_image(self, filename: str):
        """Load a UI PNG from assets/GFX/UI with alpha, returning a Surface or None."""
        path = os.path.join("assets", "GFX", "UI", filename)
        if not os.path.exists(path):
            print(f"[WARN] UI image not found: {path}")
            return None
        try:
            return pygame.image.load(path).convert_alpha()
        except Exception as e:
            print(f"[ERROR] Failed loading UI image {path}: {e}")
            return None

    def _scale_fit(self, surf: pygame.Surface, max_w: int, max_h: int) -> pygame.Surface:
        """
        Scale surf to fit within (max_w,max_h) while preserving aspect ratio.
        """
        if surf is None:
            return None
        sw, sh = surf.get_width(), surf.get_height()
        if sw <= 0 or sh <= 0:
            return surf
        scale = min(max_w / float(sw), max_h / float(sh))
        new_w = max(1, int(round(sw * scale)))
        new_h = max(1, int(round(sh * scale)))
        return pygame.transform.smoothscale(surf, (new_w, new_h)).convert_alpha()

    def _scale_stretch(self, surf: pygame.Surface, w: int, h: int) -> pygame.Surface:
        """
        Scale surf to exactly (w,h) (does NOT preserve aspect ratio).
        """
        if surf is None:
            return None
        w = max(1, int(w))
        h = max(1, int(h))
        return pygame.transform.smoothscale(surf, (w, h)).convert_alpha()

    def _normalize_spell_info(self, raw_spell_info: dict) -> dict:
        """
        Accept either old spell JSON format:
            { "Flood": "description text" }
        or new format:
            {
            "Flood": {
                "name": "Flood",
                "description": "...",
                "cast_type": "targeted",
                "target_mode": "square",
                "target_rgb": [40,120,255]
            }
            }

        Returns normalized dict in the new structure.
        """
        normalized = {}

        for spell_name, value in raw_spell_info.items():
            # Old format: plain string description
            if isinstance(value, str):
                normalized[spell_name] = {
                    "name": spell_name,
                    "description": value,
                    "cast_type": "instant",
                    "target_mode": None,
                    "target_rgb": None,
                }
                continue

            # New format: dict
            if isinstance(value, dict):
                rgb = value.get("target_rgb")
                if rgb is not None:
                    rgb = list(rgb)

                normalized[spell_name] = {
                    "name": value.get("name", spell_name),
                    "description": value.get("description", ""),
                    "cast_type": value.get("cast_type", "instant"),
                    "target_mode": value.get("target_mode"),
                    "target_rgb": rgb,
                }
                continue

            # Fallback
            print(f"[WARN] Invalid spell info entry for {spell_name}; using defaults.")
            normalized[spell_name] = {
                "name": spell_name,
                "description": "",
                "cast_type": "instant",
                "target_mode": None,
                "target_rgb": None,
            }

        print(f"[INFO] Loaded spell metadata for {len(normalized)} spells.")
        return normalized


    def get_spell_def(self, spell_name: str) -> dict:
        """
        Safe accessor for spell metadata.
        """
        info = getattr(self.g, "spell_info", {}) or {}
        return info.get(spell_name, {
            "name": spell_name,
            "description": "",
            "cast_type": "instant",
            "target_mode": None,
            "target_rgb": None,
        })