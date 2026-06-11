import secrets
import string

from sqlalchemy.orm import Session

from merlin.db.models import ShareToken


def _gen_token() -> str:
    alphabet = string.ascii_lowercase + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(8))


def create_share_token(db: Session, knowledge_item_id: str) -> str:
    token = _gen_token()
    db.add(ShareToken(token=token, knowledge_item_id=knowledge_item_id))
    db.commit()
    return token


def get_item_id_for_token(db: Session, token: str) -> str | None:
    row = db.query(ShareToken).filter(ShareToken.token == token).first()
    return row.knowledge_item_id if row else None
