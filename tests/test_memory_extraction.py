"""Memory extraction parser tests."""
from app.services.memory_service import MIN_CONFIDENCE, parse_extraction


def test_parse_valid_extraction():
    raw = ('{"should_remember": true, "memories": ['
           '{"type": "emotional", "content": "最近工作压力大", '
           '"importance": 4, "confidence": 0.86},'
           '{"type": "preference", "content": "喜欢被叫宝宝", '
           '"importance": 3, "confidence": 0.9}]}')
    memories = parse_extraction(raw)
    assert len(memories) == 2
    assert memories[0].type == "emotional"
    assert memories[0].importance == 4


def test_parse_should_not_remember():
    assert parse_extraction('{"should_remember": false, "memories": []}') == []


def test_parse_drops_low_confidence():
    raw = ('{"should_remember": true, "memories": ['
           f'{{"type": "episodic", "content": "...", "importance": 2, '
           f'"confidence": {MIN_CONFIDENCE - 0.1}}}]}}')
    assert parse_extraction(raw) == []


def test_parse_drops_invalid_type():
    raw = ('{"should_remember": true, "memories": ['
           '{"type": "nonsense", "content": "x", "importance": 3, "confidence": 0.9}]}')
    assert parse_extraction(raw) == []


def test_parse_tolerates_wrapping_text():
    raw = ('好的，这是结果：\n{"should_remember": true, "memories": ['
           '{"type": "profile", "content": "她叫小美", "importance": 5, '
           '"confidence": 0.95}]}\n以上。')
    memories = parse_extraction(raw)
    assert len(memories) == 1
    assert memories[0].type == "profile"


def test_parse_garbage_returns_empty():
    assert parse_extraction("complete garbage") == []
    assert parse_extraction("") == []


def test_parse_clamps_ranges():
    raw = ('{"should_remember": true, "memories": ['
           '{"type": "task", "content": "提醒交房租", "importance": 99, '
           '"confidence": 0.8}]}')
    memories = parse_extraction(raw)
    assert memories[0].importance == 5
