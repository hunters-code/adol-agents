import os
import re
import logging
from datetime import datetime, timezone
from uuid import uuid4
from typing import Dict, Optional
from uagents import Agent, Context, Protocol, Model
from uagents_core.contrib.protocols.chat import (
    ChatMessage,
    ChatAcknowledgement,
    TextContent,
    EndSessionContent,
    chat_protocol_spec,
)
from openai import OpenAI
import aiohttp

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Environment variables
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "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")
AGENT_SEED = os.getenv("AGENT_SEED", "marketplace_negotiator_chat_seed")
AGENT_PORT = int(os.getenv("AGENT_PORT", "8000"))
ICP_CANISTER_URL = os.getenv("ICP_CANISTER_URL", "https://ujk5g-liaaa-aaaam-aeocq-cai.ic0.app")

# Initialize OpenAI client with OpenRouter
client = OpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key=OPENROUTER_API_KEY,
)

# Create the marketplace negotiator agent with chat protocol
agent = Agent(
    name="marketplace_negotiator",
    seed=AGENT_SEED,
    port=AGENT_PORT,
    endpoint=[f"http://localhost:{AGENT_PORT}/submit"],
    mailbox=True,
    publish_agent_details=True,
)

# Initialize chat protocol
chat_proto = Protocol(spec=chat_protocol_spec)

# Global state management
item_details = {}
seller_address = None

# ICP Backend Integration Functions
async def save_conversation_to_icp(conversation_id: str, conversation_data: dict):
    """Save conversation state to ICP canister"""
    try:
        async with aiohttp.ClientSession() as session:
            payload = {
                "conversation_id": conversation_id,
                "data": conversation_data,
                "timestamp": datetime.now().isoformat()
            }
            
            async with session.post(
                f"{ICP_CANISTER_URL}/api/conversations",
                json=payload,
                headers={"Content-Type": "application/json"},
                timeout=aiohttp.ClientTimeout(total=10)
            ) as response:
                if response.status == 200:
                    logger.info(f"✅ Conversation {conversation_id} saved to ICP")
                    return True
                else:
                    logger.error(f"❌ Failed to save to ICP: {response.status}")
                    return False
    except Exception as e:
        logger.error(f"❌ Error saving to ICP: {e}")
        return False

async def load_conversation_from_icp(conversation_id: str) -> Optional[dict]:
    """Load conversation state from ICP canister"""
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                f"{ICP_CANISTER_URL}/api/conversations/{conversation_id}",
                timeout=aiohttp.ClientTimeout(total=10)
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    logger.info(f"✅ Conversation {conversation_id} loaded from ICP")
                    return data.get("data", {})
                elif response.status == 404:
                    logger.info(f"📝 New conversation {conversation_id}")
                    return {"messages": [], "offers": [], "status": "active"}
                else:
                    logger.error(f"❌ Failed to load from ICP: {response.status}")
                    return None
    except Exception as e:
        logger.error(f"❌ Error loading from ICP: {e}")
        return None

async def save_message_to_icp(conversation_id: str, message_data: dict):
    """Save individual message to ICP canister"""
    try:
        async with aiohttp.ClientSession() as session:
            payload = {
                "conversation_id": conversation_id,
                "message": message_data,
                "timestamp": datetime.now().isoformat()
            }
            
            async with session.post(
                f"{ICP_CANISTER_URL}/api/messages",
                json=payload,
                headers={"Content-Type": "application/json"},
                timeout=aiohttp.ClientTimeout(total=10)
            ) as response:
                if response.status == 200:
                    logger.info(f"💾 Message saved to ICP for conversation {conversation_id}")
                    return True
                else:
                    logger.error(f"❌ Failed to save message to ICP: {response.status}")
                    return False
    except Exception as e:
        logger.error(f"❌ Error saving message to ICP: {e}")
        return False

async def get_conversation_history_from_icp(conversation_id: str) -> list:
    """Get conversation history from ICP canister"""
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                f"{ICP_CANISTER_URL}/api/conversations/{conversation_id}/history",
                timeout=aiohttp.ClientTimeout(total=10)
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    return data.get("messages", [])
                else:
                    logger.warning(f"⚠️ Could not load history from ICP: {response.status}")
                    return []
    except Exception as e:
        logger.error(f"❌ Error loading history from ICP: {e}")
        return []

