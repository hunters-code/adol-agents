from datetime import datetime
from uuid import uuid4
import os
import json
import random
from typing import Dict, Optional, Tuple, List

from dotenv import load_dotenv
from openai import OpenAI
from uagents import Context, Protocol, Agent
from uagents_core.contrib.protocols.chat import (
    ChatAcknowledgement,
    ChatMessage,
    TextContent,
    ResourceContent,
    MetadataContent,
    StartSessionContent,
    chat_protocol_spec,
)
from uagents_core.storage import ExternalStorage
import requests

# Load environment variables
load_dotenv()

# Initialize OpenAI client
client = OpenAI(
    base_url=os.getenv("OPENAI_BASE_URL", "https://openrouter.ai/api/v1"),
    api_key=os.getenv("OPENAI_API_KEY"),
)

# API Configuration
API_BASE_URL = os.getenv("API_BASE_URL", "https://dummyjson.com/c/a2d5-5008-4347-9d22")
STORAGE_URL = os.getenv("AGENTVERSE_URL", "https://agentverse.ai") + "/v1/storage"

# Create the agent
agent = Agent()
protocol = Protocol(spec=chat_protocol_spec)

# Persistent memory - store recent interactions for context
recent_interactions = []
MAX_INTERACTIONS = 50

# Global product state - simpler approach
current_product_data = None
last_update_time = None


def set_current_product(product_data: Dict):
    """Set current product data globally"""
    global current_product_data, last_update_time
    current_product_data = product_data.copy()
    last_update_time = datetime.now()
    print(
        f"🟢 PRODUCT SET: {product_data.get('item_name', 'Unknown')} - Rp{product_data.get('listing_price', 0):,.0f}"
    )


def get_current_product() -> Optional[Dict]:
    """Get current product data if recent"""
    global current_product_data, last_update_time

    if current_product_data and last_update_time:
        # Check if data is recent (within 1 hour)
        if (datetime.now() - last_update_time).seconds < 3600:
            print(f"🟢 PRODUCT GET: {current_product_data.get('item_name', 'Unknown')}")
            return current_product_data.copy()

    print("🔴 NO CURRENT PRODUCT DATA")
    return None


def clear_current_product():
    """Clear current product data"""
    global current_product_data, last_update_time
    current_product_data = None
    last_update_time = None
    print("🟡 PRODUCT CLEARED")


def add_interaction(interaction_type: str, content: Dict):
    """Add interaction to persistent memory"""
    global recent_interactions

    interaction = {
        "timestamp": datetime.now().isoformat(),
        "type": interaction_type,  # "image_analysis", "user_input", "listing_created"
        "content": content,
    }

    recent_interactions.append(interaction)

    # Keep only recent interactions
    if len(recent_interactions) > MAX_INTERACTIONS:
        recent_interactions = recent_interactions[-MAX_INTERACTIONS:]


def get_relevant_context(user_message: str = "") -> str:
    """Get relevant context from recent interactions"""
    if not recent_interactions:
        return ""

    # Get last few interactions
    recent = recent_interactions[-10:]

    context = "RECENT CONVERSATION CONTEXT:\n"
    for interaction in recent:
        if interaction["type"] == "image_analysis":
            data = interaction["content"]
            context += f"[ANALYZED PRODUCT]: {data.get('item_name', 'Unknown')} - {data.get('category', '')} - Rp{data.get('listing_price', 0):,.0f}\n"
        elif interaction["type"] == "user_input":
            context += f"[USER]: {interaction['content']['message']}\n"
        elif interaction["type"] == "listing_created":
            context += f"[LISTING CREATED]: ID {interaction['content']['product_id']}\n"

    return context


def generate_product_id(category: str) -> str:
    """Generate simple product ID"""
    codes = {
        "motor": "MTR",
        "mobil": "CAR",
        "elektronik": "ELC",
        "furniture": "FUR",
        "pakaian": "CLT",
        "rumah": "HMS",
    }
    code = "PRD"
    for key, val in codes.items():
        if key in category.lower():
            code = val
            break
    return f"{code}_{random.randint(1000, 9999)}"


