from datetime import datetime
from uuid import uuid4
import re
import os
import json
from typing import Dict, Optional, List
import requests
from dotenv import load_dotenv
from openai import OpenAI
from uagents import Context, Protocol, Agent
from uagents_core.contrib.protocols.chat import (
    ChatAcknowledgement,
    ChatMessage,
    TextContent,
    chat_protocol_spec,
)

load_dotenv()

API_BASE_URL = os.getenv("API_BASE_URL", "https://dummyjson.com/c/a2d5-5008-4347-9d22")

client = OpenAI(
    base_url=os.getenv("OPENAI_BASE_URL", "https://openrouter.ai/api/v1"),
    api_key=os.getenv("OPENAI_API_KEY"),
)

agent = Agent()

protocol = Protocol(spec=chat_protocol_spec)


class ItemDetails:
    """Enhanced class for storing item details from API"""

    def __init__(self, data: Dict):
        self.product_id = data.get("id", "")
        self.category_id = data.get("categoryId", "")
        self.item_name = data.get("name", "")
        self.raw_description = data.get("description", "")
        self.price = float(data.get("price", 0))
        self.stock = int(data.get("stock", 0))
        self.image_url = data.get("imageUrl", None)
        self.is_active = data.get("isActive", True)
        self.created_by = data.get("createdBy", "")
        self.created_at = data.get("createdAt", 0)
        self.updated_at = data.get("updatedAt", 0)

        self.target_price = float(data.get("target_price", self.price * 0.85))
        self.minimum_price = float(data.get("minimum_price", self.price * 0.70))

        self.listing_price = self.price
        self.seller = data.get("seller", self.created_by or "Unknown Seller")

        self._parse_enhanced_description()

    def _parse_enhanced_description(self) -> None:
        """Parse enhanced description from seller agent"""
        description_parts = self.raw_description.split("\n\n")

        self.description = (
            description_parts[0] if description_parts else self.raw_description
        )
        self.condition = self._extract_field("Condition:", "Used")
        self.selling_points = self._extract_field("Advantages:", "Good quality item")
        self.known_flaws = self._extract_field("Known Issues:", "No significant flaws")
        self.reason_for_selling = self._extract_field(
            "Reason for Selling:", "No longer needed"
        )
        self.pickup_delivery_info = self._extract_field(
            "Pickup/Delivery:", "Contact seller for delivery info"
        )
        if self.condition == "Used":
            self.condition = self._extract_condition_from_description()
        if self.known_flaws == "No significant flaws":
            self.known_flaws = self._extract_flaws_from_description()
        if self.selling_points == "Good quality item":
            self.selling_points = self._extract_selling_points_from_description()

    def _extract_field(self, field_name: str, default: str) -> str:
        """Extract specific field from description"""
        for part in self.raw_description.split("\n\n"):
            if part.startswith(field_name):
                return part.replace(field_name, "").strip()
        return default

    def _extract_condition_from_description(self) -> str:
        """Extract condition from description text"""
        description_lower = self.description.lower()
        if any(
            word in description_lower
            for word in [
                "excellent",
                "perfect",
                "mint",
                "like new",
                "brand new",
                "pristine",
            ]
        ):
            return "Excellent condition"
        elif any(
            word in description_lower
            for word in [
                "very good",
                "good condition",
                "well maintained",
                "great condition",
            ]
        ):
            return "Good condition"
        elif any(
            word in description_lower for word in ["fair", "used", "worn", "acceptable"]
        ):
            return "Fair condition"
        else:
            return "Used condition"

    def _extract_flaws_from_description(self) -> str:
        """Extract flaws from description text"""
        description = self.description
        flaw_indicators = [
            "scratch",
            "dent",
            "crack",
            "worn",
            "flaw",
            "issue",
            "problem",
            "damage",
            "wear",
            "tear",
            "missing",
            "broken",
            "chipped",
            "faded",
        ]

        sentences = description.split(". ")
        flaws = []

        for sentence in sentences:
            if any(indicator in sentence.lower() for indicator in flaw_indicators):
                flaws.append(sentence.strip())

        return ". ".join(flaws) if flaws else "No significant flaws"

    def _extract_selling_points_from_description(self) -> str:
        """Extract selling points from description text"""
        description = self.description
        positive_indicators = [
            "original",
            "included",
            "warranty",
            "new",
            "premium",
            "quality",
            "complete",
            "genuine",
            "professional",
            "certified",
            "authentic",
            "brand new",
            "high quality",
            "well maintained",
            "barely used",
        ]

        sentences = description.split(". ")
        points = []

        for sentence in sentences:
            if any(indicator in sentence.lower() for indicator in positive_indicators):
                points.append(sentence.strip())

        return ". ".join(points[:3]) if points else "Good quality item"


