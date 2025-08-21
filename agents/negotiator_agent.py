from uagents import Agent, Context
from openai import OpenAI
import requests
import json
import re
import os
from typing import Optional, Dict, Any
from datetime import datetime
import time
from pydantic import BaseModel

class BuyerMessageRequest(BaseModel):
    message: str
    buyer_id: str = "web_client"


class NegotiationOfferRequest(BaseModel):
    offer_amount: float
    message: str
    buyer_id: str = "web_client"


class NegotiationResponseModel(BaseModel):
    message_to_buyer: str
    message_to_seller: str
    deal_status: str = (
        "ongoing"  # ongoing, deal_made, rejected, counter_offer, needs_info
    )
    counter_offer: float = 0.0
    accepted: bool = False
    timestamp: int
    agent_address: str


class ItemUpdateRequest(BaseModel):
    name: str
    listing_price: float
    target_price: float
    minimum_price: float
    condition: str
    known_flaws: str = "None"
    selling_points: str
    reason_for_selling: str
    pickup_info: str


class ConversationHistoryResponse(BaseModel):
    buyer_id: str
    conversation_history: list
    total_messages: int
    last_activity: str
    timestamp: int


class AgentStatsResponse(BaseModel):
    total_inquiries: int
    offers_received: int
    deals_made: int
    average_final_price: float
    active_conversations: int
    uptime_hours: float
    current_item: str
    timestamp: int


class ItemDetails(BaseModel):
    name: str
    listing_price: float
    target_price: float
    minimum_price: float
    condition: str
    known_flaws: str
    selling_points: str
    reason_for_selling: str
    pickup_info: str


# Load API key from environment or use hardcoded value
OPENROUTER_API_KEY = os.getenv(
    "OPENROUTER_API_KEY",
    "",
)

openai_client = OpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key=OPENROUTER_API_KEY,
)

# Create the marketplace negotiator agent
negotiator_agent = Agent(
    name="adol_negotiatior_agent",
    seed="marketplace_negotiator_hackathon_hunters",
    port=8000,
    endpoint=["http://localhost:8000/submit"],
    mailbox=True,
)

ITEM_DETAILS = {
    "name": "Vintage Oak Coffee Table",
    "listing_price": 150,
    "target_price": 130,
    "minimum_price": 100,
    "condition": "Good condition, with a few minor scratches on the surface. Structurally very sound.",
    "known_flaws": "One small water ring on the top right corner.",
    "selling_points": "Solid wood, beautiful mid-century modern design, great storage shelf underneath.",
    "reason_for_selling": "I'm redecorating and it no longer fits my space.",
    "pickup_info": "Pickup only from downtown. I cannot deliver.",
}

# Conversation history storage (in-memory)
conversation_history = {}  # Dictionary to store conversation per buyer
negotiation_stats = {
    "total_inquiries": 0,
    "offers_received": 0,
    "deals_made": 0,
    "average_final_price": 0.0,
    "start_time": datetime.now(),
}


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
                            "content": """You are Marketplace Pro, an expert AI sales assistant and intermediary for Facebook Marketplace. Your persona is friendly, professional, and an expert negotiator. Follow the exact protocol provided in the prompt.""",
                        },
                        {"role": "user", "content": prompt},
                    ],
                    "max_tokens": 400,
                    "temperature": 0.7,
                }
            ),
        )

        response_data = response.json()

        if "choices" in response_data and len(response_data["choices"]) > 0:
            content = response_data["choices"][0]["message"]["content"]
            return content
        else:
            return "Error: No content in API response"

    except Exception as e:
        return f"Error generating response: {str(e)}"


