"""
Notion Webhook Server for HubSpot User Sync
Real-time webhook server that syncs users when they're created/updated in Notion

Run this server and set up Notion webhook to point to it
"""

from flask import Flask, request, jsonify
import os
from dotenv import load_dotenv
from notion_webhook_handler import handle_notion_webhook

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

@app.route('/notion-webhook', methods=['POST'])
def notion_webhook():
    """
    Main webhook endpoint for Notion events
    """
    try:
        # Get the webhook event
        event = request.json
        
        if not event:
            return jsonify({
                "status": "error",
                "message": "No event data received"
            }), 400
        
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
        return jsonify({
            "status": "error",
            "message": f"Exception handling webhook: {str(e)}"
        }), 500

@app.route('/', methods=['GET'])
def home():
    """Home page with instructions"""
    return jsonify({
        "service": "Notion to HubSpot User Sync Webhook",
        "endpoints": {
            "/notion-webhook": "POST - Webhook endpoint for Notion events",
            "/health": "GET - Health check"
        },
        "instructions": {
            "1": "Make this server publicly accessible (use ngrok for local testing)",
            "2": "Configure Notion webhook to point to: https://your-server.com/notion-webhook",
            "3": "Webhook will automatically sync users when created/updated in Notion"
        }
    }), 200

if __name__ == '__main__':
    print("=" * 60)
    print("Notion to HubSpot Webhook Server")
    print("=" * 60)
    print(f"\n🌐 Server starting on: http://localhost:{PORT}")
    print(f"📡 Webhook endpoint: http://localhost:{PORT}/notion-webhook")
    print(f"❤️  Health check: http://localhost:{PORT}/health")
    print("\n📝 Next steps:")
    print("  1. For local testing, use ngrok:")
    print("     ngrok http 5000")
    print("  2. Copy the ngrok HTTPS URL")
    print("  3. Configure Notion webhook (see instructions below)")
    print("\n" + "=" * 60 + "\n")
    
    app.run(host=HOST, port=PORT, debug=True)