def analyze_image_with_ai(
    image_data: str, mime_type: str, user_notes: str = ""
) -> Dict:
    """Analyze image and generate product listing"""

    system_prompt = """Anda adalah AI ahli marketplace yang menganalisis foto produk dan membuat listing lengkap.

Berdasarkan foto, buat data produk dalam format JSON yang valid:

{
    "item_name": "Nama produk dengan brand/model jika terlihat",
    "category": "Kategori produk (motor, elektronik, furniture, dll)", 
    "description": "Deskripsi lengkap dan menarik produk",
    "condition": "Excellent/Good/Fair/Poor",
    "listing_price": 1000000,
    "target_price": 850000,
    "minimum_price": 700000,
    "selling_points": "3-5 poin menarik untuk pembeli",
    "known_flaws": "Masalah/kerusakan yang terlihat dari foto",
    "reason_selling": "Tebakan alasan menjual yang masuk akal",
    "delivery_info": "Info pengambilan/pengiriman"
}

PENTING:
- Harga dalam Rupiah
- Target price = 85% dari listing price
- Minimum price = 70% dari listing price  
- Analisis kondisi dari foto secara jujur
- Jika user memberikan notes tambahan, pertimbangkan dalam analisis"""

    user_prompt = f"Analisis foto produk ini dan buat listing marketplace lengkap.\n\nCatatan user: {user_notes}"

    try:
        response = client.chat.completions.create(
            model=os.getenv("OPENAI_VISION_MODEL", "gpt-4-vision-preview"),
            messages=[
                {"role": "system", "content": system_prompt},
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": user_prompt},
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:{mime_type};base64,{image_data}"
                            },
                        },
                    ],
                },
            ],
            max_tokens=1000,
            temperature=0.3,
        )

        result = response.choices[0].message.content.strip()

        # Clean JSON
        if "```json" in result:
            result = result.split("```json")[1].split("```")[0]
        elif "```" in result:
            result = result.split("```")[1].split("```")[0]

        data = json.loads(result)

        # Add to context AND set as current product
        add_interaction("image_analysis", data)
        set_current_product(data)

        return data

    except Exception as e:
        return {"error": f"Gagal analisis: {str(e)}"}


def process_user_message_with_ai(user_message: str) -> Dict:
    """Process user message with full AI understanding of context"""

    context = get_relevant_context(user_message)

    # Get the most recent product data for better context
    latest_product_data = None
    for interaction in reversed(recent_interactions):
        if interaction["type"] == "image_analysis":
            latest_product_data = interaction["content"]
            break

    system_prompt = f"""Anda adalah AI assistant marketplace yang membantu user membuat listing produk.

{context}

CURRENT PRODUCT DATA (if any):
{json.dumps(latest_product_data, indent=2, ensure_ascii=False) if latest_product_data else "No product data available"}

USER MESSAGE: {user_message}

TUGAS: Pahami maksud user dan tentukan tindakan yang tepat.

IMPORTANT RULES:
1. Jika ada CURRENT PRODUCT DATA dan user bilang "buat listing", "oke", "setuju" → action: "create_listing"
2. Jika user minta revisi (harga, kondisi, dll) dan ada CURRENT PRODUCT DATA → action: "apply_revision"
3. Jika tidak ada CURRENT PRODUCT DATA → action: "need_image"

Respons dalam format JSON:
{{
    "action": "welcome|need_image|show_preview|apply_revision|create_listing|clarification_needed",
    "product_data": {{}},  // Updated product data (copy dari CURRENT + modifications)
    "response_text": "Response yang akan dikirim ke user",
    "explanation": "Penjelasan tindakan yang diambil"
}}

ACTION GUIDELINES:
- create_listing: User setuju dengan listing (kata: "buat listing", "oke", "setuju", "jadi", "lanjut")
- apply_revision: User minta ubah sesuatu, update product_data
- need_image: Tidak ada product data, user harus upload foto
- clarification_needed: Tidak jelas maksudnya

REVISION EXAMPLES:
- "harga 5 juta" → update listing_price: 5000000, target_price: 4250000, minimum_price: 3500000
- "kondisi excellent" → update condition: "Excellent"
- "ada lecet di belakang" → tambahkan ke known_flaws

Berikan response yang natural dan helpful dalam Bahasa Indonesia."""

    try:
        response = client.chat.completions.create(
            model=os.getenv("OPENAI_MODEL", "gpt-3.5-turbo"),
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"User berkata: {user_message}"},
            ],
            max_tokens=800,
            temperature=0.3,
        )

        result = response.choices[0].message.content.strip()

        # Clean JSON
        if "```json" in result:
            result = result.split("```json")[1].split("```")[0]
        elif "```" in result:
            result = result.split("```")[1].split("```")[0]

        data = json.loads(result)

        # Add user input to context
        add_interaction(
            "user_input", {"message": user_message, "ai_action": data.get("action")}
        )

        return data

    except Exception as e:
        return {
            "action": "clarification_needed",
            "response_text": f"Maaf, saya mengalami gangguan teknis. Bisa coba lagi? Error: {str(e)}",
            "explanation": f"AI processing error: {str(e)}",
        }


