from __future__ import annotations

import chess


PIECE_SYMBOLS = set("PNBRQKpnbrqk")


def _log(message: str) -> None:
    print(f"[DEBUG OVERLAY] {message}")


def _player_turn_color(g):
    return chess.WHITE if getattr(g, "player_side", "white") == "white" else chess.BLACK


def _mark_board_changed(g) -> None:
    if hasattr(g, "_spell_cache_dirty"):
        g._spell_cache_dirty = True
    if hasattr(g, "possible_moves"):
        g.possible_moves = []
    if hasattr(g, "selected_square"):
        g.selected_square = None
    if hasattr(g, "selected_power"):
        g.selected_power = None
    if hasattr(g, "selected_spell"):
        g.selected_spell = None
    if hasattr(g, "compass_hint"):
        g.compass_hint = None


def register_win(g, **_):
    _log("Registering win round.")
    return g.win_round()


def register_loss(g, **_):
    _log("Registering loss round.")
    return g.lose_round()


def register_stalemate(g, **_):
    _log("Registering stalemate round.")
    return g.stalemate_round()


def trigger_gamestate_display(g, state="check", **_):
    renderer = getattr(g, "renderer", None)
    if renderer and hasattr(renderer, "trigger_gamestate_display"):
        _log(f"Triggering game-state overlay: {state}")
        renderer.trigger_gamestate_display(state)


def reset_quest_status(g, **_):
    quests = getattr(g, "quests", None)
    if quests and hasattr(quests, "setup_quest_status_tracking"):
        _log("Resetting quest status for active quests.")
        quests.setup_quest_status_tracking()


def complete_quest(g, quest_num=None, **_):
    quests = getattr(g, "quests", None)
    if not quests:
        return
    if quest_num is None:
        active = getattr(quests, "active_quests", [])
        if not active:
            _log("No active quest selected to complete.")
            return
        quest_num = active[0]
    quest_num = int(quest_num)
    quest_data = quests.quest_lookup.get(quest_num)
    reward = {}
    if quest_data:
        pairs = quest_data.get("win_reward_pairs") or []
        if pairs:
            reward = pairs[0].get("reward", {})
    _log(f"Completing quest {quest_num}.")
    quests.win_quest(quest_num, reward)


def start_quest(g, quest_num=None, **_):
    if quest_num is None:
        return
    quest_num = int(quest_num)
    quests = getattr(g, "quests", None)
    if not quests or quest_num not in quests.quest_lookup:
        _log(f"Cannot start unknown quest {quest_num}.")
        return
    if quest_num not in quests.active_quests:
        if len(quests.active_quests) >= 3:
            removed = quests.active_quests.pop(0)
            _log(f"Removed active quest {removed} to make room.")
        quests.active_quests.append(quest_num)
    _ensure_quest_card_available(g, quest_num)
    quests.setup_quest_status_tracking()
    _log(f"Started quest {quest_num}.")


def grant_quest_reward(g, quest_num=None, pair_index=0, **_):
    if quest_num is None:
        return
    quest_num = int(quest_num)
    pair_index = int(pair_index or 0)
    quests = getattr(g, "quests", None)
    handler = getattr(g, "quest_reward_handler", None)
    if not quests or not handler:
        return
    quest_data = quests.quest_lookup.get(quest_num)
    if not quest_data:
        return
    pairs = quest_data.get("win_reward_pairs") or []
    if not pairs:
        _log(f"Quest {quest_num} has no reward pairs.")
        return
    pair_index = max(0, min(pair_index, len(pairs) - 1))
    reward = pairs[pair_index].get("reward", {})
    display_index = quests.active_quests.index(quest_num) if quest_num in quests.active_quests else None
    _ensure_quest_card_available(g, quest_num)
    _log(f"Granting reward for quest {quest_num}: {reward}")
    handler.give_reward(quest_num, reward, display_index=display_index)


def _ensure_quest_card_available(g, quest_num: int) -> None:
    quests = getattr(g, "quests", None)
    if not quests:
        return
    if not hasattr(quests, "quest_candidates") or quests.quest_candidates is None:
        quests.quest_candidates = []
    if not hasattr(quests, "quest_cards") or quests.quest_cards is None:
        quests.quest_cards = []
    if quest_num in quests.quest_candidates:
        return
    try:
        import pygame
        import config
        from quest_cards import CreateQuestCard

        card = CreateQuestCard(quest_num)
        w, h = card.get_size()
        quests.original_card_size = (w, h)
        scaled = pygame.transform.smoothscale(
            card,
            (int(w * config.CARD_SCALE_EXPAND), int(h * config.CARD_SCALE_EXPAND)),
        )
        quests.quest_candidates.append(quest_num)
        quests.quest_cards.append(scaled)
    except Exception as exc:
        _log(f"Could not build quest card {quest_num}: {exc}")


def force_turn(g, color="white", **_):
    board = getattr(g, "board", None)
    if not board:
        return
    board.turn = chess.WHITE if color == "white" else chess.BLACK
    _mark_board_changed(g)
    _log(f"Forced side to move: {color}.")


def trigger_enemy_move(g, **_):
    engine = getattr(g, "enemy_move_engine", None)
    if not engine:
        _log("Enemy move engine is not available.")
        return
    _log("Triggering one enemy move manually.")
    try:
        engine.engine_move()
    except Exception as exc:
        _log(f"Enemy move failed: {exc}")


