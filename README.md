![tag:innovationlab](https://img.shields.io/badge/innovationlab-3D8BD3)

# 🤖 Adol AI Sales Negotiation Agent

> **Autonomous AI Agent for Marketplace Sales Negotiations**  
> Powered by Fetch.ai & Agentverse | Built for Indonesian E-commerce Markets

## 📋 Overview

The Adol AI Sales Negotiation Agent is an intelligent autonomous agent that handles end-to-end sales negotiations on behalf of sellers across multiple marketplace platforms. Built on the Fetch.ai framework and deployable both locally and on Agentverse, this agent provides professional-level negotiation capabilities with 24/7 availability.

### 🎯 Key Features

- **Autonomous Negotiations**: Handles buyer interactions independently within seller-defined parameters
- **Multi-Language Support**: Operates in English and Indonesian (Bahasa Indonesia)
- **Strategic Pricing**: Maintains target pricing while maximizing sale opportunities
- **Intelligent Escalation**: Only forwards serious offers within acceptable price ranges
- **Dynamic Knowledge**: Learns and stores product information during conversations
- **Platform Integration**: Works across Facebook Marketplace, Tokopedia, Shopee, and more

## 🏗️ Architecture

### Technology Stack

- **Framework**: [Fetch.ai uAgents](https://fetch.ai/)
- **Deployment**: Local development + [Agentverse Platform](https://agentverse.ai/)
- **AI Engine**: OpenAI GPT integration
- **Communication**: uAgents Chat Protocol
- **Backend**: Internet Computer (ICP) Canister / Mock API
- **Languages**: Python 3.9+

## 🚀 Local Development Setup

### Prerequisites

- Python 3.9 or higher
- pip package manager
- Git
- OpenAI API key (or OpenRouter API key)

### Installation

1. **Clone the Repository**
```bash
git clone https://github.com/hunters-code/adol-agents.git
cd adol-agents
```

2. **Create Virtual Environment**
```bash
python -m venv venv

# On Windows
venv\Scripts\activate

# On macOS/Linux
source venv/bin/activate
```

3. **Install Dependencies**
```bash
pip install -r requirements.txt
```

4. **Environment Configuration**

Copy the example environment file and configure it:
```bash
cp .env.example .env
```

Edit `.env` file with your configuration:
```bash
# OpenAI Configuration (required)
OPENAI_API_KEY=your_openai_or_openrouter_api_key_here
OPENAI_BASE_URL=https://openrouter.ai/api/v1
OPENAI_MODEL=gpt-3.5-turbo
OPENAI_VISION_MODEL=gpt-4-vision-preview
OPENAI_MAX_TOKENS=500
OPENAI_TEMPERATURE=0.7

# API Backend (for product data)
API_BASE_URL=https://dummyjson.com/c/a2d5-5008-4347-9d22
```

### Project Structure

```
adol-agents/
├── agents/
│   ├── __init__.py           # Empty init file
│   ├── image_analyzer.py     # Empty (placeholder)
│   ├── product_listing.py    # Product listing agent with image analysis
│   └── negotiator.py         # Sales negotiation agent
├── app.py                    # Flask web server (basic setup)
├── requirements.txt          # Python dependencies
├── .env.example             # Environment configuration template
├── .gitignore              # Git ignore rules
└── README.md               # This file
```

## 🎮 How to Use

### 1. Running the Product Listing Agent

The product listing agent handles image analysis and product listing creation:

```bash
# Run the product listing agent
python agents/product_listing.py
```

**Features:**
- ✅ Image analysis with AI
- ✅ Product listing generation
- ✅ Price estimation and strategy
- ✅ Context-aware conversations
- ✅ Product memory management

### 2. Running the Sales Negotiation Agent

The negotiation agent handles buyer interactions and price negotiations:

```bash
# Run the negotiation agent
python agents/negotiator.py
```

**Features:**
- ✅ Buyer message handling
- ✅ Price negotiation logic
- ✅ Product information retrieval
- ✅ Multi-language support (English/Indonesian)
- ✅ Conversation history management

### 3. Running the Flask Web Server (Optional)

Basic web server setup for API endpoints:

```bash
# Run the web server
python app.py
```

## 💬 Agent Usage Examples

### Product Listing Agent

**Upload a product image and get a complete listing:**

1. Start the agent: `python agents/product_listing.py`
2. Connect via Agentverse or uAgents protocol
3. Upload an image of your product
4. The AI will analyze and create a complete product listing
5. Review and approve the listing
6. Say "buat listing" (create listing) to finalize

**Example conversation:**
```
User: [uploads photo of motorcycle]
Agent: ✅ Analisis selesai!

🛍️ **Honda Beat 2019**
📂 motor | ⭐ Good

💰 **Strategi Harga:**
• **Listing:** Rp18.500.000
• **Target:** Rp15.725.000 ⭐  
• **Minimum:** Rp12.950.000 ❌

User: kondisi agak lecet di spakbor belakang
Agent: [updates known_flaws and shows updated preview]

User: buat listing
Agent: 🎉 **Listing berhasil dibuat!** ID Produk: MTR_1234
```

### Sales Negotiation Agent

**Handle buyer negotiations automatically:**

1. Start the agent: `python agents/negotiator.py`
2. Buyers send: `product_1 Hi, is this still available?`
3. Agent handles all negotiations within your price limits

**Example negotiation:**
```
Buyer: product_1 Hi, interested in this item. Will you take Rp 800,000?
Agent: Hi! Yes, the item is still available. Your offer of Rp 800,000 is below 
our asking price of Rp 1,400,000. Considering the excellent condition, I can 
offer Rp 1,250,000. This is a great deal!

Buyer: How about Rp 1,000,000?
Agent: I understand you're looking for a good deal. The lowest I can go is 
Rp 1,200,000. This is already a significant discount from the original price.
```

## ⚙️ Configuration

### Pricing Strategy

Both agents use automatic pricing calculations:
- **Listing Price**: AI-estimated market price (100%)
- **Target Price**: Preferred sale price (85% of listing)
- **Minimum Price**: Absolute minimum (70% of listing)

### AI Models Configuration

```bash
# Use OpenAI directly
OPENAI_BASE_URL=https://api.openai.com/v1
OPENAI_MODEL=gpt-3.5-turbo
OPENAI_VISION_MODEL=gpt-4-vision-preview

# Use OpenRouter (recommended for cost)
OPENAI_BASE_URL=https://openrouter.ai/api/v1
OPENAI_MODEL=gpt-3.5-turbo
OPENAI_VISION_MODEL=gpt-4-vision-preview
```

### Language Support

The negotiation agent automatically detects and responds in:
- **English**: For international buyers
- **Bahasa Indonesia**: For local Indonesian market

## 🔧 Development & Testing

### Running Individual Agents

```bash
# Test product listing agent
python agents/product_listing.py

# Test negotiation agent  
python agents/negotiator.py

# Run web server (optional)
python app.py
```

### Environment Variables

```bash
# Required
OPENAI_API_KEY=your_api_key_here

# Optional (with defaults)
OPENAI_BASE_URL=https://openrouter.ai/api/v1
OPENAI_MODEL=gpt-3.5-turbo
OPENAI_VISION_MODEL=gpt-4-vision-preview
OPENAI_MAX_TOKENS=500
OPENAI_TEMPERATURE=0.7
API_BASE_URL=https://dummyjson.com/c/a2d5-5008-4347-9d22
```

### Debugging

Enable debug logging by checking the console output when running the agents. Both agents include comprehensive logging for troubleshooting.

## 🔗 API Integration

### Product Data API

The agents integrate with a backend API to fetch product information:

```python
# Default API endpoint (mock data for testing)
API_BASE_URL = "https://dummyjson.com/c/a2d5-5008-4347-9d22"

# Product endpoint
GET /products/{product_id}

# Example response
{
  "id": "product_1",
  "name": "Bose QuietComfort 35 II",
  "description": "Premium noise-canceling headphones...",
  "price": 1400000,
  "stock": 1,
  "isActive": true,
  "categoryId": "electronics"
}
```

### Creating New Products

The product listing agent can create new products via API:

```python
POST /products
Content-Type: application/json

{
  "id": "MTR_1234",
  "name": "Honda Beat 2019",
  "description": "Well-maintained motorcycle...",
  "price": 18500000,
  "target_price": 15725000,
  "minimum_price": 12950000,
  "category": "motor",
  "condition": "Good"
}
```

## 📦 Deployment to Agentverse

### Deploy Product Listing Agent

1. **Test Locally First**
```bash
python agents/product_listing.py
```

2. **Upload to Agentverse**
- Visit [Agentverse](https://agentverse.ai/)
- Create new agent
- Upload `agents/product_listing.py`
- Configure environment variables
- Deploy

### Deploy Negotiation Agent

1. **Test Locally**
```bash
python agents/negotiator.py
```

2. **Upload to Agentverse**
- Create separate agent for negotiation
- Upload `agents/negotiator.py`
- Configure API endpoints
- Deploy

### Production Agents

**Live Negotiation Agent**: https://agentverse.ai/agents/details/agent1qd2mu8zses2cxgd46wn9d79esn6u64juz00sg7w0qc5zsxa2v0fgs9c5a6w/profile

## 🎯 Agent Capabilities

### Product Listing Agent

| Function | Description | Status |
|----------|-------------|--------|
| Image Analysis | AI-powered product recognition from photos | ✅ Active |
| Listing Generation | Complete product listings with pricing strategy | ✅ Active |
| Context Management | Remembers product details during conversation | ✅ Active |
| Price Strategy | Automatic target/minimum price calculation | ✅ Active |
| Natural Language | Processes user input and modifications | ✅ Active |

### Sales Negotiation Agent

| Function | Description | Status |
|----------|-------------|--------|
| Product Fetching | Retrieves item details from backend API | ✅ Active |
| Price Negotiation | Handles buyer offers within seller limits | ✅ Active |
| Q&A Management | Answers product questions intelligently | ✅ Active |
| Language Detection | Auto-detects and responds in appropriate language | ✅ Active |
| Conversation History | Maintains context throughout negotiation | ✅ Active |
| Deal Closure | Finalizes agreements within price limits | ✅ Active |

## 🧪 Testing

### Manual Testing Scripts

Create test scripts to validate agent behavior:

```python
# test_agents.py
import asyncio
from agents.negotiator import agent as negotiator_agent
from agents.product_listing import agent as listing_agent

async def test_negotiation():
    # Test negotiation flow
    test_message = "product_1 Hi, is this available? I can pay 1,200,000"
    # Send to negotiation agent
    print("Testing negotiation agent...")

async def test_listing():
    # Test listing creation
    print("Testing product listing agent...")

if __name__ == "__main__":
    asyncio.run(test_negotiation())
```

### Integration Testing

Test the complete flow from listing creation to negotiation:

1. Create a product with the listing agent
2. Use the product ID with the negotiation agent
3. Test buyer interactions and price negotiations

## 🔍 Troubleshooting

### Common Issues

1. **Missing OpenAI API Key**
```bash
Error: Missing environment variables: OPENAI_API_KEY
Solution: Set OPENAI_API_KEY in your .env file
```

2. **Product Not Found**
```bash
Error: Product ID not found in API
Solution: Ensure the product exists or use test product IDs like "product_1"
```

3. **Agent Connection Issues**
```bash
Error: Failed to connect to Agentverse
Solution: Check internet connection and agent configuration
```

### Debug Mode

Both agents include comprehensive logging. Check console output for detailed debugging information.

## 📊 Monitoring

### Conversation Logging

Both agents automatically log:
- Message interactions
- Price negotiations
- Product inquiries
- Error conditions
- Performance metrics

### Analytics

Track agent performance:
- Successful negotiations
- Average negotiation time
- Price acceptance rates
- User satisfaction metrics

## 🤝 Contributing

### Development Workflow

1. **Fork the Repository**
2. **Create Feature Branch**
```bash
git checkout -b feature/your-feature-name
```

3. **Test Your Changes**
```bash
# Test both agents
python agents/product_listing.py
python agents/negotiator.py
```

4. **Commit and Push**
```bash
git commit -m "Add: your feature description"
git push origin feature/your-feature-name
```

5. **Create Pull Request**

### Code Standards

- Follow existing code structure
- Add comprehensive logging
- Test with both agents
- Update documentation

## 📄 License

This project is part of the Adol AI Sales Agent ecosystem. Licensed under MIT License.

---

**🔗 Related Links**
- [Main Project Repository](https://github.com/Hackathon-Hunter/adol-website)  
- [Backend Repository](https://github.com/Hackathon-Hunter/adol-icp-backend)
- [Fetch.ai Documentation](https://docs.fetch.ai/)
- [Agentverse Platform](https://agentverse.ai/)

Built with ❤️ using Fetch.ai & Internet Computer Protocol

## 📞 Support & Contact

- **Issues**: [GitHub Issues](https://github.com/Hackathon-Hunter/adol-agents/issues)
- **Documentation**: [Project Wiki](https://github.com/Hackathon-Hunter/adol-agents/wiki)
- **Community**: Join our Discord for real-time support