def create_listing_api(product_data: Dict, seller_id: str) -> Tuple[bool, str]:
    """Create final listing via API"""
    try:
        product_id = generate_product_id(product_data.get("category", ""))

        listing = {
            "id": product_id,
            "name": product_data["item_name"],
            "description": product_data["description"],
            "price": product_data["listing_price"],
            "target_price": product_data["target_price"],
            "minimum_price": product_data["minimum_price"],
            "category": product_data["category"],
            "condition": product_data["condition"],
            "isActive": True,
            "createdBy": seller_id,
            "createdAt": int(datetime.now().timestamp() * 1000),
        }

        response = requests.post(f"{API_BASE_URL}/products", json=listing, timeout=10)

        if response.status_code in [200, 201]:
            # Add to context
            add_interaction(
                "listing_created", {"product_id": product_id, "data": product_data}
            )
            return True, product_id
        else:
            return False, f"API error: {response.status_code}"

    except Exception as e:
        return False, f"Error: {str(e)}"


def format_product_preview(data: Dict) -> str:
    """Format product preview nicely"""

    listing_price = f"Rp{data['listing_price']:,.0f}".replace(",", ".")
    target_price = f"Rp{data['target_price']:,.0f}".replace(",", ".")
    minimum_price = f"Rp{data['minimum_price']:,.0f}".replace(",", ".")

    return f"""✅ **Listing produk berhasil dibuat!**

🛍️ **{data['item_name']}**
📂 {data['category']} | ⭐ {data['condition']}

📝 **Deskripsi:**
{data['description']}

💰 **Strategi Harga:**
• **Listing:** {listing_price}
• **Target:** {target_price} ⭐  
• **Minimum:** {minimum_price} ❌

✨ **Poin menarik:** {data['selling_points']}
⚠️ **Perlu diketahui:** {data['known_flaws']}
📦 **Alasan jual:** {data['reason_selling']}
🚚 **Pengiriman:** {data['delivery_info']}

═══════════════════════

**Mau ubah sesuatu?** Bilang aja secara natural:
• "harga 5 juta" 
• "kondisinya excellent"
• "ada lecet di belakang"

**Kalau udah oke, ketik "buat listing"!** 😊"""


def create_chat_message(text: str) -> ChatMessage:
    """Create chat message"""
    return ChatMessage(
        timestamp=datetime.utcnow(),
        msg_id=uuid4(),
        content=[TextContent(type="text", text=text)],
    )


def create_metadata_message(metadata: dict) -> ChatMessage:
    """Create metadata message"""
    return ChatMessage(
        timestamp=datetime.utcnow(),
        msg_id=uuid4(),
        content=[MetadataContent(type="metadata", metadata=metadata)],
    )


