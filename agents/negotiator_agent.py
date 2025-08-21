from uagents import Agent, Context, Model
from openai import OpenAI
import requests
import json
import re
import os
from typing import Optional, Dict, Any
from datetime import datetime
import time
from pydantic import Field
from dotenv import load_dotenv, find_dotenv


class NegotiationRequest(Model):
    message: str = Field(description="Buyer's message")
    buyer_id: str = Field(default="buyer", description="Buyer identifier")
    title: str = Field(description="Title of the item being sold")
    description: str = Field(description="Detailed description of the item")
    minimum_price: float = Field(description="Minimum acceptable price in Rupiah")
    maximum_price: float = Field(description="Maximum asking price in Rupiah")
    condition: str = Field(default="Kondisi baik", description="Item condition")
    location: str = Field(default="Jakarta", description="Item location")
    delivery_info: str = Field(default="COD/Pickup", description="Delivery options")


class NegotiationResponse(Model):
    message_to_buyer: str = Field(description="Response to buyer")
    message_to_seller: str = Field(description="Report to seller")
    deal_status: str = Field(description="Status of negotiation")
    counter_offer: float = Field(description="Counter offer amount in Rupiah")
    accepted: bool = Field(description="Whether deal was accepted")
    timestamp: int = Field(description="Response timestamp")


# Load API key from environment
load_dotenv(find_dotenv())

OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY", "")

# Create the marketplace negotiator agent
negotiator_agent = Agent(
    name="negotiator_agent",
    seed="marketplace_negotiator_seed",
    port=8000,
    mailbox=True,
    network='fetchai_testnet',
)

# Global storage for conversations
conversations = {}
stats = {"total_negotiations": 0, "deals_made": 0, "start_time": datetime.now()}


def generate_response_with_gpt(prompt: str) -> str:
    """Generate response using OpenRouter API"""
    try:
        response = requests.post(
            url="https://openrouter.ai/api/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {OPENROUTER_API_KEY}",
                "Content-Type": "application/json",
            },
            data=json.dumps(
                {
                    "model": "openai/gpt-3.5-turbo",
                    "messages": [
                        {
                            "role": "system",
                            "content": "You are a professional marketplace sales assistant for Indonesian online marketplace. Be friendly, professional, and strategic in your negotiations. Respond in the same language as the buyer's message (Indonesian or English). Use Indonesian Rupiah (Rp) for all prices.",
                        },
                        {"role": "user", "content": prompt},
                    ],
                    "max_tokens": 300,
                    "temperature": 0.7,
                }
            ),
        )

        response_data = response.json()
        if "choices" in response_data and len(response_data["choices"]) > 0:
            return response_data["choices"][0]["message"]["content"]
        else:
            return "Error: No content in API response"

    except Exception as e:
        return f"Error generating response: {str(e)}"


def parse_response(gpt_response: str) -> Dict[str, Any]:
    """Parse GPT response to extract structured information"""
    lines = gpt_response.split("\n")

    result = {
        "message_to_buyer": "",
        "message_to_seller": "",
        "deal_status": "ongoing",
        "counter_offer": 0.0,
        "accepted": False,
    }

    current_section = None
    for line in lines:
        line = line.strip()

        if line == "[message_to_buyer]":
            current_section = "message_to_buyer"
        elif line == "[message_to_seller]":
            current_section = "message_to_seller"
        elif line.startswith("[") and line.endswith("]"):
            current_section = None
        elif line and current_section:
            if current_section in ["message_to_buyer", "message_to_seller"]:
                result[current_section] += line + " "

    # Clean up messages
    result["message_to_buyer"] = result["message_to_buyer"].strip()
    result["message_to_seller"] = result["message_to_seller"].strip()

    # Analyze response for deal status
    response_lower = gpt_response.lower()

    # Check for deal acceptance
    if any(
        phrase in response_lower
        for phrase in [
            "deal",
            "sold",
            "agreed",
            "accept",
            "yours",
            "setuju",
            "sepakat",
            "jadi",
            "oke deal",
        ]
    ):
        result["deal_status"] = "deal_made"
        result["accepted"] = True
        price_match = re.search(
            r"(?:Rp\.?\s*)?(\d{1,3}(?:[.,]\d{3})*(?:[.,]\d{2})?)", gpt_response
        )
        if price_match:
            # Clean and convert price
            price_str = price_match.group(1).replace(",", "").replace(".", "")
            try:
                result["counter_offer"] = float(price_str)
            except ValueError:
                result["counter_offer"] = 0.0

    # Check for counter offers
    elif any(
        phrase in response_lower
        for phrase in [
            "counter",
            "how about",
            "consider",
            "meet",
            "gimana kalau",
            "bagaimana",
            "bisa",
        ]
    ):
        result["deal_status"] = "counter_offer"
        price_match = re.search(
            r"(?:Rp\.?\s*)?(\d{1,3}(?:[.,]\d{3})*(?:[.,]\d{2})?)", gpt_response
        )
        if price_match:
            price_str = price_match.group(1).replace(",", "").replace(".", "")
            try:
                result["counter_offer"] = float(price_str)
            except ValueError:
                result["counter_offer"] = 0.0

    # Check for rejection
    elif any(
        phrase in response_lower
        for phrase in [
            "too low",
            "cannot",
            "below",
            "sorry",
            "terlalu rendah",
            "tidak bisa",
            "maaf",
        ]
    ):
        result["deal_status"] = "rejected"

    # Check if seller action required
    elif any(
        phrase in response_lower for phrase in ["action required", "perlu tindakan"]
    ):
        result["deal_status"] = "needs_info"

    return result