# Message models for structured communication
class ItemSetup(Model):
    item_name: str
    listing_price: float
    target_price: float
    minimum_price: float
    condition: str
    known_flaws: str
    key_selling_points: str
    reason_for_selling: str
    pickup_delivery_info: str
    seller_address: str

class NegotiationReport(Model):
    conversation_id: str
    buyer_address: str
    current_offer: Optional[float]
    action_type: str  # INFO or ACTION_REQUIRED
    message: str

# Marketplace negotiation prompt template
NEGOTIATION_PROMPT = """
You are Marketplace Pro, an expert AI sales assistant managing Facebook Marketplace negotiations.

ITEM DETAILS:
- Name: {item_name}
- Listed: ${listing_price} | Target: ${target_price} | Minimum: ${minimum_price}
- Condition: {condition}
- Flaws: {known_flaws}
- Selling Points: {key_selling_points}
- Pickup Info: {pickup_delivery_info}

RULES:
1. NEVER go below ${minimum_price}
2. Aim for ${target_price}
3. Be friendly but professional
4. If unsure of details, say you'll check with the seller
5. Use language based on buyer language

BUYER MESSAGE: "{buyer_message}"

CONVERSATION HISTORY: {conversation_history}

Respond naturally in under 100 words as Marketplace Pro would.
"""

