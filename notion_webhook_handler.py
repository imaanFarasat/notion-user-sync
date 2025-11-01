"""
Notion Webhook Handler
Handles webhook events from Notion to automatically sync users to HubSpot

Usage:
1. Set up a webhook endpoint (using Flask, FastAPI, or similar)
2. Configure Notion webhook to send events to your endpoint
3. This handler processes page.created and page.updated events
"""

from notion_hubspot_sync import sync_user_to_hubspot
import json
import os
from typing import Dict, Optional
from dotenv import load_dotenv

load_dotenv()

# Get Users database ID from environment
USERS_DATABASE_ID = os.getenv("NOTION_USERS_DATABASE_ID", None)


def is_user_page(event: Dict) -> bool:
    """Check if the event is for a user page in the Users database"""
    # Notion webhook structure has two possible formats:
    # 1. event.data.object.parent (for page.created/updated)
    # 2. event.data.parent (for page.properties_updated)
    
    event_data = event.get("data", {})
    
    # Check if it's a page entity
    entity = event.get("entity", {})
    if entity.get("type") != "page":
        return False
    
    # Get parent database info
    parent = event_data.get("parent", {})
    if not parent:
        # Try alternative structure (for page.created/updated)
        page_obj = event_data.get("object", {})
        parent = page_obj.get("parent", {})
    
    # Check parent type
    if parent.get("type") == "database" or parent.get("type") == "database_id":
        # Get database ID
        database_id = parent.get("id") or parent.get("database_id")
        
        if not database_id:
            return False
        
        # If we have the Users database ID, check if it matches
        if USERS_DATABASE_ID:
            # Remove hyphens for comparison (Notion IDs can have different formats)
            db_id_normalized = database_id.replace("-", "") if database_id else ""
            users_db_id_normalized = USERS_DATABASE_ID.replace("-", "")
            return db_id_normalized == users_db_id_normalized
        else:
            # If no database ID configured, accept all database pages (not ideal)
            return True
    
    return False


def handle_notion_webhook(event: Dict) -> Dict:
    """
    Handle a webhook event from Notion
    Returns a response dict with status
    """
    print(f"   🔍 Processing webhook event...")
    
    event_type = event.get("type")
    print(f"   📋 Event type: {event_type}")
    
    # Support multiple event types
    supported_types = ["page.created", "page.updated", "page.properties_updated"]
    if event_type not in supported_types:
        print(f"   ⏭️  Ignoring event type: {event_type}")
        return {
            "status": "ignored",
            "message": f"Event type {event_type} not handled"
        }
    
    # Get page ID from entity or data.object
    entity = event.get("entity", {})
    event_data = event.get("data", {})
    
    # Extract page ID
    if entity.get("type") == "page":
        page_id = entity.get("id")
        print(f"   📄 Page from entity: {page_id}")
    else:
        # Fallback to data.object structure
        page_obj = event_data.get("object", {})
        page_id = page_obj.get("id")
        print(f"   📄 Page from data.object: {page_id}")
    
    # Get page ID first
    if not page_id:
        print(f"   ❌ No page ID found")
        return {
            "status": "error",
            "message": "No page ID found in event"
        }
    
    print(f"   🆔 Page ID: {page_id}")
    
    # Check if it's a user page
    is_user = is_user_page(event)
    print(f"   👤 Is user page: {is_user}")
    
    if not is_user:
        print(f"   ⏭️  Not a user page, ignoring")
        return {
            "status": "ignored",
            "message": "Not a user page"
        }
    
    print(f"   🔄 Starting sync to HubSpot...")
    
    # Sync to HubSpot
    try:
        success = sync_user_to_hubspot(page_id)
        if success:
            print(f"   ✅ Successfully synced to HubSpot")
            return {
                "status": "success",
                "message": f"User {page_id} synced to HubSpot",
                "page_id": page_id
            }
        else:
            print(f"   ❌ Failed to sync to HubSpot")
            return {
                "status": "error",
                "message": f"Failed to sync user {page_id}",
                "page_id": page_id
            }
    except Exception as e:
        print(f"   ❌ Exception: {str(e)}")
        return {
            "status": "error",
            "message": f"Exception syncing user: {str(e)}",
            "page_id": page_id
        }


# Example Flask webhook endpoint (uncomment and adapt if using Flask)
"""
from flask import Flask, request, jsonify

app = Flask(__name__)

@app.route('/notion-webhook', methods=['POST'])
def notion_webhook():
    event = request.json
    result = handle_notion_webhook(event)
    return jsonify(result), 200 if result["status"] in ["success", "ignored"] else 500

if __name__ == '__main__':
    app.run(port=5000, debug=True)
"""


# Example FastAPI webhook endpoint (uncomment and adapt if using FastAPI)
"""
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

app = FastAPI()

@app.post('/notion-webhook')
async def notion_webhook(request: Request):
    event = await request.json()
    result = handle_notion_webhook(event)
    status_code = 200 if result["status"] in ["success", "ignored"] else 500
    return JSONResponse(content=result, status_code=status_code)

if __name__ == '__main__':
    import uvicorn
    uvicorn.run(app, host='0.0.0.0', port=5000)
"""