def extract_offer_amount(message: str) -> Optional[float]:
    """Extract monetary offer from message (supports Rupiah format)"""
    patterns = [
        r"(?:Rp\.?\s*)?(\d{1,3}(?:[.,]\d{3})*(?:[.,]\d{2})?)",  # Rp1.000.000 or 1,000,000
        r"(\d+(?:[.,]\d{3})*)\s*(?:ribu|rb)",  # 500 ribu
        r"(\d+(?:[.,]\d{3})*)\s*(?:juta|jt)",  # 5 juta
        r"offer\s+(\d+(?:[.,]\d{3})*)",  # offer 1000000
        r"tawar\s+(\d+(?:[.,]\d{3})*)",  # tawar 1000000
    ]

    for i, pattern in enumerate(patterns):
        match = re.search(pattern, message.lower())
        if match:
            price_str = match.group(1).replace(",", "").replace(".", "")
            try:
                price = float(price_str)
                # Convert ribu/juta to full amount
                if i == 1:  # ribu pattern
                    price *= 1000
                elif i == 2:  # juta pattern
                    price *= 1000000
                return price
            except ValueError:
                continue
    return None


def format_rupiah(amount: float) -> str:
    """Format amount to Indonesian Rupiah"""
    if amount == 0:
        return "Rp0"

    # Convert to integer for formatting
    amount_int = int(amount)

    # Format with thousands separator
    formatted = f"{amount_int:,}".replace(",", ".")
    return f"Rp{formatted}"


def get_conversation_key(buyer_id: str, title: str) -> str:
    """Generate unique conversation key"""
    return f"{buyer_id}_{title.lower().replace(' ', '_')[:20]}"


def add_to_conversation(conversation_key: str, message: str, sender: str):
    """Add message to conversation history"""
    if conversation_key not in conversations:
        conversations[conversation_key] = []

    timestamp = datetime.now().strftime("%H:%M")
    conversations[conversation_key].append(f"[{timestamp}] {sender}: {message}")


def get_conversation_history(conversation_key: str) -> str:
    """Get recent conversation history"""
    if conversation_key in conversations:
        return "\n".join(conversations[conversation_key][-6:])
    return ""


def detect_language(message: str) -> str:
    """Detect if message is in Indonesian or English"""
    indonesian_words = [
        "apa",
        "yang",
        "ini",
        "itu",
        "saya",
        "kamu",
        "dengan",
        "untuk",
        "dari",
        "ke",
        "di",
        "pada",
        "adalah",
        "akan",
        "sudah",
        "belum",
        "bisa",
        "tidak",
        "ya",
        "tidak",
        "berapa",
        "harga",
        "jual",
        "beli",
        "tawar",
        "nego",
        "cod",
        "transfer",
        "kirim",
    ]

    message_lower = message.lower()
    indonesian_count = sum(1 for word in indonesian_words if word in message_lower)

    return "indonesian" if indonesian_count >= 2 else "english"