class MarketplaceNegotiator:
    """Enhanced marketplace negotiation with chat protocol"""
    
    @staticmethod
    def extract_price_from_message(message: str) -> Optional[float]:
        """Extract price from buyer message"""
        price_patterns = [
            r"\$(\d+(?:\.\d{1,2})?)",
            r"(\d+(?:\.\d{1,2})?) dollars?",
            r"offer (\d+(?:\.\d{1,2})?)",
            r"pay (\d+(?:\.\d{1,2})?)",
            r"(\d+(?:\.\d{1,2})?) bucks"
        ]
        
        for pattern in price_patterns:
            match = re.search(pattern, message.lower())
            if match:
                try:
                    return float(match.group(1))
                except (ValueError, IndexError):
                    continue
        return None
    
    @staticmethod
    def requires_seller_info(message: str) -> bool:
        """Check if buyer message requires information from seller"""
        info_keywords = [
            "what year", "when was", "how old", "age", "brand", "model",
            "dimensions", "size", "weight", "color", "material", "made",
            "manufactured", "where", "how long", "original", "receipt",
            "warranty", "history", "previous owner", "condition details"
        ]
        message_lower = message.lower()
        return any(keyword in message_lower for keyword in info_keywords)
    
    @staticmethod
    def get_intelligent_response(buyer_message: str, buyer_address: str) -> Dict[str, str]:
        """Generate intelligent response using GPT or fallback logic"""
        global item_details, conversation_history
        
        if not item_details:
            return {
                "to_buyer": "Sorry, no item is currently listed for sale. Please check back later!",
                "to_seller": "[ERROR] No item details configured.",
                "action_type": "ERROR"
            }
        
        # Get conversation history
        history = conversation_history.get(buyer_address, [])
        history_text = "\n".join([f"- {msg['sender']}: {msg['message']}" for msg in history[-5:]])
        
        try:
            # Generate GPT response using OpenRouter
            prompt = NEGOTIATION_PROMPT.format(
                item_name=item_details.get('item_name', 'Unknown Item'),
                listing_price=item_details.get('listing_price', 0),
                target_price=item_details.get('target_price', 0),
                minimum_price=item_details.get('minimum_price', 0),
                condition=item_details.get('condition', 'Good condition'),
                known_flaws=item_details.get('known_flaws', 'None mentioned'),
                key_selling_points=item_details.get('key_selling_points', ''),
                pickup_delivery_info=item_details.get('pickup_delivery_info', ''),
                buyer_message=buyer_message,
                conversation_history=history_text
            )
            
            response = client.chat.completions.create(
                model="openai/gpt-3.5-turbo",
                messages=[{"role": "user", "content": prompt}],
                max_tokens=150,
                temperature=0.7
            )
            agent_response = response.choices[0].message.content.strip()
            
            # Generate seller report
            price_offer = MarketplaceNegotiator.extract_price_from_message(buyer_message)
            seller_report = f"[INFO] Buyer: '{buyer_message}' | My response: '{agent_response}'"
            if price_offer:
                seller_report += f" | Offer: ${price_offer}"
            
            action_type = "ACTION_REQUIRED" if MarketplaceNegotiator.requires_seller_info(buyer_message) else "INFO"
            
            return {
                "to_buyer": agent_response,
                "to_seller": seller_report,
                "action_type": action_type
            }
                
        except Exception as e:
            logger.error(f"Error with OpenRouter GPT response: {e}")
            # Fallback to rule-based logic if OpenRouter fails
            return MarketplaceNegotiator.get_fallback_response(buyer_message)
    
    @staticmethod
    async def get_fallback_response_with_icp(buyer_message: str, buyer_address: str) -> Dict[str, str]:
        """Fallback response with ICP integration"""
        global item_details
        
        message_lower = buyer_message.lower().strip()
        conversation_id = f"conv_{buyer_address}"
        
        # Save buyer message to ICP
        buyer_message_data = {
            "sender": "buyer",
            "sender_address": buyer_address,
            "message": buyer_message,
            "timestamp": datetime.now().isoformat(),
            "message_type": "incoming"
        }
        await save_message_to_icp(conversation_id, buyer_message_data)
        
        # Generate response based on rules
        if "available" in message_lower:
            response = f"Hi! Yes, the {item_details.get('item_name', 'item')} is still available. What would you like to know about it?"
            seller_report = "[INFO] New buyer inquiry - confirmed availability."
            action_type = "INFO"
        else:
            # Price negotiation
            price_offer = MarketplaceNegotiator.extract_price_from_message(buyer_message)
            if price_offer:
                min_price = item_details.get('minimum_price', 0)
                target_price = item_details.get('target_price', 0)
                
                # Save offer to ICP
                offer_data = {
                    "conversation_id": conversation_id,
                    "buyer_address": buyer_address,
                    "offer_amount": price_offer,
                    "timestamp": datetime.now().isoformat(),
                    "status": "pending"
                }
                await save_message_to_icp(f"{conversation_id}_offers", offer_data)
                
                if price_offer < min_price:
                    response = f"Thanks for the offer! The lowest I can go is ${min_price}. This item is in {item_details.get('condition', 'great condition')}."
                    seller_report = f"[INFO] Received offer of ${price_offer}, countered with minimum ${min_price}."
                    action_type = "INFO"
                elif price_offer >= target_price:
                    response = f"Perfect! ${price_offer} works for me. {item_details.get('pickup_delivery_info', 'When would you like to pick it up?')}"
                    seller_report = f"[ACTION_REQUIRED] Deal agreed at ${price_offer}! Please confirm pickup arrangements."
                    action_type = "ACTION_REQUIRED"
                else:
                    counter = min(target_price, price_offer * 1.15)
                    response = f"I appreciate the offer! Could you do ${counter:.0f}? {item_details.get('key_selling_points', 'It\'s really worth it.')}"
                    seller_report = f"[INFO] Received ${price_offer}, countered with ${counter:.0f}."
                    action_type = "INFO"
            elif MarketplaceNegotiator.requires_seller_info(buyer_message):
                response = "That's a great question! Let me check on that for you and get right back to you."
                seller_report = f"[ACTION_REQUIRED] Buyer asking: '{buyer_message}'. Please provide this information."
                action_type = "ACTION_REQUIRED"
            else:
                response = f"Thanks for your interest in the {item_details.get('item_name', 'item')}! It's in {item_details.get('condition', 'good condition')}. Any specific questions?"
                seller_report = f"[INFO] General inquiry: '{buyer_message}'. Provided basic information."
                action_type = "INFO"
        
        # Save agent response to ICP
        agent_message_data = {
            "sender": "agent",
            "sender_address": "marketplace_agent",
            "message": response,
            "timestamp": datetime.now().isoformat(),
            "message_type": "response"
        }
        await save_message_to_icp(conversation_id, agent_message_data)
        
        return {
            "to_buyer": response,
            "to_seller": seller_report,
            "action_type": action_type
        }