@protocol.on_message(ChatMessage)
async def handle_message(ctx: Context, sender: str, msg: ChatMessage):
    """Stateless message handler - every message processed independently"""

    # Always acknowledge
    await ctx.send(
        sender,
        ChatAcknowledgement(
            timestamp=datetime.utcnow(), acknowledged_msg_id=msg.msg_id
        ),
    )

    try:
        ctx.logger.info(f"📨 Processing message from {sender}")

        # Extract content
        text_content = ""
        image_data = None
        mime_type = None

        for item in msg.content:
            if isinstance(item, StartSessionContent):
                await ctx.send(sender, create_metadata_message({"attachments": "true"}))
                return

            elif isinstance(item, TextContent):
                text_content += item.text + " "

            elif isinstance(item, ResourceContent):
                try:
                    storage = ExternalStorage(
                        identity=ctx.agent.identity, storage_url=STORAGE_URL
                    )
                    data = storage.download(str(item.resource_id))

                    if data["mime_type"].startswith("image/"):
                        image_data = data["contents"]
                        mime_type = data["mime_type"]
                        ctx.logger.info(f"📸 Image received: {mime_type}")
                    else:
                        await ctx.send(
                            sender,
                            create_chat_message(
                                f"❌ File {data['mime_type']} tidak didukung. Upload foto saja ya!"
                            ),
                        )
                        return

                except Exception as e:
                    ctx.logger.error(f"Failed to download file: {e}")
                    await ctx.send(
                        sender,
                        create_chat_message(
                            "❌ Gagal download file. Coba upload ulang!"
                        ),
                    )
                    return

        text_content = text_content.strip()

        # MAIN LOGIC: Process based on what we have
        if image_data:
            # Image uploaded - analyze it
            ctx.logger.info("🔍 Analyzing uploaded image...")

            await ctx.send(
                sender,
                create_chat_message(
                    "🔍 **Menganalisis foto produk...**\n\n⏳ AI sedang memproses gambar Anda..."
                ),
            )

            result = analyze_image_with_ai(image_data, mime_type, text_content)

            if "error" in result:
                response = f"❌ **Analisis gagal:** {result['error']}\n\nCoba upload foto yang lebih jelas ya! 📸"
            else:
                response = (
                    f"✅ **Analisis selesai!**\n\n{format_product_preview(result)}"
                )

        elif text_content:
            # Text message - let AI decide what to do
            ctx.logger.info(f"💬 Processing text: {text_content[:50]}...")

            # Debug: Check current context
            ctx.logger.info(f"📊 Context: {len(recent_interactions)} interactions")
            for i, interaction in enumerate(recent_interactions[-3:]):  # Last 3
                ctx.logger.info(
                    f"   {i}: {interaction['type']} - {str(interaction['content'])[:100]}..."
                )

            ai_decision = process_user_message_with_ai(text_content)
            action = ai_decision.get("action", "clarification_needed")

            ctx.logger.info(
                f"🤖 AI decision: {action} - {ai_decision.get('explanation', '')}"
            )

            # FALLBACK: Simple keyword detection if AI fails
            if action == "clarification_needed" or action == "need_image":
                text_lower = text_content.lower()
                create_keywords = [
                    "buat listing",
                    "buat",
                    "oke",
                    "ok",
                    "setuju",
                    "jadi",
                    "lanjut",
                    "siap",
                ]

                if any(keyword in text_lower for keyword in create_keywords):
                    ctx.logger.info("🔄 Fallback: Detected create listing keywords")
                    action = "create_listing"
                    ai_decision["action"] = "create_listing"

            if action == "create_listing":
                # User wants to create listing - use multiple fallbacks
                product_data = ai_decision.get("product_data", {})

                # Fallback 1: Get from global current product
                if not product_data or not product_data.get("item_name"):
                    ctx.logger.info(
                        "🔄 Fallback 1: Getting from global current product..."
                    )
                    product_data = get_current_product()

                # Fallback 2: Get from recent interactions
                if not product_data or not product_data.get("item_name"):
                    ctx.logger.info(
                        "🔄 Fallback 2: Getting from recent interactions..."
                    )
                    for interaction in reversed(recent_interactions):
                        if interaction["type"] == "image_analysis":
                            product_data = interaction["content"]
                            ctx.logger.info(
                                f"✅ Found in interactions: {product_data.get('item_name', 'Unknown')}"
                            )
                            break

                # Validate product data
                if product_data and product_data.get("item_name"):
                    ctx.logger.info(
                        f"🚀 Creating listing for: {product_data['item_name']}"
                    )
                    ctx.logger.info(
                        f"📊 Product data keys: {list(product_data.keys())}"
                    )

                    success, result = create_listing_api(product_data, sender)

                    if success:
                        product_id = result
                        clear_current_product()  # Clear after successful creation
                        response = f"""🎉 **Listing berhasil dibuat!**

**🆔 ID Produk:** `{product_id}`
**📦 Nama:** {product_data['item_name']}
**💰 Harga:** Rp{product_data['listing_price']:,.0f}

🤖 **AI Negotiator AKTIF!**

**Selanjutnya:**
1. Share ID Produk ke calon pembeli: **`{product_id}`**
2. Pembeli chat ke negotiator: `{product_id} Halo, masih available?`
3. AI handle negosiasi otomatis
4. AI tidak jual di bawah Rp{product_data['minimum_price']:,.0f}

**Produk Anda sudah online! 🚀**"""
                    else:
                        response = (
                            f"❌ **Gagal buat listing:** {result}\n\nCoba lagi ya!"
                        )
                else:
                    ctx.logger.warning("❌ No valid product data found anywhere")
                    ctx.logger.info(
                        f"📊 Recent interactions: {len(recent_interactions)}"
                    )
                    ctx.logger.info(
                        f"📊 Global product: {current_product_data is not None}"
                    )

                    # Debug: Show what's in recent interactions
                    for i, interaction in enumerate(recent_interactions[-3:]):
                        ctx.logger.info(
                            f"   Interaction {i}: {interaction['type']} - {str(interaction.get('content', {}))[:100]}"
                        )

                    response = """❌ **Tidak ada data produk untuk dibuat listing.**

**Debug Info:** Data produk hilang dari memory.

**Solusi:**
1. 📸 **Upload foto produk lagi**
2. 🤖 **Tunggu sampai muncul preview listing**
3. ✅ **Langsung ketik "buat listing"** (jangan tunggu lama)

**Upload foto produk Anda sekarang!** 📱"""

            elif action == "apply_revision":
                # User wants to modify something
                product_data = ai_decision.get("product_data", {})
                if product_data:
                    response = f"✅ **Perubahan diterapkan!**\n\n{format_product_preview(product_data)}"
                    # Update context
                    add_interaction("image_analysis", product_data)
                else:
                    response = ai_decision.get(
                        "response_text", "Perubahan tidak bisa diterapkan."
                    )

            else:
                # welcome, need_image, show_preview, clarification_needed
                response = ai_decision.get(
                    "response_text", "Maaf, saya tidak mengerti. Bisa dijelaskan lagi?"
                )

        else:
            # No image, no text - welcome
            response = """👋 **Selamat datang di AI Marketplace Assistant!**

**Cara pakai:**
1. 📸 **Upload foto produk** yang mau dijual
2. 🤖 **AI analisis** dan buat listing lengkap
3. 💬 **Chat natural** untuk revisi apapun
4. ✅ **Listing jadi** dengan ID produk siap jual

**Upload foto produk Anda sekarang!** 📱"""

    except Exception as e:
        ctx.logger.error(f"❌ Error processing message: {e}")
        response = "❌ Terjadi kesalahan sistem. Coba lagi ya!"

    # Send response
    await ctx.send(sender, create_chat_message(response))


