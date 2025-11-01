"""
Notion Webhook Server for HubSpot User Sync
Real-time webhook server that syncs users when they're created/updated in Notion

Run this server and set up Notion webhook to point to it
"""

from flask import Flask, request, jsonify
import os
from dotenv import load_dotenv
from notion_webhook_handler import handle_notion_webhook
from hubspot_webhook_handler import handle_hubspot_user_webhook

# Load environment variables
load_dotenv()

app = Flask(__name__)

# Configuration
# Railway and other cloud services set PORT environment variable
PORT = int(os.getenv("PORT", os.getenv("WEBHOOK_PORT", "5000")))
HOST = os.getenv("WEBHOOK_HOST", "0.0.0.0")

@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    return jsonify({
        "status": "healthy",
        "service": "Notion to HubSpot User Sync Webhook"
    }), 200

@app.route('/notion-webhook', methods=['GET', 'POST'])
def notion_webhook():
    """
    Main webhook endpoint for Notion events
    Handles both GET (verification) and POST (events)
    """
    # Handle GET request (webhook verification)
    if request.method == 'GET':
        # Notion may send a verification request
        # Return 200 to confirm endpoint is working
        return jsonify({
            "status": "ready",
            "message": "Webhook endpoint is ready to receive events",
            "endpoint": "/notion-webhook"
        }), 200
    
    # Handle POST request (webhook events)
    try:
        # Handle case where request has no JSON body (verification might be in query params or headers)
        if not request.is_json:
            # Check for token in query parameters
            token = request.args.get('token') or request.args.get('challenge') or request.args.get('verification_token')
            if token:
                print(f"   ✅ Verification token from query params: {token}")
                return jsonify({"challenge": token, "token": token}), 200
            
            # Check headers for token
            token_header = request.headers.get('X-Notion-Verification-Token') or request.headers.get('Notion-Verification-Token')
            if token_header:
                print(f"   ✅ Verification token from headers: {token_header}")
                return jsonify({"challenge": token_header, "token": token_header}), 200
            
            # Return empty JSON if no JSON body
            return jsonify({
                "status": "ready",
                "message": "Endpoint is ready"
            }), 200
        
        # Get the webhook event
        event = request.json
        
        if not event:
            return jsonify({
                "status": "error",
                "message": "No event data received"
            }), 400
        
        # Log the incoming request for debugging
        print(f"\n📨 Received webhook request:")
        print(f"   Method: {request.method}")
        print(f"   Headers: {dict(request.headers)}")
        print(f"   Data: {event}")
        
        # Check if this is a verification challenge
        # Notion sends verification tokens in different formats:
        # 1. As "challenge" field - echo it back
        # 2. As "token" field - return it
        # 3. In request body - return the whole response
        
        if isinstance(event, dict):
            # Check for challenge token
            challenge = event.get("challenge") or event.get("token") or event.get("verification_token")
            if challenge:
                # Echo back the challenge for verification
                print(f"   ✅ Verification token received: {challenge}")
                return jsonify({"challenge": challenge}), 200
            
            # Check if it's a verification request
            if event.get("type") == "verification" or "verify" in str(event).lower():
                # Return the token if present
                token = event.get("token") or event.get("challenge")
                if token:
                    print(f"   ✅ Verification token: {token}")
                    return jsonify({"token": token, "challenge": token}), 200
        
        # Handle the webhook event
        result = handle_notion_webhook(event)
        
        # Return appropriate status code
        if result["status"] == "success":
            return jsonify(result), 200
        elif result["status"] == "ignored":
            return jsonify(result), 200  # Still OK, just not a user page
        else:
            return jsonify(result), 500
            
    except Exception as e:
        print(f"   ❌ Error: {str(e)}")
        return jsonify({
            "status": "error",
            "message": f"Exception handling webhook: {str(e)}"
        }), 500

@app.route('/hubspot-webhook', methods=['POST', 'GET'])
def hubspot_webhook():
    """
    Webhook endpoint for HubSpot events
    Normalizes user names (capitalizes first letters)
    """
    # Handle GET request (verification)
    if request.method == 'GET':
        return jsonify({
            "status": "ready",
            "message": "HubSpot webhook endpoint is ready to receive events",
            "endpoint": "/hubspot-webhook"
        }), 200
    
    # Handle POST request (webhook events)
    try:
        event = request.json
        
        if not event:
            return jsonify({
                "status": "error",
                "message": "No event data received"
            }), 400
        
        # Log the incoming request
        print(f"\n📨 Received HubSpot webhook request:")
        print(f"   Method: {request.method}")
        print(f"   Data: {event}")
        
        # Handle the webhook event
        result = handle_hubspot_user_webhook(event)
        
        # Return appropriate status code
        if result["status"] == "success":
            return jsonify(result), 200
        elif result["status"] == "ignored":
            return jsonify(result), 200
        else:
            return jsonify(result), 500
            
    except Exception as e:
        print(f"   ❌ Error: {str(e)}")
        return jsonify({
            "status": "error",
            "message": f"Exception handling HubSpot webhook: {str(e)}"
        }), 500

@app.route('/', methods=['GET'])
def home():
    """Home page with instructions"""
    return jsonify({
        "service": "Notion to HubSpot User Sync Webhook",
        "endpoints": {
            "/notion-webhook": "POST - Webhook endpoint for Notion events (syncs users to HubSpot)",
            "/hubspot-webhook": "POST - Webhook endpoint for HubSpot events (normalizes names)",
            "/health": "GET - Health check"
        },
        "instructions": {
            "1": "Notion webhook: Configure in Notion → https://your-server.com/notion-webhook",
            "2": "HubSpot webhook: Configure in HubSpot → https://your-server.com/hubspot-webhook",
            "3": "HubSpot webhook normalizes user names (capitalizes first letters)"
        }
    }), 200

if __name__ == '__main__':
    print("=" * 60)
    print("Notion to HubSpot Webhook Server")
    print("=" * 60)
    print(f"\n🌐 Server starting on: http://localhost:{PORT}")
    print(f"📡 Notion webhook: http://localhost:{PORT}/notion-webhook")
    print(f"📡 HubSpot webhook: http://localhost:{PORT}/hubspot-webhook")
    print(f"❤️  Health check: http://localhost:{PORT}/health")
    print("\n📝 Next steps:")
    print("  1. For local testing, use ngrok:")
    print("     ngrok http 5000")
    print("  2. Copy the ngrok HTTPS URL")
    print("  3. Configure Notion webhook → https://your-server.com/notion-webhook")
    print("  4. Configure HubSpot webhook → https://your-server.com/hubspot-webhook")
    print("     (Note: HubSpot user webhooks may need custom setup)")
    print("\n" + "=" * 60 + "\n")
    
    app.run(host=HOST, port=PORT, debug=True)

