from rwa_access.http import _is_rate_limited


def test_rate_limit_markers_only_in_error_text():
    # Etherscan rate limit: status 0, the text is in `result`.
    assert _is_rate_limited({"status": "0", "message": "NOTOK", "result": "Max calls per sec rate limit reached (3/sec)"})
    # Verified source code that contains "rate limit" is a normal result.
    source = [{"SourceCode": "// The rate limiter enforces a rate limit per user", "ContractName": "GMTokenManager"}]
    assert not _is_rate_limited({"status": "1", "message": "OK", "result": source})
