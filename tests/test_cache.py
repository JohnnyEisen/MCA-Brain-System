from brain_system.cache import LruTtlCache


def test_lru_eviction():
    c = LruTtlCache(max_entries=2, ttl_seconds=60)
    c.set("a", 1)
    c.set("b", 2)
    c.get("a")
    c.set("c", 3)
    assert c.get("b") is None
    assert c.get("a") == 1
    assert c.get("c") == 3