def create_text_chat(text: str, end_session: bool = False) -> ChatMessage:
    """Create a chat message with text content"""
    content = [TextContent(type="text", text=text)]
    if end_session:
        content.append(EndSessionContent())
    
    return ChatMessage(
        timestamp=datetime.now(timezone.utc),
        msg_id=uuid4(),
        content=content
    )

# Agent startup event
@agent.on_event("startup")
async def startup_handler(ctx: Context):
    """Agent startup handler"""
    ctx.logger.info(f"🤖 Marketplace Negotiator Agent starting up...")
    ctx.logger.info(f"📍 Agent address: {agent.address}")
    ctx.logger.info(f"🔌 Port: {AGENT_PORT}")
    ctx.logger.info(f"🧠 OpenRouter enabled: {bool(OPENROUTER_API_KEY)}")
    ctx.logger.info("✅ Marketplace Negotiator ready for chat protocol communication!")

# Chat message handler
@chat_proto.on_message(ChatMessage)
async def handle_chat_message(ctx: Context, sender: str, msg: ChatMessage):
    """Handle incoming chat messages from buyers and sellers with ICP backend integration"""
    global seller_address
    
    ctx.logger.info(f"💬 Received chat message from {sender}")
    
    # Extract text content from message
    message_text = ""
    for content in msg.content:
        if isinstance(content, TextContent):
            message_text = content.text
            break
    
    if not message_text:
        ctx.logger.warning("⚠️ No text content found in message")
        return
    
    ctx.logger.info(f"📝 Message content: {message_text}")
    
    conversation_id = f"conv_{sender}"
    
    # Load conversation from ICP to check if seller is responding
    conversation_data = await load_conversation_from_icp(conversation_id)
    awaiting_seller = conversation_data and conversation_data.get("awaiting_seller_response", False)
    
    # Check if this is a seller providing information
    if sender == seller_address and awaiting_seller:
        # Handle seller response to pending question
        buyer_waiting = conversation_data.get("buyer_waiting_for_info")
        if buyer_waiting:
            response_text = f"I've confirmed that for you - {message_text}. Hope that helps!"
            
            # Send response to buyer
            response_msg = create_text_chat(response_text)
            await ctx.send(buyer_waiting, response_msg)
            
            # Confirm to seller
            seller_confirmation = create_text_chat("[INFO] I have relayed the information to the buyer.")
            await ctx.send(sender, seller_confirmation)
            
            # Update conversation state in ICP
            updated_conversation = {
                **conversation_data,
                "awaiting_seller_response": False,
                "buyer_waiting_for_info": None
            }
            await save_conversation_to_icp(conversation_id, updated_conversation)
            
            # Save seller response to ICP
            seller_message_data = {
                "sender": "seller",
                "sender_address": sender,
                "message": message_text,
                "timestamp": datetime.now().isoformat(),
                "message_type": "seller_response"
            }
            await save_message_to_icp(conversation_id, seller_message_data)
            
            ctx.logger.info(f"✅ Seller info relayed from {sender} to {buyer_waiting}")
        
    else:
        # Handle buyer message with negotiation logic
        responses = await MarketplaceNegotiator.get_intelligent_response(message_text, sender)
        
        # Send response to buyer
        if responses["to_buyer"]:
            buyer_response = create_text_chat(responses["to_buyer"])
            await ctx.send(sender, buyer_response)
            
            ctx.logger.info(f"💬 Sent response to buyer {sender}")
        
        # Send report to seller and update ICP state
        if responses["to_seller"] and seller_address:
            seller_report = create_text_chat(responses["to_seller"])
            await ctx.send(seller_address, seller_report)
            
            # Update conversation state in ICP if action required
            if responses["action_type"] == "ACTION_REQUIRED":
                conversation_data = await load_conversation_from_icp(conversation_id) or {}
                updated_conversation = {
                    **conversation_data,
                    "awaiting_seller_response": True,
                    "buyer_waiting_for_info": sender,
                    "pending_question": message_text
                }
                await save_conversation_to_icp(conversation_id, updated_conversation)
                ctx.logger.info(f"⏳ Awaiting seller response for {sender}")
            
            ctx.logger.info(f"📊 Sent report to seller {seller_address}")
    
    # Send acknowledgment
    ack = ChatAcknowledgement(
        timestamp=datetime.now(timezone.utc),
        acknowledged_msg_id=msg.msg_id
    )
    await ctx.send(sender, ack)