def fetch_item_details(product_id: str, ctx: Context = None) -> Optional[ItemDetails]:
    """Fetch item details from API with improved error handling and debug logging"""
    try:
        headers = {
            "Content-Type": "application/json",
        }
        url = f"{API_BASE_URL}/products/{product_id}"

        response = requests.get(url, headers=headers, timeout=15)
        if response.status_code == 200:
            try:
                data = response.json()
                item = ItemDetails(data)
                return item

            except json.JSONDecodeError as e:
                if ctx:
                    ctx.logger.debug(f"❌ JSON Decode Error: {str(e)}")
                    ctx.logger.debug(f"📄 Response Text: {response.text}")
                return None

        elif response.status_code == 404:
            if ctx:
                ctx.logger.debug(f"❌ Product not found (404): {product_id}")
            return None
        else:
            error_msg = f"API returned status code: {response.status_code}"
            if ctx:
                ctx.logger.debug(f"❌ API Error: {error_msg}")
                ctx.logger.debug(f"📄 Response Text: {response.text}")
            raise Exception(error_msg)

    except (
        requests.exceptions.Timeout,
        requests.exceptions.ConnectionError,
        requests.exceptions.RequestException,
        Exception,
    ) as e:
        if ctx:
            ctx.logger.debug(f"❌ Exception in fetch_item_details: {str(e)}")
            ctx.logger.debug(f"🔍 Product ID: {product_id}")
            ctx.logger.debug(f"📡 API URL: {API_BASE_URL}/products/{product_id}")
        return None


def extract_product_id(text: str) -> Optional[str]:
    """Extract product ID from message with enhanced patterns to support product_, product_1, etc formats"""
    patterns = [
        r"\bproduct_\b",
        r"product_([a-zA-Z0-9_-]+)",
        r"product[_ ]([a-zA-Z0-9_-]+)",
        r"(product[A-Z0-9]{8})",
    ]

    text_clean = text.strip()

    for i, pattern in enumerate(patterns):
        match = re.search(pattern, text_clean, re.IGNORECASE)
        if match:
            if i == 0:
                return "product_"
            elif i == 1:
                product_id = f"product_{match.group(1)}"
                return product_id
            elif i == 2:
                raw_id = match.group(1)
                product_id = f"product_{raw_id}"
                return product_id
            elif i == 3:
                return match.group(1).upper()
            elif i == 4:
                return match.group(1).upper()
            else:
                captured_id = match.group(1)
                if captured_id.isdigit():
                    return f"product_{captured_id}"
                else:
                    return captured_id

    return None


