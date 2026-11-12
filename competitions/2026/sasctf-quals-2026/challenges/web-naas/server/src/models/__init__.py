from utils.database import engine, Base
from models.user import User
from models.billing import Billing
from models.storage import Storage
from models.processor import Processor
from models.published_record import PublishedRestoreRecord

# Creating table
Base.metadata.create_all(bind=engine)

default_billing = Billing(balance=0, granted=False)
