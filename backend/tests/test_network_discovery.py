from app.observer.network.discovery import discover_candidates


def test_map_id_is_safe_to_apply():
    candidates = discover_candidates({"mapId": 191105026})
    candidate = next(item for item in candidates if item.semantic == "map_id")
    assert candidate.value == 191105026
    assert candidate.auto_apply is True
    assert candidate.confidence >= 0.95


def test_nested_character_cell_is_player_cell():
    candidates = discover_candidates({"character": {"cellId": 287}})
    candidate = next(item for item in candidates if item.semantic == "player_cell")
    assert candidate.value == 287
    assert candidate.auto_apply is True


def test_generic_actor_cell_is_not_auto_applied():
    candidates = discover_candidates({"actors": [{"id": 9, "cellId": 214}]})
    candidate = next(item for item in candidates if item.path.endswith("cellId"))
    assert candidate.semantic == "cell_id"
    assert candidate.auto_apply is False


def test_out_of_range_cell_is_ignored():
    candidates = discover_candidates({"character": {"cellId": 999999}})
    assert not any(item.semantic == "player_cell" for item in candidates)