def parse_gpt_response(gpt_response: str) -> Dict[str, Any]:
    """Parse the GPT response to extract buyer and seller messages"""
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

    # Analyze response for negotiation details
    response_lower = gpt_response.lower()

    # Check if deal is made
    if any(
        phrase in response_lower
        for phrase in ["deal", "sold", "agreed", "accept your offer", "it's yours"]
    ):
        result["deal_status"] = "deal_made"
        result["accepted"] = True

        # Extract final price
        price_match = re.search(r"\$(\d+(?:\.\d{2})?)", gpt_response)
        if price_match:
            result["counter_offer"] = float(price_match.group(1))

    # Check for counter offers
    elif any(
        phrase in response_lower
        for phrase in ["counter", "how about", "would you consider", "meet me at"]
    ):
        result["deal_status"] = "counter_offer"

        # Extract counter offer amount
        price_match = re.search(r"\$(\d+(?:\.\d{2})?)", gpt_response)
        if price_match:
            result["counter_offer"] = float(price_match.group(1))

    # Check for rejection
    elif any(
        phrase in response_lower
        for phrase in ["too low", "cannot accept", "below my minimum", "sorry"]
    ):
        result["deal_status"] = "rejected"

    # Check if seller action required
    elif "action required" in response_lower:
        result["deal_status"] = "needs_info"

    return result


def extract_offer_amount(message: str) -> Optional[float]:
    """Extract monetary offer from buyer message"""
    patterns = [
        r"\$(\d+(?:\.\d{2})?)",  # $100 or $100.50
        r"(\d+(?:\.\d{2})?)\s*dollars?",  # 100 dollars
        r"offer\s+(\d+(?:\.\d{2})?)",  # offer 100
        r"pay\s+(\d+(?:\.\d{2})?)",  # pay 100
    ]

    for pattern in patterns:
        match = re.search(pattern, message.lower())
        if match:
            return float(match.group(1))

    return None


def get_conversation_context(buyer_id: str) -> str:
    """Get conversation history for a specific buyer"""
    if buyer_id in conversation_history:
        return "\n".join(conversation_history[buyer_id][-6:])  # Last 6 messages
    return ""


def add_to_conversation(buyer_id: str, message: str, sender: str):
    """Add message to conversation history"""
    if buyer_id not in conversation_history:
        conversation_history[buyer_id] = []

    timestamp = datetime.now().strftime("%H:%M")
    conversation_history[buyer_id].append(f"[{timestamp}] {sender}: {message}")


# REST ENDPOINTS


@negotiator_agent.on_rest_get("/status", AgentStatsResponse)
async def get_agent_status(ctx: Context) -> Dict[str, Any]:
    """GET endpoint to check agent status and negotiation statistics"""
    ctx.logger.info("📊 Received GET request for agent status")

    uptime_delta = datetime.now() - negotiation_stats["start_time"]
    uptime_hours = uptime_delta.total_seconds() / 3600

    return {
        "total_inquiries": negotiation_stats["total_inquiries"],
        "offers_received": negotiation_stats["offers_received"],
        "deals_made": negotiation_stats["deals_made"],
        "average_final_price": round(negotiation_stats["average_final_price"], 2),
        "active_conversations": len(conversation_history),
        "uptime_hours": round(uptime_hours, 2),
        "current_item": ITEM_DETAILS["name"],
        "timestamp": int(time.time()),
    }


@negotiator_agent.on_rest_get("/item", ItemDetails)
async def get_item_details(ctx: Context) -> Dict[str, Any]:
    """GET endpoint to retrieve current item details"""
    ctx.logger.info("🏪 Received GET request for item details")

    return ITEM_DETAILS


@negotiator_agent.on_rest_post("/item", ItemUpdateRequest, ItemDetails)
async def update_item_details(ctx: Context, req: ItemUpdateRequest) -> ItemDetails:
    """POST endpoint to update item details"""
    ctx.logger.info(f"🔄 Updating item details: {req.name}")

    # Update global item details
    global ITEM_DETAILS
    ITEM_DETAILS.update(
        {
            "name": req.name,
            "listing_price": req.listing_price,
            "target_price": req.target_price,
            "minimum_price": req.minimum_price,
            "condition": req.condition,
            "known_flaws": req.known_flaws,
            "selling_points": req.selling_points,
            "reason_for_selling": req.reason_for_selling,
            "pickup_info": req.pickup_info,
        }
    )

    # Clear conversation history for new item
    global conversation_history
    conversation_history = {}

    # Reset stats for new item
    negotiation_stats.update(
        {
            "total_inquiries": 0,
            "offers_received": 0,
            "deals_made": 0,
            "average_final_price": 0.0,
            "start_time": datetime.now(),
        }
    )

    ctx.logger.info(f"✅ Updated item details for: {req.name}")

    return ItemDetails(**ITEM_DETAILS)


