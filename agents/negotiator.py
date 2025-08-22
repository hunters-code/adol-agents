from datetime import datetime
from uuid import uuid4
import re
import os
from typing import Dict, Optional

from dotenv import load_dotenv
from openai import OpenAI
from uagents import Context, Protocol, Agent
from uagents_core.contrib.protocols.chat import (
    ChatAcknowledgement,
    ChatMessage,
    TextContent,
    chat_protocol_spec,
)

# Load environment variables from .env file
load_dotenv()

# Configuration for API endpoints
API_BASE_URL = os.getenv("API_BASE_URL", "https://dummyjson.com/c/a2d5-5008-4347-9d22")

# Initialize OpenAI client with environment variables
client = OpenAI(
    base_url=os.getenv("OPENAI_BASE_URL", "https://openrouter.ai/api/v1"),
    api_key=os.getenv("OPENAI_API_KEY"),
)

# Create the agent
agent = Agent()

# Create protocol compatible with chat protocol spec
protocol = Protocol(spec=chat_protocol_spec)


class ItemDetails:
    """Class to hold item details from API"""

    def __init__(self, data: Dict):
        self.product_id = data.get("id", "")
        self.category_id = data.get("categoryId", "")
        self.item_name = data.get("name", "")
        self.description = data.get("description", "")
        self.price = float(data.get("price", 0))
        self.stock = int(data.get("stock", 0))
        self.image_url = data.get("imageUrl", None)
        self.is_active = data.get("isActive", True)
        self.created_by = data.get("createdBy", "")
        self.created_at = data.get("createdAt", 0)
        self.updated_at = data.get("updatedAt", 0)

        # Calculate negotiation prices
        self.listing_price = self.price
        self.target_price = self.price * 0.85
        self.minimum_price = self.price * 0.70

        # Extract info from description
        self.condition = self._extract_condition()
        self.known_flaws = self._extract_flaws()
        self.selling_points = self._extract_selling_points()
        self.pickup_delivery_info = self._extract_delivery_info()

    def _extract_condition(self) -> str:
        description_lower = self.description.lower()

        if any(
            word in description_lower
            for word in ["excellent", "perfect", "mint", "like new"]
        ):
            return "Excellent condition"
        elif any(
            word in description_lower
            for word in ["very good", "good condition", "well maintained"]
        ):
            return "Good condition"
        elif any(word in description_lower for word in ["fair", "used", "worn"]):
            return "Fair condition"
        elif any(word in description_lower for word in ["kondisi baik", "sangat baik"]):
            return "Kondisi baik"
        else:
            return "Used condition"

    def _extract_flaws(self) -> str:
        description = self.description
        flaw_indicators = [
            "scratch",
            "dent",
            "crack",
            "worn",
            "flaw",
            "issue",
            "problem",
            "lecet",
            "retak",
            "cacat",
            "rusak",
            "bekas",
        ]

        sentences = description.split(". ")
        flaws = []

        for sentence in sentences:
            if any(indicator in sentence.lower() for indicator in flaw_indicators):
                flaws.append(sentence.strip())

        return ". ".join(flaws) if flaws else "No major flaws mentioned"

    def _extract_selling_points(self) -> str:
        description = self.description
        positive_indicators = [
            "original",
            "included",
            "warranty",
            "new",
            "premium",
            "quality",
            "asli",
            "berkualitas",
            "bagus",
            "lengkap",
        ]

        sentences = description.split(". ")
        points = []

        for sentence in sentences:
            if any(indicator in sentence.lower() for indicator in positive_indicators):
                points.append(sentence.strip())

        return ". ".join(points[:3]) if points else "Good quality item"

    def _extract_delivery_info(self) -> str:
        description_lower = self.description.lower()

        if any(
            word in description_lower for word in ["pickup", "cod", "meet", "ambil"]
        ):
            return "Pickup available"
        elif any(
            word in description_lower
            for word in ["shipping", "delivery", "kirim", "diantar"]
        ):
            return "Shipping/delivery available"
        else:
            return "Contact seller for delivery options"


