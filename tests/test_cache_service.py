from text_to_sql_agent.services.cache_service import CacheService


def test_same_input_generates_same_key():
    cache = CacheService()

    key1 = cache.build_key(
        user_id="user_1",
        session_id="session_1",
        question="What is total revenue?",
    )

    key2 = cache.build_key(
        user_id="user_1",
        session_id="session_1",
        question="What is total revenue?",
    )

    assert key1 == key2


def test_question_normalization():
    cache = CacheService()

    key1 = cache.build_key(
        user_id="user_1",
        session_id="session_1",
        question="What is total revenue?",
    )

    key2 = cache.build_key(
        user_id="user_1",
        session_id="session_1",
        question="  WHAT   IS   TOTAL   REVENUE?  ",
    )

    assert key1 == key2


def test_different_users_generate_different_keys():
    cache = CacheService()

    key1 = cache.build_key(
        user_id="user_1",
        session_id="session_1",
        question="What is total revenue?",
    )

    key2 = cache.build_key(
        user_id="user_2",
        session_id="session_1",
        question="What is total revenue?",
    )

    assert key1 != key2


def test_different_sessions_generate_different_keys():
    cache = CacheService()

    key1 = cache.build_key(
        user_id="user_1",
        session_id="session_1",
        question="What is total revenue?",
    )

    key2 = cache.build_key(
        user_id="user_1",
        session_id="session_2",
        question="What is total revenue?",
    )

    assert key1 != key2


def test_different_questions_generate_different_keys():
    cache = CacheService()

    key1 = cache.build_key(
        user_id="user_1",
        session_id="session_1",
        question="What is total revenue?",
    )

    key2 = cache.build_key(
        user_id="user_1",
        session_id="session_1",
        question="What is total trips?",
    )

    assert key1 != key2