@negotiator_agent.on_rest_post(
    "/negotiate", BuyerMessageRequest, NegotiationResponseModel
)
async def handle_buyer_message(
    ctx: Context, req: BuyerMessageRequest
) -> NegotiationResponseModel:
    """POST endpoint to handle buyer messages and negotiate"""
    buyer_id = req.buyer_id

    ctx.logger.info(f"📥 Received message from buyer {buyer_id}: {req.message}")

    # Update stats
    negotiation_stats["total_inquiries"] += 1

    # Add buyer message to conversation history
    add_to_conversation(buyer_id, req.message, "Buyer")

    # Check if this is an offer
    offer_amount = extract_offer_amount(req.message)
    if offer_amount:
        negotiation_stats["offers_received"] += 1
        ctx.logger.info(f"💰 Detected offer: ${offer_amount}")

    # Get conversation context
    context = get_conversation_context(buyer_id)

    # Create comprehensive prompt with conversation history
    prompt = f"""
    [ROLE] You are Marketplace Pro, an expert AI sales assistant for Facebook Marketplace.
    
    [GOAL] Your primary goal is to sell the item for ${ITEM_DETAILS['target_price']}, but you must never go below ${ITEM_DETAILS['minimum_price']}.
    
    [ITEM_DETAILS]
    Item Name: {ITEM_DETAILS['name']}
    Listing Price: ${ITEM_DETAILS['listing_price']}
    Target Price: ${ITEM_DETAILS['target_price']}
    Minimum Price: ${ITEM_DETAILS['minimum_price']}
    Condition: {ITEM_DETAILS['condition']}
    Known Flaws: {ITEM_DETAILS['known_flaws']}
    Key Selling Points: {ITEM_DETAILS['selling_points']}
    Reason for Selling: {ITEM_DETAILS['reason_for_selling']}
    Pickup Info: {ITEM_DETAILS['pickup_info']}
    
    [CONVERSATION_HISTORY]
    {context}
    
    [CURRENT_MESSAGE_FROM_BUYER]
    {req.message}
    
    [NEGOTIATION_INSTRUCTIONS]
    1. If buyer offers below ${ITEM_DETAILS['minimum_price']}: Politely decline and suggest a counter-offer closer to ${ITEM_DETAILS['target_price']}
    2. If buyer offers between ${ITEM_DETAILS['minimum_price']}-${ITEM_DETAILS['target_price']}: Try to negotiate upward, but be willing to accept reasonable offers
    3. If buyer offers ${ITEM_DETAILS['target_price']} or above: Accept the deal enthusiastically
    4. Always be friendly, professional, and highlight the item's value
    5. If you need more information, ask specific questions
    
    Generate response using this EXACT format:
    [message_to_buyer]
    (Your response to the buyer - be conversational and professional)
    
    [message_to_seller]
    (Your report to the seller - start with [INFO] or [ACTION REQUIRED])
    
    Follow the Facebook Marketplace negotiation strategy.
    """

    # Get GPT response
    gpt_response = generate_response_with_gpt(prompt)
    ctx.logger.info(f"🤖 AI Response generated")

    # Parse the response
    parsed_response = parse_gpt_response(gpt_response)

    # Add seller response to conversation history
    if parsed_response["message_to_buyer"]:
        add_to_conversation(buyer_id, parsed_response["message_to_buyer"], "Seller")

    # Handle deal status updates
    if parsed_response["deal_status"] == "deal_made":
        negotiation_stats["deals_made"] += 1
        if parsed_response["counter_offer"] > 0:
            negotiation_stats["average_final_price"] = (
                negotiation_stats["average_final_price"]
                * (negotiation_stats["deals_made"] - 1)
                + parsed_response["counter_offer"]
            ) / negotiation_stats["deals_made"]
        ctx.logger.info(
            f"🎉 DEAL MADE! Final price: ${parsed_response['counter_offer']}"
        )

    elif parsed_response["deal_status"] == "counter_offer":
        ctx.logger.info(f"🔄 Counter offer made: ${parsed_response['counter_offer']}")

    elif parsed_response["deal_status"] == "rejected":
        ctx.logger.info("❌ Offer rejected - below minimum price")

    elif parsed_response["deal_status"] == "needs_info":
        ctx.logger.info("⚠️ Seller action required!")

    # Log seller report
    if parsed_response["message_to_seller"]:
        ctx.logger.info(f"📊 SELLER REPORT: {parsed_response['message_to_seller']}")

    return NegotiationResponseModel(
        message_to_buyer=parsed_response["message_to_buyer"],
        message_to_seller=parsed_response["message_to_seller"],
        deal_status=parsed_response["deal_status"],
        counter_offer=parsed_response["counter_offer"],
        accepted=parsed_response["accepted"],
        timestamp=int(time.time()),
        agent_address=ctx.agent.address,
    )


