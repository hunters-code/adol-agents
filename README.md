![tag:innovationlab](https://img.shields.io/badge/innovationlab-3D8BD3)


# 🤖 Adol AI Sales Negotiation Agent

> **Autonomous AI Agent for Marketplace Sales Negotiations**  
> Powered by Fetch.ai & Agentverse | Built for Indonesian E-commerce Markets

## 📋 Overview

The Adol AI Sales Negotiation Agent is an intelligent autonomous agent that handles end-to-end sales negotiations on behalf of sellers across multiple marketplace platforms. Built on the Fetch.ai framework and deployed on Agentverse, this agent provides professional-level negotiation capabilities with 24/7 availability.

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
- **Deployment**: [Agentverse Platform](https://agentverse.ai/)
- **AI Engine**: OpenAI GPT integration
- **Communication**: uAgents Chat Protocol
- **Backend**: Internet Computer (ICP) Canister
- **Languages**: Python 3.9+

## 🎮 How to Use

### 1. Agent Initialization

The agent automatically starts with these capabilities:
- ✅ Chat protocol integration
- ✅ OpenAI GPT connection
- ✅ Product API integration
- ✅ Multi-language detection
- ✅ Negotiation logic

### 2. Starting a Negotiation

**Format for buyers:**
```
[Product ID]
[Your message as buyer]

Example:
PROD123456
Hi, is this still available? I'm interested in buying it for Rp 900,000.
```

### 3. Agent Responses

The agent provides dual responses:
- **To Buyer**: Professional negotiation response
- **To Seller**: Status updates and action requirements

## 💬 Conversation Examples

### Successful Negotiation Flow

```
Buyer: "PROD123456 Hi, is this available? Will you take Rp 800,000?"

Agent Response:
[message_to_buyer]
Hi! Yes, the Bose QC35 II headphones are still available and in excellent 
condition. Your offer of Rp 800,000 is below our asking price of Rp 1,400,000. 
Considering the premium quality and excellent battery life, I can offer 
Rp 1,250,000. This is a great deal for these high-end headphones!

[message_to_seller]
[INFO] Buyer interested in PROD123456. Offered Rp 800,000, countered with 
Rp 1,250,000. Waiting for response.
```

### Information Query Handling

```
Buyer: "PROD123456 Are there any scratches on the charging port?"

Agent Response:
[message_to_buyer]
Let me check the specific condition details for you. I'll get back to you 
shortly with accurate information about the charging port condition.

[message_to_seller]
[ACTION REQUIRED] Buyer asking about charging port scratches on PROD123456. 
Please provide condition details.
```

## ⚙️ Configuration

### Pricing Strategy

The agent automatically calculates:
- **Listing Price**: Original seller price (100%)
- **Target Price**: Preferred sale price (85% of listing)
- **Minimum Price**: Absolute minimum (70% of listing)

### Negotiation Tactics

1. **Price Anchoring**: Always reference the listing price
2. **Value Emphasis**: Highlight product benefits and condition
3. **Urgency Creation**: Mention item popularity when appropriate
4. **Polite Decline**: Professional rejection of lowball offers
5. **Strategic Concessions**: Gradual price reductions within limits

### Language Detection

The agent automatically detects and responds in:
- **English**: For international buyers
- **Bahasa Indonesia**: For local Indonesian market

## 📊 Agent Capabilities

### Core Functions

| Function | Description | Status |
|----------|-------------|--------|
| Product Fetching | Retrieves item details from backend API | ✅ Active |
| Price Negotiation | Handles buyer offers within seller limits | ✅ Active |
| Q&A Management | Answers product questions intelligently | ✅ Active |
| Language Detection | Auto-detects and responds in appropriate language | ✅ Active |
| Seller Communication | Forwards important updates to seller | ✅ Active |
| Deal Closure | Finalizes agreements and logistics | ✅ Active |

### Advanced Features

- **Memory System**: Stores product-specific information learned during conversations
- **Context Awareness**: Maintains conversation context throughout negotiation
- **Error Handling**: Graceful handling of API failures and edge cases
- **Audit Trail**: Comprehensive logging of all interactions

## 🔗 API Integration

The AI agent integrates with the **Internet Computer (ICP) backend API** to fetch product data and send notifications to sellers. All API communications are secured through ICP's decentralized infrastructure.

### Backend Configuration
- **Platform**: Internet Computer Protocol (ICP)
- **Canister ID**: `ujk5g-liaaa-aaaam-aeocq-cai`
- **Network**: IC Mainnet
- **Authentication**: ICP Identity-based

### Product Details Endpoint

```python
GET /api/products/{product_id}
Host: ujk5g-liaaa-aaaam-aeocq-cai.ic0.app
Authorization: Bearer {icp_identity_token}

Response:
{
  "id": "PROD123456",
  "name": "Bose QuietComfort 35 II",
  "description": "Premium noise-canceling headphones...",
  "price": 1400000,
  "stock": 1,
  "isActive": true,
  "categoryId": "electronics",
  "imageUrl": "https://...",
  "createdBy": "seller123",
  "createdAt": 1234567890,
  "updatedAt": 1234567890
}
```

### Notification API Endpoints

The agent uses these ICP backend endpoints to communicate with sellers:

#### Send Seller Notification
```python
POST /api/notifications/send
Host: ujk5g-liaaa-aaaam-aeocq-cai.ic0.app
Content-Type: application/json
Authorization: Bearer {icp_identity_token}

Request Body:
{
  "sellerId": "seller123",
  "productId": "PROD123456",
  "type": "negotiation_update",
  "message": "New offer received: Rp 1,200,000",
  "data": {
    "buyerOffer": 1200000,
    "agentResponse": "Countered with Rp 1,250,000",
    "timestamp": "2024-08-26T10:30:00Z",
    "requiresAction": false
  }
}

Response:
{
  "success": true,
  "notificationId": "notif_abc123",
  "deliveredAt": "2024-08-26T10:30:01Z"
}
```

#### Send Action Required Alert
```python
POST /api/notifications/action-required
Host: ujk5g-liaaa-aaaam-aeocq-cai.ic0.app
Content-Type: application/json
Authorization: Bearer {icp_identity_token}

Request Body:
{
  "sellerId": "seller123",
  "productId": "PROD123456",
  "type": "seller_input_needed",
  "message": "Buyer asking about charging port condition",
  "data": {
    "buyerQuestion": "Are there any scratches on the charging port?",
    "urgency": "medium",
    "expectedResponse": "condition_details",
    "timestamp": "2024-08-26T10:45:00Z"
  }
}

Response:
{
  "success": true,
  "actionId": "action_xyz789",
  "notificationId": "notif_def456",
  "deliveredAt": "2024-08-26T10:45:01Z"
}
```

#### Send Deal Completion Alert
```python
POST /api/notifications/deal-closed
Host: ujk5g-liaaa-aaaam-aeocq-cai.ic0.app
Content-Type: application/json
Authorization: Bearer {icp_identity_token}

Request Body:
{
  "sellerId": "seller123",
  "productId": "PROD123456",
  "type": "sale_completed",
  "message": "Item sold successfully for Rp 1,250,000",
  "data": {
    "finalPrice": 1250000,
    "buyerDetails": {
      "contactInfo": "buyer_contact_encrypted",
      "pickupPreference": "seller_location"
    },
    "commission": {
      "amount": 125000,
      "percentage": 10
    },
    "timestamp": "2024-08-26T11:00:00Z"
  }
}

Response:
{
  "success": true,
  "saleId": "sale_completed_123",
  "notificationId": "notif_ghi789",
  "deliveredAt": "2024-08-26T11:00:01Z",
  "nextSteps": [
    "Prepare item for pickup",
    "Wait for buyer contact",
    "Commission will be deducted from credits"
  ]
}
```

### Chat Protocol Messages

```python
# Incoming buyer message
{
  "type": "ChatMessage",
  "content": [{"type": "text", "text": "PROD123456 Hi, interested!"}],
  "timestamp": "2024-08-26T10:00:00Z",
  "msg_id": "uuid-here"
}

# Agent response
{
  "type": "ChatMessage", 
  "content": [{"type": "text", "text": "Hello! This item is available..."}],
  "timestamp": "2024-08-26T10:00:01Z",
  "msg_id": "uuid-here"
}
```

## 🎯 Agent URL

**Live Agent**: https://agentverse.ai/agents/details/agent1qd2mu8zses2cxgd46wn9d79esn6u64juz00sg7w0qc5zsxa2v0fgs9c5a6w/profile

### Connecting to the Agent

1. Visit the Agentverse agent profile
2. Click "Start Chat" or "Connect"
3. Send a message with format: `[PRODUCT_ID] [Your message]`
4. The agent will respond with professional negotiation


## 📄 License

This project is part of the Adol AI Sales Agent ecosystem. See main project for licensing details.

---

**🔗 Related Links**
- [Main Project Repository](https://github.com/Hackathon-Hunter/adol-website)  
- [Backend Repository](https://github.com/Hackathon-Hunter/adol-icp-backend)
- [Fetch.ai Documentation](https://docs.fetch.ai/)
- [Agentverse Platform](https://agentverse.ai/)

Built with ❤️ using Fetch.ai & Internet Computer Protocol
