import hashlib


def challenge_response(challenge_code: str, verification_token: str, endpoint: str) -> str:
    raw = f"{challenge_code}{verification_token}{endpoint}"
    return hashlib.sha256(raw.encode()).hexdigest()
