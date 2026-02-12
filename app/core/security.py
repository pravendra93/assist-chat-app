from passlib.hash import argon2

def hash_api_key(api_key: str) -> str:
    """
    Hash API key using Argon2 (secure, slow, salted).
    """
    return argon2.hash(api_key)

def verify_api_key(api_key: str, hashed: str) -> bool:
    """
    Verify API key against Argon2 hash.
    Returns False if hash is malformed (e.g. legacy SHA256 hashes).
    """
    try:
        return argon2.verify(api_key, hashed)
    except (ValueError, TypeError):
        # Handle malformed or legacy hashes gracefully
        return False
