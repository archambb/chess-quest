# config.py
import chess

# Global constants
WIDTH = 1280
HEIGHT = 800
SQUARE_SIZE = 80
FPS = 60

PORTRAIT_WIDTH = WIDTH // 6  # ≈213
BOARD_WIDTH = (WIDTH // 6) * 4  # ≈854
BOARD_HEIGHT = BOARD_WIDTH
POWER_WIDTH = WIDTH // 6  # ≈213


WHITE_COLOR = (240, 217, 181)
BLACK_COLOR = (181, 136, 99)
LIGHT_BLUE = (173, 216, 230)
DARKER_BLUE = (0, 191, 255)
BLUE_OUTLINE = (0, 0, 255)

# Mutable variable (not constant!)
difficulty = 0


# Note: Magic effects are in a glob (alphabetical order) so we use filenames magic_effects_<3-digit number>x<#>y<#>.png
MFX_METEOR  = 0      # effect #1  - falling meteor  (static OR sheet)
MFX_EXPLODE = 1      # effect #2  - explosion
MFX_BOULDER = 2      # effect #3  - falling boulder


# Quest card globals
CARD_SCALE = .2
CARD_SCALE_EXPAND = .4
CARD_MARGIN = 20
CARD_SELECTED_TINT = (255, 255, 0, 100)  # yellowish highlight
CARD_DIM_TINT = (0, 0, 0, 100)           # darken overlay

STARTING_KING_SQUARES = {
    "white": chess.E1,
    "black": chess.E8
}

# --- Piece scaling / layout knobs ---
PIECE_HEIGHT = 1.9            # Max sprite height in squares (cap). e.g., 1.9 = 1 square + 90% of the next
PIECE_BASE_FRACTION = 0.96    # Fraction of square width the piece's base should fill (0.0-1.0)
# File Locations
ASSET_PIECES_DIR =  "assets/GFX/pieces"

# Hover effects
BASE = 0.08          # minimum glow (0..1)
AMP  = 0.80          # additional glow at pulse peak
GAMMA = 1.6          # >1 softens near the peak


check_notification_duration = 750 # /1000 seconds delay of unplayable hard pause notification


# Use this everywhere for consistency
GEAR_ORDER = [
    "hatchet",            # 1.png
    "mace",               # 2.png
    "crossbow",           # 3.png
    "sling",              # 4.png
    "torch",              # 5.png
    "crystal_staff",      # 6.png
    "wand_of_stupidity",  # 7.png
    "gear_key",      # 8.png
    "compass",            # 9.png
    "boots",              # 10.png
    "ice_pick",           # 11.png
    "sword_of_regicide",  # 12.png
]

# Canonical descriptions for each piece of gear
GEAR_DESCRIPTIONS = {
    # Weapons
    "hatchet": (
        "Hatchet - Shatter an enemy shield."
    ),
    "mace": (
        "Mace - Smash the stone of a castle, turning a rook into a pawn."
    ),
    "crossbow": (
        "Crossbow - Fire straight down your king's file, destroying any pawn in its path."
    ),
    "sling": (
        "Sling - Your pawns sling a stone along their rank to kill the enemy queen if unobstructed."
    ),

    # Magic / relics
    "crystal_staff": (
        "Crystal Staff of Transmutation - Transform your pawns into random higher pieces (N, B, or R)."
    ),
    "wand_of_stupidity": (
        "Wand of Stupidity - Temporarily reduce the enemy AI's strength."
    ),

    # Navigation / utility
    "torch": (
        "Torch - Burn away all Pawns of Darkness."
    ),
    "gear_key": (
        "Gear Key - Unlocks the use of all power-ups."
    ),
    "compass": (
        "Compass - Highlight any checkmating move on the board."
    ),

    # Gear
    "boots": (
        "Boots - All forked non-king pieces retreat to a random adjacent safe square."
    ),
    "ice_pick": (
        "Ice Pick - Break a freeze on a single square."
    ),
    
    "sword_of_regicide": (
        "Sword of Regicide - Slay all enemy queens. Future promotions become rooks instead."
    ),
}

DIFFICULTY = "NORMAL"
SFX_VOLUME = 50
MUSIC_VOLUME = 50
VOICE_VOLUME = 50