def extract_offer_amount(message: str) -> Optional[float]:
    """Extract offer amount from message with enhanced patterns"""

    idr_patterns = [
        r"(?:Rp\.?\s*)?(\d{1,3}(?:[.,]\d{3})*(?:[.,]\d{2})?)",
        r"(\d+(?:[.,]\d{3})*)\s*(?:thousand|k)",
        r"(\d+(?:[.,]\d{3})*)\s*(?:million|m)",
        r"offer\s+(?:Rp\.?\s*)?(\d+(?:[.,]\d{3})*)",
        r"pay\s+(?:Rp\.?\s*)?(\d+(?:[.,]\d{3})*)",
        r"buy\s+(?:Rp\.?\s*)?(\d+(?:[.,]\d{3})*)",
    ]

    usd_patterns = [
        r"\$(\d+(?:\.\d{2})?)",
        r"(\d+(?:\.\d{2})?)\s*dollars?",
        r"offer\s+\$?(\d+(?:\.\d{2})?)",
        r"pay\s+\$?(\d+(?:\.\d{2})?)",
        r"(\d+)\s*usd",
        r"(\d+)\s*bucks?",
    ]

    for i, pattern in enumerate(usd_patterns):
        match = re.search(pattern, message.lower())
        if match:
            try:
                amount = float(match.group(1))
                return amount
            except ValueError:
                continue

    for i, pattern in enumerate(idr_patterns):
        match = re.search(pattern, message.lower())
        if match:
            try:
                price_str = match.group(1).replace(",", "").replace(".", "")
                price = float(price_str)

                if i == 1:  # thousand/k
                    price *= 1000
                elif i == 2:  # million/m
                    price *= 1000000

                return price
            except ValueError:
                continue

    return None


def format_currency(amount: float, is_indonesian: bool = True) -> str:
    """Format amount to currency based on context"""
    if is_indonesian:
        if amount == 0:
            return "Rp0"
        amount_int = int(amount)
        formatted = f"{amount_int:,}".replace(",", ".")
        return f"Rp{formatted}"
    else:
        return f"${amount:.2f}" if amount > 0 else "$0"


def get_storage_key(sender: str, key_type: str) -> str:
    """Generate storage key for different types of data"""
    return f"{key_type}_{sender}"


def load_message_history(ctx: Context, sender: str) -> List[Dict]:
    """Load message history from storage"""
    try:
        storage_key = get_storage_key(sender, "messages")
        stored_messages = ctx.storage.get(storage_key)

        if stored_messages:
            if isinstance(stored_messages, str):
                return json.loads(stored_messages)
            elif isinstance(stored_messages, list):
                return stored_messages

        return []
    except Exception:
        return []


def save_message_history(ctx: Context, sender: str, messages: List[Dict]) -> None:
    """Save message history to storage"""
    try:
        storage_key = get_storage_key(sender, "messages")

        if len(messages) > 50:
            messages = messages[-40:]

        ctx.storage.set(storage_key, json.dumps(messages))
    except Exception as e:
        ctx.logger.error(f"Failed to save message history: {e}")


def clear_conversation_history(ctx: Context, sender: str) -> None:
    """Clear conversation history for a user"""
    try:
        storage_key = get_storage_key(sender, "messages")
        ctx.storage.set(storage_key, json.dumps([]))
        ctx.logger.info(f"🧹 Cleared conversation history for {sender}")
    except Exception as e:
        ctx.logger.error(f"Failed to clear conversation history: {e}")


def get_last_product_context(ctx: Context, sender: str) -> Optional[str]:
    """Get the last discussed product ID from storage"""
    try:
        storage_key = get_storage_key(sender, "last_product")
        return ctx.storage.get(storage_key)
    except Exception:
        return None


def set_last_product_context(ctx: Context, sender: str, product_id: str) -> None:
    """Store the last discussed product ID"""
    try:
        storage_key = get_storage_key(sender, "last_product")
        ctx.storage.set(storage_key, product_id)
        ctx.logger.info(f"💾 Set last product context for {sender}: {product_id}")
    except Exception as e:
        ctx.logger.error(f"Failed to store last product context: {e}")