@protocol.on_message(ChatAcknowledgement)
async def handle_ack(ctx: Context, sender: str, msg: ChatAcknowledgement):
    """Handle acknowledgements"""
    pass


# Attach protocol
agent.include(protocol, publish_manifest=True)


if __name__ == "__main__":
    # Check environment
    required_vars = ["OPENAI_API_KEY", "API_BASE_URL"]
    missing = [var for var in required_vars if not os.getenv(var)]

    if missing:
        print("❌ Missing environment variables:")
        for var in missing:
            print(f"   - {var}")
        exit(1)

    print("🤖 STATELESS CONTEXT-AWARE SELLER AGENT STARTING...")
    print("=" * 60)
    print("🎯 NEW APPROACH:")
    print("   ✅ Stateless architecture - no sessions!")
    print("   ✅ Context-aware AI processing")
    print("   ✅ Persistent memory of recent interactions")
    print("   ✅ Every message processed independently")
    print("   ✅ AI decides action based on full context")
    print("")
    print("🧠 HOW IT WORKS:")
    print("   • Store recent interactions in memory")
    print("   • AI gets full context for every message")
    print("   • Smart decision making based on conversation flow")
    print("   • No dependency on sender ID consistency")
    print("")
    print("💬 CONVERSATION EXAMPLES:")
    print("   User: [uploads photo]")
    print("   AI: Analyzes → Creates listing preview")
    print("   User: 'kondisi agak lecet bagian belakang'")
    print("   AI: Sees context → Updates known_flaws → Shows preview")
    print("   User: 'buat listing'")
    print("   AI: Creates final listing → Returns product ID")
    print("")
    print(f"📡 API: {API_BASE_URL}")
    print("🚀 Ready - no sessions, just smart AI!")
    print("=" * 60)

    agent.run()
