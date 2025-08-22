from flask import Flask, request, jsonify
from flask_cors import CORS
from fetchai import fetch
from fetchai.registration import register_with_agentverse
from fetchai.communication import parse_message_from_agent, send_message_to_agent
import logging
import os
from dotenv import load_dotenv
from uagents_core.identity import Identity

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)
app = Flask(__name__)
CORS(app)


def init_client():
    """Initialize and register the client agent."""
    global client_identity
    try:
        client_identity = Identity.from_seed(
            "eyJhbGciOiJSUzI1NiJ9.eyJleHAiOjE3NjM2MDA1MTQsImlhdCI6MTc1NTgyNDUxNCwiaXNzIjoiZmV0Y2guYWkiLCJqdGkiOiI4YTNkOTEwNWJjMjk4ZGZmMDIyOWFkOGEiLCJzY29wZSI6ImF2Iiwic3ViIjoiODJkZWIzYWE3NzQ5ZGViYzhlMzA4YzkyYWJiNzY4NzEzNTk5N2EwMWRmM2UxZDU1In0.clv4zoxXjjOmCXxBaV4r7pqARVSJiOx_N-Ib7HqgfVxcbLzhgOki5gGCCmOZleOniK3yEdnTw8_UN5J2SCMxPoObsq9mXe8oMiiEKCa8VtdBoCoeXjpG0lzHwT4agT_3b3OILg0weUQlJ82U67Yz8irg-Ejh_iGHn6AUtzQnpibf3cjWjorF3mimETQzr8DfI0BR2kxHMKLv8kPGZxP-k1VQsYRi_iDfnNPaRZGfocN3a7vG3KkmtjHVEKzMapuvumQ7gQTm1dR_GBtBYAYsEQVmEvPRffKeVX8ky1IOG8lTjQCwL3j3rCixR--ayeWruEyNMGd3vFT40e0zej0PvQ",
            0,
        )
        logger.info(f"Client agent started with address: {client_identity.address}")
        logger.info("Quickstart agent registration complete!")

    except Exception as e:
        logger.error(f"Initialization error: {e}")
        raise