def clear_all_user_storage(ctx: Context, sender: str) -> None:
    """Clear all storage data for a user"""
    try:
        # Clear message history
        messages_key = get_storage_key(sender, "messages")
        ctx.storage.set(messages_key, json.dumps([]))

        # Clear last product context
        product_key = get_storage_key(sender, "last_product")
        ctx.storage.set(product_key, "")

        ctx.logger.info(f"🧹 Cleared all storage for user: {sender}")
    except Exception as e:
        ctx.logger.error(f"❌ Failed to clear storage for user {sender}: {e}")


def detect_new_product_and_clear_if_needed(ctx: Context, sender: str, user_message: str) -> tuple[bool, Optional[str]]:
    """
    Detect if user message contains a product ID and clear storage if it's different from current product.
    Returns (is_new_product, product_id)
    """
    # Extract product ID from current message
    current_product_id = extract_product_id(user_message)
    
    if not current_product_id:
        # No product ID in message, return current context
        return False, get_last_product_context(ctx, sender)
    
    # Get last product from storage
    last_product_id = get_last_product_context(ctx, sender)
    
    ctx.logger.info(f"🔍 Product detection - Current: {current_product_id}, Last: {last_product_id}")
    
    # If this is a different product or first time, clear everything and start fresh
    if current_product_id != last_product_id:
        ctx.logger.info(f"🆕 NEW PRODUCT DETECTED! Clearing all storage...")
        ctx.logger.info(f"   - Previous product: {last_product_id or 'None'}")
        ctx.logger.info(f"   - New product: {current_product_id}")
        
        # Clear all storage for this user
        clear_all_user_storage(ctx, sender)
        
        # Set new product context
        set_last_product_context(ctx, sender, current_product_id)
        
        return True, current_product_id
    
    # Same product, no need to clear
    ctx.logger.info(f"📦 Continuing conversation with same product: {current_product_id}")
    return False, current_product_id


def create_system_message(item: ItemDetails = None, is_new_product: bool = False, current_product_id: str = None) -> str:
    """Create comprehensive system message for the negotiation"""
    
    if item:
        # SUCCESS CASE: Product found and loaded
        item_price = format_currency(item.listing_price)
        target_price = format_currency(item.target_price)
        minimum_price = format_currency(item.minimum_price)

        # Add new product indicator
        new_product_text = ""
        if is_new_product:
            new_product_text = f"""🆕 **NEW PRODUCT CONVERSATION STARTED**
🧹 I've cleared our previous conversation to focus on this new product.
🔄 Starting fresh negotiation context.

"""

        return f"""You are Marketplace Pro, a friendly and professional AI marketplace negotiation assistant. 

{new_product_text}📦 **CURRENT PRODUCT DISCUSSION: {current_product_id}**
✅ **Product Successfully Loaded!**

• **Name:** {item.item_name}
• **Listed Price:** {item_price}
• **Target Price:** {target_price}
• **Minimum Price:** {minimum_price}
• **Condition:** {item.condition}
• **Stock:** {item.stock} units
• **Description:** {item.description[:200]}{'...' if len(item.description) > 200 else ''}
• **Seller Information:** {item.seller}

💡 **Negotiation Context:**
You are now discussing {item.item_name} (ID: {current_product_id}) with the user. The product is available for {item_price}. You should help negotiate a fair price between the target price of {target_price} and minimum price of {minimum_price}.

**Product Advantages:** {item.selling_points}
**Things to Note:** {item.known_flaws}

🤝 **Your Role:**
• Help the user negotiate this specific product
• Provide information about the product when asked
• Suggest reasonable offers based on the price range
• Be friendly and professional in all interactions
• You KNOW about this product - don't ask the user to provide product details again

IMPORTANT: The user has already provided the product ID ({current_product_id}) and the product data has been successfully loaded. Respond naturally about this product."""

    elif current_product_id:
        # PRODUCT ID PROVIDED BUT NOT FOUND
        if is_new_product:
            return f"""You are Marketplace Pro, a friendly and professional AI marketplace negotiation assistant.

🧹 **NEW PRODUCT CONVERSATION STARTED**
I've cleared our previous conversation to focus on the new product.

❌ **PRODUCT NOT FOUND: {current_product_id}**
The product ID "{current_product_id}" was not found in our database.

This could mean:
• The product ID is incorrect or has a typo
• The product has been removed or is no longer available
• The product is temporarily inactive

💡 **What you can do:**
• Double-check the product ID format
• Try a different product ID (like product_1, product_2, etc.)
• Ask the seller for the correct product information

Please provide a valid product ID to continue with the negotiation!"""
        else:
            return f"""You are Marketplace Pro, a friendly and professional AI marketplace negotiation assistant.

❌ **PRODUCT NOT FOUND: {current_product_id}**
The product ID "{current_product_id}" was not found in our database.

Please provide a valid product ID to start the negotiation."""
    
    else:
        # NO PRODUCT ID PROVIDED - GENERAL WELCOME
        return """You are Marketplace Pro, a friendly and professional AI marketplace negotiation assistant following the Facebook Marketplace Sales Negotiator protocol.

Welcome! 👋 I'm ready to help you negotiate products.

📝 **How to Use:**
1. Send the Product ID you want to negotiate
2. Add your message after the Product ID  
3. I'll help you negotiate with the seller

💬 **Usage Examples:**
• `product_` → View general/template product
• `product_1` → View product details
• `product_1 Hi, is this still available?`
• `product_123 Can we negotiate the price?`
• `product_abc What's the condition like?`

✨ **Features I Offer:**
• Smart price negotiation
• Detailed product information
• Auto-translation (Indonesian/English)
• Negotiation strategy suggestions
• Offer management
• Analyze offer prices and suggest counters

Please start by sending the Product ID you're interested in!

IMPORTANT: If you mention a Product ID in your message, I will immediately process it as a product request."""


