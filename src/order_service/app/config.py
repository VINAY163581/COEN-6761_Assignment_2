"""_summary_
Configuration module for the order service.
This module loads environment variables from a .env file and provides a Config class
to access these variables.

Author: 
    @TheBarzani
"""

import os
from dataclasses import dataclass
from dotenv import load_dotenv
load_dotenv()

@dataclass
class Config:
    """
    Configuration class for the order service.
    This class loads environment variables from a .env file and provides attributes
    to access these variables.
    Attributes:
        MONGO_URI (str): The URI for connecting to the MongoDB database.
        DATABASE_NAME (str): The name of the MongoDB database to use.
        RABBITMQ_QUEUE_NAME (str): The name of the RabbitMQ queue to consume events from.
    """
    MONGO_URI = os.getenv("MONGO_URI")
    # Keep order data isolated in its own DB unless explicitly overridden.
    DATABASE_NAME = os.getenv("ORDER_DATABASE_NAME") or os.getenv("DATABASE_NAME") or "orderdb"
    RABBITMQ_QUEUE_NAME = os.getenv("RABBITMQ_QUEUE_NAME")