def fetch_item_details(product_id: str) -> Optional[ItemDetails]:
    """Fetch item details from API"""
    try:
        import requests

        headers = {
            "Content-Type": "application/json",
        }

        response = requests.get(
            f"{API_BASE_URL}/products/{product_id}", headers=headers, timeout=10
        )

        if response.status_code == 200:
            data = response.json()
            return ItemDetails(data)
        elif response.status_code == 404:
            return None
        else:
            raise Exception(f"API returned status code: {response.status_code}")

    except Exception as e:
        print(f"Error fetching item details: {str(e)}")
        return None


def extract_product_id(text: str) -> Optional[str]:
    """Extract product ID from message"""
    patterns = [
        r"product[_ ]id:?\s*([a-zA-Z0-9_-]+)",
        r"id:?\s*([a-zA-Z0-9_-]+)",
        r"^([a-zA-Z0-9_-]{6,})$",
        r"#([a-zA-Z0-9_-]+)",
    ]

    text_clean = text.strip()

    for pattern in patterns:
        match = re.search(pattern, text_clean, re.IGNORECASE)
        if match:
            return match.group(1)

    return None


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
        "berapa",
        "harga",
        "jual",
        "beli",
        "tawar",
        "nego",
        "cod",
        "transfer",
        "kirim",
        "barang",
        "kondisi",
        "masih",
        "ada",
        "gimana",
        "bagaimana",
        "ambil",
        "pickup",
        "lokasi",
        "dimana",
        "kapan",
        "jam",
        "hari",
        "minggu",
        "bulan",
    ]

    message_lower = message.lower()
    indonesian_count = sum(1 for word in indonesian_words if word in message_lower)

    return "indonesian" if indonesian_count >= 2 else "english"


def extract_offer_amount(message: str) -> Optional[float]:
    """Extract monetary offer from message"""
    usd_patterns = [
        r"\$(\d+(?:\.\d{2})?)",
        r"(\d+(?:\.\d{2})?)\s*dollars?",
        r"offer\s+\$?(\d+(?:\.\d{2})?)",
        r"pay\s+\$?(\d+(?:\.\d{2})?)",
    ]

    idr_patterns = [
        r"(?:Rp\.?\s*)?(\d{1,3}(?:[.,]\d{3})*(?:[.,]\d{2})?)",
        r"(\d+(?:[.,]\d{3})*)\s*(?:ribu|rb)",
        r"(\d+(?:[.,]\d{3})*)\s*(?:juta|jt)",
        r"tawar\s+(?:Rp\.?\s*)?(\d+(?:[.,]\d{3})*)",
        r"bayar\s+(?:Rp\.?\s*)?(\d+(?:[.,]\d{3})*)",
    ]

    for pattern in usd_patterns:
        match = re.search(pattern, message.lower())
        if match:
            try:
                return float(match.group(1))
            except ValueError:
                continue

    for i, pattern in enumerate(idr_patterns):
        match = re.search(pattern, message.lower())
        if match:
            try:
                price_str = match.group(1).replace(",", "").replace(".", "")
                price = float(price_str)
                if i == 1:
                    price *= 1000
                elif i == 2:
                    price *= 1000000
                return price
            except ValueError:
                continue

    return None


def format_currency(amount: float, language: str = "english") -> str:
    """Format amount to currency based on language"""
    if language == "indonesian":
        if amount == 0:
            return "Rp0"
        amount_int = int(amount)
        formatted = f"{amount_int:,}".replace(",", ".")
        return f"Rp{formatted}"
    else:
        return f"${amount:.2f}" if amount > 0 else "$0"


