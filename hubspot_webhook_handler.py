"""
HubSpot Webhook Handler
Handles webhook events from HubSpot to normalize user names (capitalize first letters)
"""

import requests
import os
from typing import Dict, Optional
from dotenv import load_dotenv

load_dotenv()

HUBSPOT_ACCESS_TOKEN = os.getenv("HUBSPOT_ACCESS_TOKEN", None)
HUBSPOT_BASE_URL = "https://api.hubapi.com"

HUBSPOT_HEADERS = {
    "Content-Type": "application/json",
    "Authorization": f"Bearer {HUBSPOT_ACCESS_TOKEN}"
}


def capitalize_name(name: str) -> str:
    """
    Capitalize the first letter of a name
    
    Examples:
        "john" → "John"
        "mary jane" → "Mary jane"
        "O'CONNOR" → "O'connor"
        "" → ""
    """
    if not name or not name.strip():
        return name
    
    # Trim whitespace
    name = name.strip()
    
    # Capitalize first letter, keep rest as-is
    if len(name) > 0:
        return name[0].upper() + name[1:] if len(name) > 1 else name[0].upper()
    
    return name


def normalize_user_name(first_name: str, last_name: str) -> tuple:
    """
    Normalize user names by capitalizing first letters
    
    Args:
        first_name: Current first name
        last_name: Current last name
    
    Returns:
        Tuple of (normalized_first_name, normalized_last_name)
    """
    normalized_first = capitalize_name(first_name) if first_name else ""
    normalized_last = capitalize_name(last_name) if last_name else ""
    
    return (normalized_first, normalized_last)


def get_hubspot_user(user_id: str) -> Optional[Dict]:
    """Get a user from HubSpot by user ID"""
    if not HUBSPOT_ACCESS_TOKEN:
        print("  ✗ Error: HUBSPOT_ACCESS_TOKEN not set")
        return None
    
    url = f"{HUBSPOT_BASE_URL}/settings/v3/users/{user_id}"
    response = requests.get(url, headers=HUBSPOT_HEADERS)
    
    if response.status_code == 200:
        return response.json()
    else:
        print(f"  ✗ Error getting HubSpot user: {response.status_code}")
        print(f"    Response: {response.text}")
        return None


def update_hubspot_user_name(user_id: str, first_name: str, last_name: str) -> bool:
    """
    Update a user's first and last name in HubSpot
    
    Args:
        user_id: HubSpot user ID
        first_name: New first name
        last_name: New last name
    
    Returns:
        True if successful, False otherwise
    """
    if not HUBSPOT_ACCESS_TOKEN:
        print("  ✗ Error: HUBSPOT_ACCESS_TOKEN not set")
        return False
    
    url = f"{HUBSPOT_BASE_URL}/settings/v3/users/{user_id}"
    
    payload = {}
    if first_name:
        payload["firstName"] = first_name
    if last_name:
        payload["lastName"] = last_name
    
    if not payload:
        print("  ℹ️  No names to update")
        return True
    
    response = requests.patch(url, headers=HUBSPOT_HEADERS, json=payload)
    
    if response.status_code == 200:
        print(f"  ✅ Updated user name: {first_name} {last_name}")
        return True
    else:
        print(f"  ✗ Error updating user: {response.status_code}")
        print(f"    Response: {response.text}")
        return False


def handle_hubspot_user_webhook(event: Dict) -> Dict:
    """
    Handle a webhook event from HubSpot
    Normalizes user names (capitalizes first letters)
    
    Works for:
    - Users created/updated via Notion sync
    - Users created/updated directly in HubSpot
    
    Args:
        event: Webhook event data from HubSpot
    
    Returns:
        Response dict with status
    """
    print(f"   🔍 Processing HubSpot webhook event...")
    
    # HubSpot webhook structure varies, check common formats
    event_type = event.get("eventType") or event.get("subscriptionType") or event.get("type")
    print(f"   📋 Event type: {event_type}")
    
    # Extract user information from different webhook formats
    user_id = None
    user_data = None
    
    # Format 1: Standard HubSpot subscription webhook (subscriptionId, portalId, eventType, objectId)
    if "objectId" in event:
        user_id = str(event.get("objectId"))
        # Properties might be in event or need to fetch from API
        user_data = event.get("properties", {})
        print(f"   📦 Found objectId format: {user_id}")
    
    # Format 2: user.create or user.propertyChange (userId directly)
    elif "userId" in event:
        user_id = str(event.get("userId"))
        user_data = event.get("properties", {})
        print(f"   📦 Found userId format: {user_id}")
    
    # Format 3: Full user object in response
    elif "id" in event:
        # Check if this looks like a user object
        if event.get("type") == "USER" or "email" in event or "firstName" in event:
            user_id = str(event.get("id"))
            user_data = event
            print(f"   📦 Found user object format: {user_id}")
    
    # Format 4: HubSpot contact/object webhook with associations
    elif "objectType" in event:
        if event.get("objectType") == "USER" or event.get("objectType") == "USER_DEFINED":
            user_id = str(event.get("objectId", ""))
            user_data = event.get("properties", {})
            print(f"   📦 Found objectType format: {user_id}")
    
    if not user_id:
        print(f"   ⏭️  No user ID found in webhook event (may not be a user event)")
        print(f"   📄 Event keys: {list(event.keys())}")
        return {
            "status": "ignored",
            "message": "No user ID found in webhook event"
        }
    
    print(f"   🆔 User ID: {user_id}")
    
    # Get current user data from HubSpot API (more reliable than webhook payload)
    user = get_hubspot_user(user_id)
    if not user:
        print(f"   ❌ Could not retrieve user from HubSpot")
        return {
            "status": "error",
            "message": f"Could not retrieve user {user_id}"
        }
    
    # Extract current names from API response (most reliable)
    current_first = user.get("firstName", "") or ""
    current_last = user.get("lastName", "") or ""
    
    # If names are empty, try from webhook payload
    if not current_first and user_data:
        current_first = user_data.get("firstName", "") or ""
    if not current_last and user_data:
        current_last = user_data.get("lastName", "") or ""
    
    print(f"   📝 Current names: '{current_first}' '{current_last}'")
    
    # Skip if no names to normalize
    if not current_first and not current_last:
        print(f"   ⏭️  No names found, skipping normalization")
        return {
            "status": "ignored",
            "message": "User has no first or last name to normalize"
        }
    
    # Normalize names
    normalized_first, normalized_last = normalize_user_name(current_first, current_last)
    
    print(f"   ✨ Normalized names: '{normalized_first}' '{normalized_last}'")
    
    # Check if update is needed
    needs_update = (current_first != normalized_first) or (current_last != normalized_last)
    
    if not needs_update:
        print(f"   ✅ Names already normalized, no update needed")
        return {
            "status": "ignored",
            "message": "Names already normalized"
        }
    
    # Update user in HubSpot
    print(f"   🔄 Updating user names in HubSpot...")
    success = update_hubspot_user_name(user_id, normalized_first, normalized_last)
    
    if success:
        print(f"   ✅ Successfully normalized user name")
        return {
            "status": "success",
            "message": f"User {user_id} name normalized",
            "user_id": user_id,
            "before": {"firstName": current_first, "lastName": current_last},
            "after": {"firstName": normalized_first, "lastName": normalized_last}
        }
    else:
        return {
            "status": "error",
            "message": f"Failed to normalize user {user_id}",
            "user_id": user_id
        }