@negotiator_agent.on_rest_post(
    "/offer", NegotiationOfferRequest, NegotiationResponseModel
)
async def handle_formal_offer(
    ctx: Context, req: NegotiationOfferRequest
) -> NegotiationResponseModel:
    """POST endpoint to handle formal negotiation offers"""
    buyer_id = req.buyer_id

    ctx.logger.info(
        f"💰 Received formal offer from buyer {buyer_id}: ${req.offer_amount}"
    )
    ctx.logger.info(f"📝 Offer message: {req.message}")

    # Update stats
    negotiation_stats["offers_received"] += 1

    # Add to conversation history
    add_to_conversation(
        buyer_id, f"${req.offer_amount} - {req.message}", "Buyer (Formal Offer)"
    )

    # Determine response based on offer amount
    if req.offer_amount >= ITEM_DETAILS["target_price"]:
        # Accept offer - at or above target
        message_to_buyer = f"Perfect! I accept your offer of ${req.offer_amount}. When would you like to pick up the {ITEM_DETAILS['name']}?"
        message_to_seller = f"[INFO] DEAL MADE! Buyer {buyer_id} offered ${req.offer_amount} which meets our target price. Arrange pickup details."
        deal_status = "deal_made"
        accepted = True
        counter_offer = req.offer_amount

        negotiation_stats["deals_made"] += 1
        negotiation_stats["average_final_price"] = (
            negotiation_stats["average_final_price"]
            * (negotiation_stats["deals_made"] - 1)
            + req.offer_amount
        ) / negotiation_stats["deals_made"]

        ctx.logger.info(f"🎉 ACCEPTED OFFER: ${req.offer_amount} (at/above target)")

    elif req.offer_amount >= ITEM_DETAILS["minimum_price"]:
        # Counter offer - between minimum and target
        counter_amount = min(
            ITEM_DETAILS["target_price"],
            req.offer_amount
            + ((ITEM_DETAILS["target_price"] - req.offer_amount) * 0.5),
        )

        message_to_buyer = f"Thanks for your offer! I was hoping to get closer to ${counter_amount}. It's a really quality piece with {ITEM_DETAILS['selling_points']}. Would that work for you?"
        message_to_seller = f"[INFO] Buyer {buyer_id} offered ${req.offer_amount}. I countered with ${counter_amount}. This is within negotiable range."
        deal_status = "counter_offer"
        accepted = False
        counter_offer = counter_amount

        ctx.logger.info(
            f"🔄 COUNTER OFFER: ${counter_amount} (original: ${req.offer_amount})"
        )

    else:
        # Reject offer - below minimum
        message_to_buyer = f"I appreciate your interest, but ${req.offer_amount} is a bit too low for me. The lowest I could go is ${ITEM_DETAILS['minimum_price']} given the quality and condition. Would you consider that?"
        message_to_seller = f"[INFO] Buyer {buyer_id} offered ${req.offer_amount} which is below our minimum of ${ITEM_DETAILS['minimum_price']}. I suggested our minimum price."
        deal_status = "rejected"
        accepted = False
        counter_offer = ITEM_DETAILS["minimum_price"]

        ctx.logger.info(
            f"❌ REJECTED OFFER: ${req.offer_amount} (below minimum ${ITEM_DETAILS['minimum_price']})"
        )

    # Add response to conversation history
    add_to_conversation(buyer_id, message_to_buyer, "Seller (Formal Response)")

    return NegotiationResponseModel(
        message_to_buyer=message_to_buyer,
        message_to_seller=message_to_seller,
        deal_status=deal_status,
        counter_offer=counter_offer,
        accepted=accepted,
        timestamp=int(time.time()),
        agent_address=ctx.agent.address,
    )