# Chat acknowledgment handler
@chat_proto.on_message(ChatAcknowledgement)
async def handle_chat_acknowledgement(ctx: Context, sender: str, msg: ChatAcknowledgement):
    """Handle chat acknowledgments"""
    ctx.logger.info(f"✅ Received acknowledgment from {sender} for message {msg.acknowledged_msg_id}")

# Item setup message handler
@agent.on_message(ItemSetup)
async def handle_item_setup(ctx: Context, sender: str, msg: ItemSetup):
    """Handle item setup from seller with ICP storage"""
    global item_details, seller_address
    
    item_details = {
        'item_name': msg.item_name,
        'listing_price': msg.listing_price,
        'target_price': msg.target_price,
        'minimum_price': msg.minimum_price,
        'condition': msg.condition,
        'known_flaws': msg.known_flaws,
        'key_selling_points': msg.key_selling_points,
        'reason_for_selling': msg.reason_for_selling,
        'pickup_delivery_info': msg.pickup_delivery_info,
    }
    
    seller_address = msg.seller_address
    
    # Save item details to ICP
    item_data = {
        "item_details": item_details,
        "seller_address": seller_address,
        "setup_timestamp": datetime.now().isoformat(),
        "status": "active"
    }
    await save_conversation_to_icp("item_config", item_data)
    
    ctx.logger.info(f"🏷️ Item configured: {msg.item_name} (${msg.listing_price})")
    
    # Send confirmation to seller
    confirmation = create_text_chat(
        f"✅ Item setup complete: {msg.item_name} - Listed at ${msg.listing_price}, Target: ${msg.target_price}, Minimum: ${msg.minimum_price}"
    )
    await ctx.send(sender, confirmation)
    
    seller_address = msg.seller_address
    
    ctx.logger.info(f"🏷️ Item configured: {msg.item_name} (${msg.listing_price})")
    
    # Send confirmation to seller
    confirmation = create_text_chat(
        f"✅ Item setup complete: {msg.item_name} - Listed at ${msg.listing_price}, Target: ${msg.target_price}, Minimum: ${msg.minimum_price}"
    )
    await ctx.send(sender, confirmation)

# Include chat protocol in agent
agent.include(chat_proto)

# Health check interval
@agent.on_interval(period=300.0)  # Every 5 minutes
async def health_check(ctx: Context):
    """Periodic health check"""
    ctx.logger.info(f"💓 Health check - Item configured: {bool(item_details)}, Active conversations: {len(conversation_history)}")

if __name__ == "__main__":
    logger.info("🚀 Starting Facebook Marketplace Negotiator with Chat Protocol...")
    logger.info(f"🔧 Agent configuration:")
    logger.info(f"   - Seed: {AGENT_SEED}")
    logger.info(f"   - Port: {AGENT_PORT}")
    logger.info(f"   - OpenRouter: {'✅ Enabled' if OPENROUTER_API_KEY else '❌ Disabled (using fallback)'}")
    logger.info(f"   - Mailbox: ✅ Enabled")
    logger.info(f"   - Chat Protocol: ✅ Enabled")
    
    print("\n" + "="*60)
    print("🏪 FACEBOOK MARKETPLACE NEGOTIATOR AGENT")
    print("="*60)
    print(f"📍 Agent Address: {agent.address}")
    print(f"💬 Chat Protocol: Enabled")
    print(f"🧠 AI Response: {'OpenRouter GPT' if OPENROUTER_API_KEY else 'Rule-based'}")
    print("="*60)
    print("Ready to negotiate! Send me:")
    print("1. ItemSetup message to configure item for sale")
    print("2. ChatMessage for buyer communications")
    print("="*60 + "\n")
    
    agent.run()