async def generate_ai_response(
    ctx: Context, sender: str, user_message: str, is_new_product: bool, current_product_id: Optional[str]
) -> str:
    """Generate AI response using OpenAI with new product detection"""

    try:
        # Fetch item details if we have a product ID
        item = None
        if current_product_id:
            item = fetch_item_details(current_product_id, ctx)
            
            if item:
                ctx.logger.debug(f"✅ Item fetched successfully: {item.item_name} (ID: {item.product_id})")
            else:
                ctx.logger.debug(f"❌ Item not found for ID: {current_product_id}")

        # Load message history (should be empty if new product was detected and cleared)
        conversation_history = load_message_history(ctx, sender)
        
        # Create OpenAI messages
        openai_messages = []

        # Create system message with current product context
        system_msg = create_system_message(item, is_new_product, current_product_id)
        openai_messages.append({"role": "system", "content": system_msg})

        # Add recent conversation history (limited to prevent token overflow)
        recent_history = conversation_history[-20:] if len(conversation_history) > 20 else conversation_history

        # Add conversation history to OpenAI messages
        for msg in recent_history:
            if msg.get("role") in ["user", "assistant"] and msg.get("content", "").strip():
                openai_messages.append({"role": msg["role"], "content": msg["content"]})

        # Add current user message
        user_message = user_message.strip() if user_message else "Hello"
        openai_messages.append({"role": "user", "content": user_message})

        # Validate all messages before sending to API
        validated_messages = []
        for msg in openai_messages:
            if msg.get("content") and msg["content"].strip():
                validated_messages.append(msg)

        if not validated_messages:
            # Fallback if no valid messages
            validated_messages = [
                {"role": "system", "content": "You are a marketplace AI assistant."},
                {"role": "user", "content": user_message},
            ]

        # Get OpenAI configuration from environment
        model = os.getenv("OPENAI_MODEL", "gpt-3.5-turbo")
        max_tokens = int(os.getenv("OPENAI_MAX_TOKENS", "800"))
        temperature = float(os.getenv("OPENAI_TEMPERATURE", "0.7"))

        ctx.logger.debug(f"🤖 Calling OpenAI API with {len(validated_messages)} messages")

        # Call OpenAI API
        response = client.chat.completions.create(
            model=model,
            messages=validated_messages,
            max_tokens=max_tokens,
            temperature=temperature,
        )

        ai_response = response.choices[0].message.content
        final_response = ai_response or "Sorry, I cannot process your request at this time."

        ctx.logger.debug(f"✅ AI Response generated successfully ({len(final_response)} chars)")
        return final_response

    except Exception as e:
        ctx.logger.error(f"❌ Error in generate_ai_response: {str(e)}")
        return f"Sorry, I'm experiencing technical difficulties: {str(e)}. Please wait a moment and try again."