def setup_instant_checkmate(g, color="white", **_):
    """
    Build a tiny king + two rooks position where the chosen color has mate in 1.

    White setup: white to move, K a1, R a2/b2, black K c1, with Rb1#.
    Black setup mirrors piece colors: black to move, k a1, r a2/b2, white K c1,
    with ...Rb1#.
    """
    board = getattr(g, "board", None)
    if not board:
        return

    color = "black" if color == "black" else "white"
    mover = chess.BLACK if color == "black" else chess.WHITE
    defender = not mover

    board.clear()
    board.set_piece_at(chess.A1, chess.Piece(chess.KING, mover))
    board.set_piece_at(chess.A2, chess.Piece(chess.ROOK, mover))
    board.set_piece_at(chess.B2, chess.Piece(chess.ROOK, mover))
    board.set_piece_at(chess.C1, chess.Piece(chess.KING, defender))
    board.turn = mover
    board.clear_stack()
    _mark_board_changed(g)
    _log(f"Set up {color} mate-in-one: move rook b2 to b1.")


def reset_board(g, **_):
    _log("Resetting board.")
    return g.reset_board()


def clear_board_to_tray(g, tray=None, **_):
    board = getattr(g, "board", None)
    if not board:
        return []
    removed = []
    for square, piece in list(board.piece_map().items()):
        removed.append({"symbol": piece.symbol(), "last_square": chess.square_name(square)})
        board.remove_piece_at(square)
    if tray is not None:
        tray.extend(removed)
    _mark_board_changed(g)
    _log(f"Cleared board to tray ({len(removed)} pieces).")
    return removed


def print_fen(g, **_):
    board = getattr(g, "board", None)
    if board:
        _log(f"Current FEN: {board.fen()}")


def validate_board(g, **_):
    warnings = validate_board_warnings(g)
    if warnings:
        for warning in warnings:
            _log(f"Board warning: {warning}")
    else:
        _log("Board validation passed.")
    return warnings


def validate_board_warnings(g):
    board = getattr(g, "board", None)
    if not board:
        return ["Board is not available."]

    warnings = []
    white_kings = 0
    black_kings = 0
    for square, piece in board.piece_map().items():
        if piece.piece_type == chess.KING:
            if piece.color == chess.WHITE:
                white_kings += 1
            else:
                black_kings += 1
        if piece.piece_type == chess.PAWN and chess.square_rank(square) in (0, 7):
            warnings.append(f"Pawn on invalid rank at {chess.square_name(square)}.")

    if white_kings == 0:
        warnings.append("White king is missing.")
    if black_kings == 0:
        warnings.append("Black king is missing.")
    if white_kings > 1:
        warnings.append("Multiple white kings.")
    if black_kings > 1:
        warnings.append("Multiple black kings.")

    try:
        status = board.status()
        if status:
            warnings.append(f"python-chess board status: {status}.")
    except Exception as exc:
        warnings.append(f"Could not compute board status: {exc}")

    try:
        if board.is_checkmate():
            warnings.append("Current side to move is checkmated.")
        elif board.is_stalemate():
            warnings.append("Current side to move is stalemated.")
        elif board.is_check():
            warnings.append("Current side to move is in check.")
    except Exception as exc:
        warnings.append(f"Could not inspect terminal/check state: {exc}")

    return warnings


def move_piece(g, from_square, to_square):
    board = getattr(g, "board", None)
    if not board or from_square == to_square:
        return None
    piece = board.piece_at(from_square)
    if not piece:
        return None
    target_piece = board.piece_at(to_square)
    board.remove_piece_at(from_square)
    if target_piece:
        board.set_piece_at(from_square, target_piece)
    board.set_piece_at(to_square, piece)
    _mark_board_changed(g)
    _log(f"Moved {piece.symbol()} from {chess.square_name(from_square)} to {chess.square_name(to_square)}.")
    return target_piece.symbol() if target_piece else None


def remove_piece_to_tray(g, square):
    board = getattr(g, "board", None)
    if not board:
        return None
    piece = board.piece_at(square)
    if not piece:
        return None
    board.remove_piece_at(square)
    _mark_board_changed(g)
    item = {"symbol": piece.symbol(), "last_square": chess.square_name(square)}
    _log(f"Removed {piece.symbol()} from {item['last_square']} to tray.")
    return item


def place_piece_from_symbol(g, square, symbol):
    if symbol not in PIECE_SYMBOLS:
        _log(f"Refusing invalid piece symbol {symbol!r}.")
        return None
    board = getattr(g, "board", None)
    if not board:
        return None
    old_piece = board.piece_at(square)
    board.set_piece_at(square, chess.Piece.from_symbol(symbol))
    _mark_board_changed(g)
    _log(f"Placed {symbol} on {chess.square_name(square)}.")
    if old_piece:
        return {"symbol": old_piece.symbol(), "last_square": chess.square_name(square)}
    return None


ACTION_MAP = {
    "register_win": register_win,
    "register_loss": register_loss,
    "register_stalemate": register_stalemate,
    "trigger_gamestate_display": trigger_gamestate_display,
    "reset_quest_status": reset_quest_status,
    "complete_quest": complete_quest,
    "start_quest": start_quest,
    "grant_quest_reward": grant_quest_reward,
    "force_turn": force_turn,
    "trigger_enemy_move": trigger_enemy_move,
    "setup_instant_checkmate": setup_instant_checkmate,
    "reset_board": reset_board,
    "clear_board_to_tray": clear_board_to_tray,
    "print_fen": print_fen,
    "validate_board": validate_board,
}


def run_action(g, action_name: str, **kwargs):
    action = ACTION_MAP.get(action_name)
    if not action:
        _log(f"Unknown action {action_name!r}.")
        return None
    return action(g, **kwargs)