@negotiator_agent.on_rest_get("/conversations", Dict)
async def get_all_conversations(ctx: Context) -> Dict[str, Any]:
    """GET endpoint to retrieve all conversation histories"""
    ctx.logger.info("📋 Received GET request for all conversations")

    conversations_summary = {}
    for buyer_id, messages in conversation_history.items():
        if messages:
            conversations_summary[buyer_id] = {
                "total_messages": len(messages),
                "last_message": messages[-1] if messages else "No messages",
                "first_contact": messages[0] if messages else "No messages",
            }

    return {
        "total_conversations": len(conversation_history),
        "conversations": conversations_summary,
        "timestamp": int(time.time()),
    }


@negotiator_agent.on_rest_get("/conversation/{buyer_id}", ConversationHistoryResponse)
async def get_conversation_history(ctx: Context, buyer_id: str) -> Dict[str, Any]:
    """GET endpoint to retrieve conversation history for a specific buyer"""
    ctx.logger.info(f"📋 Received GET request for conversation with buyer {buyer_id}")

    if buyer_id in conversation_history:
        messages = conversation_history[buyer_id]
        last_activity = messages[-1].split("]")[0][1:] if messages else "No activity"

        return {
            "buyer_id": buyer_id,
            "conversation_history": messages,
            "total_messages": len(messages),
            "last_activity": last_activity,
            "timestamp": int(time.time()),
        }
    else:
        return {
            "buyer_id": buyer_id,
            "conversation_history": [],
            "total_messages": 0,
            "last_activity": "No conversation found",
            "timestamp": int(time.time()),
        }


@negotiator_agent.on_event("startup")
async def startup_handler(ctx: Context):
    ctx.logger.info(f"🚀 REST-based Marketplace Negotiator Agent started!")
    ctx.logger.info(f"📍 Agent address: {ctx.agent.address}")
    ctx.logger.info(
        f"🏪 Currently selling: {ITEM_DETAILS['name']} for ${ITEM_DETAILS['listing_price']}"
    )
    ctx.logger.info(
        f"🎯 Target: ${ITEM_DETAILS['target_price']} | Minimum: ${ITEM_DETAILS['minimum_price']}"
    )
    ctx.logger.info("🌐 REST API endpoints available:")
    ctx.logger.info("   GET  /status - Agent statistics")
    ctx.logger.info("   GET  /item - Item details")
    ctx.logger.info("   POST /item - Update item details")
    ctx.logger.info("   POST /negotiate - Send buyer message")
    ctx.logger.info("   POST /offer - Send formal offer")
    ctx.logger.info("   GET  /conversations - All conversations")
    ctx.logger.info("   GET  /conversation/{buyer_id} - Specific conversation")


if __name__ == "__main__":
    print("🚀 Starting REST-based Marketplace Negotiator Agent...")
    print(f"🏪 Selling: {ITEM_DETAILS['name']} for ${ITEM_DETAILS['listing_price']}")
    print(
        f"🎯 Target: ${ITEM_DETAILS['target_price']} | Minimum: ${ITEM_DETAILS['minimum_price']}"
    )
    print("\n📡 Available REST endpoints:")
    print("   GET  http://localhost:8000/status")
    print("   GET  http://localhost:8000/item")
    print("   POST http://localhost:8000/item")
    print("   POST http://localhost:8000/negotiate")
    print("   POST http://localhost:8000/offer")
    print("   GET  http://localhost:8000/conversations")
    print("   GET  http://localhost:8000/conversation/{buyer_id}")
    print("\n🔥 Enhanced with REST API functionality!")
    negotiator_agent.run()
