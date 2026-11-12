import uuid
import copy

from sqlalchemy import select
from resource.default import DefaultResource
from models.billing import Billing
from models import default_billing


class BillingResource(DefaultResource):
    def get(self, _user_id: int, _billing_id: str) -> Billing:
        return (
            self._db_session.query(Billing)
            .filter_by(uid=_billing_id, user_id=_user_id)
            .first()
        )

    def list(self, _user_id: int) -> list[str]:
        return self._db_session.scalars(
            select(Billing.uid).filter_by(user_id=_user_id)
        ).all()

    def create(self, _user_id: int, _billing: Billing | None = None) -> Billing:
        if _billing is None:
            _billing = copy.deepcopy(default_billing)
        _billing.uid = str(uuid.uuid4())
        _billing.user_id = _user_id

        self._save(_billing)
        return _billing

    def grant(self, _billing: Billing) -> Billing:
        _billing.balance += 45
        _billing.granted = True
        self._save(_billing)

    def pay(self, _billing: Billing, price: int):
        _billing.balance -= price
        self._save(_billing)

    def _save(self, _billing: Billing) -> None:
        self._db_session.add(_billing)
        self._db_session.commit()


billing_resource = BillingResource()