@negotiator_agent.on_rest_post("/negotiate", NegotiationRequest, NegotiationResponse)
async def negotiate(ctx: Context, req: NegotiationRequest) -> NegotiationResponse:
    """Handle marketplace negotiations for any item"""

    # Generate conversation key
    conversation_key = get_conversation_key(req.buyer_id, req.title)

    # Update stats
    stats["total_negotiations"] += 1

    # Add buyer message to conversation
    add_to_conversation(conversation_key, req.message, "Buyer")

    # Check for offer in message
    offer_amount = extract_offer_amount(req.message)

    # Get conversation context
    conversation_history = get_conversation_history(conversation_key)

    # Detect message language
    language = detect_language(req.message)

    # Calculate target price (75% between min and max)
    target_price = req.minimum_price + (req.maximum_price - req.minimum_price) * 0.75

    # Create negotiation prompt
    prompt = f"""
You are negotiating the sale of: {req.title}

ITEM DETAILS:
- Title: {req.title}
- Description: {req.description}
- Maximum Price: {format_rupiah(req.maximum_price)}
- Target Price: {format_rupiah(target_price)} (aim for this)
- Minimum Price: {format_rupiah(req.minimum_price)} (never go below this)
- Condition: {req.condition}
- Location: {req.location}
- Delivery: {req.delivery_info}

CONVERSATION HISTORY:
{conversation_history}

BUYER MESSAGE: {req.message}
LANGUAGE DETECTED: {language}

NEGOTIATION RULES:
1. Target price: {format_rupiah(target_price)} - try to get this or close to it
2. Minimum price: {format_rupiah(req.minimum_price)} - never go below this
3. Maximum price: {format_rupiah(req.maximum_price)} - starting point
4. If offer >= target: accept enthusiastically
5. If offer between minimum and target: negotiate upward
6. If offer < minimum: politely decline and counter
7. Respond in the same language as the buyer ({language})
8. Use Indonesian Rupiah format (Rp1.000.000) for all prices
9. Be friendly and professional
10. If buyer asks general questions, provide helpful information about the item

RESPONSE FORMAT:
[message_to_buyer]
Your response to the buyer in {language}

[message_to_seller]
Your report to the seller in English (start with [INFO] or [ACTION REQUIRED])
"""

    # Get AI response
    gpt_response = generate_response_with_gpt(prompt)
    ctx.logger.info(f"GPT Response: {gpt_response}")

    # Parse response
    parsed = parse_response(gpt_response)

    # Add seller response to conversation
    if parsed["message_to_buyer"]:
        add_to_conversation(conversation_key, parsed["message_to_buyer"], "Seller")

    # Update deal statistics
    if parsed["deal_status"] == "deal_made":
        stats["deals_made"] += 1

    # Log activity
    ctx.logger.info(f"Negotiation: {req.buyer_id} for {req.title}")
    ctx.logger.info(f"Status: {parsed['deal_status']}")
    if offer_amount:
        ctx.logger.info(f"Offer detected: {format_rupiah(offer_amount)}")
    if parsed["counter_offer"] > 0:
        ctx.logger.info(f"Counter offer: {format_rupiah(parsed['counter_offer'])}")

    return NegotiationResponse(
        message_to_buyer=parsed["message_to_buyer"],
        message_to_seller=parsed["message_to_seller"],
        deal_status=parsed["deal_status"],
        counter_offer=parsed["counter_offer"],
        accepted=parsed["accepted"],
        timestamp=int(time.time()),
    )


@negotiator_agent.on_event("startup")
async def startup_handler(ctx: Context):
    ctx.logger.info("Marketplace Negotiator Agent started")
    ctx.logger.info(f"Agent address: {ctx.agent.address}")
    ctx.logger.info("Available endpoint: POST /negotiate")
    ctx.logger.info("Supporting Indonesian Rupiah and bilingual conversations")


if __name__ == "__main__":
    print("Starting Marketplace Negotiator Agent...")
    print("Available endpoint: POST http://localhost:8000/negotiate")
    print("Supporting Indonesian Rupiah and Indonesian/English languages")
    negotiator_agent.run()