def generate_negotiation_response(
    item: ItemDetails, buyer_message: str
) -> Dict[str, str]:
    """Generate response using OpenAI"""

    buyer_language = detect_language(buyer_message)
    offer_amount = extract_offer_amount(buyer_message)

    listing_price_formatted = format_currency(item.listing_price, buyer_language)
    target_price_formatted = format_currency(item.target_price, buyer_language)
    minimum_price_formatted = format_currency(item.minimum_price, buyer_language)

    if buyer_language == "indonesian":
        lang_instruction = "BAHASA: Respons dalam Bahasa Indonesia. Gunakan format Rupiah untuk harga. Gunakan bahasa ramah dan profesional."
    else:
        lang_instruction = "LANGUAGE: Respond in English. Use USD format for prices. Use friendly and professional language."

    system_content = f"""You are Marketplace Pro, an expert AI sales assistant. You are friendly, professional, and an expert negotiator.

DETECTED BUYER LANGUAGE: {buyer_language}
{lang_instruction}

ITEM DETAILS:
- Product ID: {item.product_id}
- Item Name: {item.item_name}
- Description: {item.description}
- Listing Price: {listing_price_formatted}
- Target Price: {target_price_formatted}
- Minimum Price: {minimum_price_formatted}
- Stock Available: {item.stock}
- Condition: {item.condition}

BUYER MESSAGE: {buyer_message}

RULES:
1. Respond to buyer in {buyer_language.upper()} only
2. Target price: {target_price_formatted}
3. Minimum price: {minimum_price_formatted}
4. If offer >= target: accept enthusiastically
5. If offer between minimum and target: negotiate upward
6. If offer < minimum: politely decline and counter
7. Be friendly and professional

RESPONSE FORMAT:
[message_to_buyer]
Your response to the buyer in {buyer_language}

[message_to_seller]
Your report to the seller in English"""

    user_content = f"Buyer says: {buyer_message}"

    try:
        response = client.chat.completions.create(
            model=os.getenv("OPENAI_MODEL", "gpt-3.5-turbo"),
            messages=[
                {"role": "system", "content": system_content},
                {"role": "user", "content": user_content},
            ],
            max_tokens=int(os.getenv("OPENAI_MAX_TOKENS", "500")),
            temperature=float(os.getenv("OPENAI_TEMPERATURE", "0.7")),
        )

        ai_response = response.choices[0].message.content
        parsed_response = parse_ai_response(ai_response)
        parsed_response["detected_language"] = buyer_language

        return parsed_response

    except Exception as e:
        if buyer_language == "indonesian":
            error_msg = (
                "Maaf, saya sedang mengalami gangguan teknis. Mohon tunggu sebentar."
            )
        else:
            error_msg = "I'm having technical difficulties. Please give me a moment."

        return {
            "message_to_buyer": error_msg,
            "message_to_seller": f"[ERROR] AI response failed: {str(e)}",
            "detected_language": buyer_language,
        }


def parse_ai_response(ai_response: str) -> Dict[str, str]:
    """Parse AI response to extract buyer and seller messages"""
    result = {"message_to_buyer": "", "message_to_seller": ""}

    lines = ai_response.split("\n")
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
            result[current_section] += line + " "

    result["message_to_buyer"] = result["message_to_buyer"].strip()
    result["message_to_seller"] = result["message_to_seller"].strip()

    if not result["message_to_buyer"] and not result["message_to_seller"]:
        result["message_to_buyer"] = ai_response
        result["message_to_seller"] = "[INFO] Generated standard response to buyer."

    return result


