from app.observer.network.endpoint_discovery import (
    EndpointCandidate,
    score_candidate,
    select_endpoint,
)


def candidate(
    host: str,
    port: int,
    pid: int = 10,
) -> EndpointCandidate:
    return EndpointCandidate(
        host=host,
        port=port,
        pid=pid,
        process_name="Dofus.exe",
    )


def test_custom_private_endpoint_beats_web_endpoint():
    private_game = candidate("192.168.1.20", 5555)
    web = candidate("203.0.113.10", 443)

    assert score_candidate(private_game) > score_candidate(web)


def test_unique_candidate_is_selected():
    selected, ranked, ambiguous = select_endpoint(
        [candidate("10.0.0.2", 5555)]
    )

    assert selected is not None
    assert selected.host == "10.0.0.2"
    assert ranked[0] == selected
    assert ambiguous is False


def test_clear_score_gap_is_auto_selected():
    selected, _ranked, ambiguous = select_endpoint(
        [
            candidate("192.168.1.20", 5555),
            candidate("203.0.113.10", 443),
        ]
    )

    assert selected is not None
    assert selected.port == 5555
    assert ambiguous is False


def test_similar_candidates_are_reported_ambiguous():
    selected, ranked, ambiguous = select_endpoint(
        [
            candidate("203.0.113.10", 5555, pid=1),
            candidate("198.51.100.20", 6666, pid=1),
        ]
    )

    assert selected is None
    assert len(ranked) == 2
    assert ambiguous is True


def test_duplicate_endpoint_entries_are_collapsed():
    c = candidate("127.0.0.1", 5555)

    selected, ranked, ambiguous = select_endpoint([c, c])

    assert selected == c
    assert len(ranked) == 1
    assert ambiguous is False
