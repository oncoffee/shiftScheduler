from passlib.context import CryptContext

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_token(token: str) -> str:
    return pwd_context.hash(token)


def verify_token(token: str, hashed: str) -> bool:
    return pwd_context.verify(token, hashed)