@protocol.on_message(ChatMessage)
async def handle_message(ctx: Context, sender: str, msg: ChatMessage):
    """Handle incoming chat messages"""

    await ctx.send(
        sender,
        ChatAcknowledgement(timestamp=datetime.now(), acknowledged_msg_id=msg.msg_id),
    )

    text = ""
    for item in msg.content:
        if isinstance(item, TextContent):
            text += item.text

    try:
        product_id = extract_product_id(text)

        if not product_id:
            welcome_msg = """🤖 Marketplace Negotiation Assistant

Please provide a product ID to start negotiating.

Examples:
- PROD123456
- Product ID: ABC-789
- #ITEM001

Format:
[Product ID]
[Your message as buyer]

Example:
PROD123456
Hi, is this still available? I'm interested in buying it.

I'll fetch the item details and handle the negotiation!"""
            response_text = welcome_msg

        else:
            ctx.logger.info(f"Fetching details for product ID: {product_id}")

            item = fetch_item_details(product_id)

            if not item:
                not_found_msg = f"""❌ Product Not Found

Product ID {product_id} was not found in our system.

Please check:
- The product ID is correct
- The item hasn't been removed
- You have the right permissions

Try again with a valid product ID."""
                response_text = not_found_msg

            elif not item.is_active:
                inactive_msg = f"""⚠️ Product Inactive

Product {product_id} - {item.item_name} is no longer active for sale.

Status: Inactive
Stock: {item.stock}

Please contact the seller for more information."""
                response_text = inactive_msg

            else:
                buyer_message = text.replace(product_id, "", 1).strip()

                if not buyer_message:
                    desc_preview = item.description[:200]
                    if len(item.description) > 200:
                        desc_preview += "..."

                    found_msg = f"""✅ Product Found: {item.item_name}

Product ID: {product_id}
Category: {item.category_id}
Price: {format_currency(item.price, "english")}
Stock: {item.stock} available
Condition: {item.condition}
Description: {desc_preview}

💬 Ready to negotiate!

Send your message and I'll handle the negotiation:
- Ask questions about the item
- Make an offer
- Inquire about availability

Example: {product_id} Hi, is this still available? I can offer $X"""
                    response_text = found_msg

                else:
                    ctx.logger.info(
                        f"Processing negotiation for {product_id}: {buyer_message}"
                    )

                    ai_response = generate_negotiation_response(item, buyer_message)
                    detected_language = ai_response.get("detected_language", "english")

                    target_formatted = format_currency(
                        item.target_price, detected_language
                    )
                    minimum_formatted = format_currency(
                        item.minimum_price, detected_language
                    )

                    if detected_language == "indonesian":
                        status_msg = f"Status: Aktif | Target: {target_formatted} | Minimum: {minimum_formatted}"
                    else:
                        status_msg = f"Status: Active | Target: {target_formatted} | Minimum: {minimum_formatted}"

                    negotiation_msg = f"""🛍️ {item.item_name} [{product_id}]

To Buyer ({detected_language.title()}):
{ai_response['message_to_buyer']}

To Seller (You):
{ai_response['message_to_seller']}

---
{status_msg}

Next Steps:
- Continue negotiation: {product_id} [buyer's next message]
- New negotiation: Send a different product ID"""
                    response_text = negotiation_msg

    except Exception as e:
        ctx.logger.exception("Error processing message")
        error_msg = f"""❌ Error Processing Request

Sorry, I encountered an error: {str(e)}

Please try again with:
- A valid product ID
- Clear message format

Example: PROD123 Hi, is this available?"""
        response_text = error_msg

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


@protocol.on_message(ChatAcknowledgement)
async def handle_ack(ctx: Context, sender: str, msg: ChatAcknowledgement):
    """Handle chat acknowledgements"""
    pass


# Attach the protocol to the agent
agent.include(protocol, publish_manifest=True)

if __name__ == "__main__":
    # Check if required environment variables are set
    required_vars = ["OPENAI_API_KEY"]
    missing_vars = [var for var in required_vars if not os.getenv(var)]

    if missing_vars:
        print("❌ Error: Missing required environment variables:")
        for var in missing_vars:
            print(f"   - {var}")
        print("\nPlease create a .env file with the required variables.")
        exit(1)

    print("🤖 Marketplace Negotiation Agent Starting...")
    print("📱 This agent handles marketplace sales negotiations using chat protocol")
    print("🔗 Item details are fetched from API using Product ID")
    print("📝 No conversation history stored - each interaction is independent")
    print("🌍 Supports English and Indonesian languages")
    print("💬 Connect via AgentVerse to start negotiating!")
    print("=" * 60)
    print(f"📡 API Endpoint: {API_BASE_URL}")
    print("🔑 Environment variables loaded successfully!")
    agent.run()