@protocol.on_message(ChatMessage)
async def handle_message(ctx: Context, sender: str, msg: ChatMessage):
    """Handle incoming chat messages with enhanced product context management"""

    await ctx.send(
        sender,
        ChatAcknowledgement(timestamp=datetime.now(), acknowledged_msg_id=msg.msg_id),
    )

    text = ""
    for item in msg.content:
        if isinstance(item, TextContent):
            text += item.text

    try:
        ctx.logger.info(f"📨 Processing message from {sender}: {text[:100]}...")

        # 🔥 KEY CHANGE: Detect new product and clear storage if needed
        is_new_product, current_product_id = detect_new_product_and_clear_if_needed(ctx, sender, text)

        # Load message history (will be empty if storage was just cleared)
        message_history = load_message_history(ctx, sender)
        ctx.logger.debug(f"📚 Message history length: {len(message_history)}")

        # Generate AI response with new product awareness
        response_text = await generate_ai_response(ctx, sender, text, is_new_product, current_product_id)

        # Validate response before saving
        if not response_text or response_text.strip() == "":
            response_text = "Sorry, I cannot process your request at this time."
            ctx.logger.debug(f"⚠️ Empty response detected, using fallback message")

        # Add new messages to history
        message_history.append({"role": "user", "content": text or "Hello"})
        message_history.append({"role": "assistant", "content": response_text})

        # Save updated history
        save_message_history(ctx, sender, message_history)

        ctx.logger.info(f"💾 Updated message history length for {sender}: {len(message_history)}")
        ctx.logger.debug(f"✅ Message processing completed successfully")

    except Exception as e:
        ctx.logger.exception("❌ Error processing message")
        ctx.logger.debug(f"   - Sender: {sender}")
        ctx.logger.debug(f"   - Text: {text}")
        ctx.logger.debug(f"   - Error: {str(e)}")

        response_text = f"Sorry, a technical error occurred: {str(e)}. Please try again or contact support."

        # Try to save error response to history
        try:
            message_history = load_message_history(ctx, sender)
            message_history.append({"role": "user", "content": text or "Error"})
            message_history.append({"role": "assistant", "content": response_text})
            save_message_history(ctx, sender, message_history)
            ctx.logger.debug(f"💾 Error response saved to history")
        except Exception as save_error:
            ctx.logger.debug(f"❌ Failed to save error response: {str(save_error)}")

    # Send response back to user
    await ctx.send(
        sender,
        ChatMessage(
            timestamp=datetime.utcnow(),
            msg_id=uuid4(),
            content=[
                TextContent(type="text", text=response_text),
            ],
        ),
    )

    ctx.logger.debug(f"✅ Response sent successfully to {sender}")


@protocol.on_message(ChatAcknowledgement)
async def handle_ack(ctx: Context, sender: str, msg: ChatAcknowledgement):
    """Handle chat acknowledgements"""
    pass


agent.include(protocol, publish_manifest=True)

if __name__ == "__main__":
    required_vars = ["OPENAI_API_KEY"]
    missing_vars = [var for var in required_vars if not os.getenv(var)]

    if missing_vars:
        exit(1)

    agent.run()