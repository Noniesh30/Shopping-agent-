import os
from dotenv import load_dotenv

load_dotenv()
SECRET_KEY = os.environ["MEMORY_HMAC_SECRET"].encode("utf-8")