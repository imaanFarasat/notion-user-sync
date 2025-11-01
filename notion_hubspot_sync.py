"""
Notion to HubSpot User Sync
Syncs users created/updated in Notion to HubSpot automatically
"""

import requests
import json
import os
from typing import Dict, Optional
from datetime import datetime

# Try to load from .env file if python-dotenv is available
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# Configuration
NOTION_TOKEN = os.getenv("NOTION_TOKEN", os.getenv("NOTION_API_KEY", None))
NOTION_VERSION = "2022-06-28"
NOTION_BASE_URL = "https://api.notion.com/v1"

HUBSPOT_ACCESS_TOKEN = os.getenv("HUBSPOT_ACCESS_TOKEN", None)
HUBSPOT_BASE_URL = "https://api.hubapi.com"

# Headers
NOTION_HEADERS = {
    "Authorization": f"Bearer {NOTION_TOKEN}",
    "Content-Type": "application/json",
    "Notion-Version": NOTION_VERSION
}

HUBSPOT_HEADERS = {
    "Content-Type": "application/json",
    "Authorization": f"Bearer {HUBSPOT_ACCESS_TOKEN}"
}


def get_notion_user(user_page_id: str) -> Optional[Dict]:
    """Get a user page from Notion by page ID"""
    url = f"{NOTION_BASE_URL}/pages/{user_page_id}"
    response = requests.get(url, headers=NOTION_HEADERS)
    
    if response.status_code == 200:
        return response.json()
    else:
        print(f"✗ Error getting Notion user: {response.status_code}")
        print(f"  Response: {response.text}")
        return None


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


def extract_user_properties(notion_user: Dict) -> Dict:
    """
    Extract user properties from Notion page
    Returns a dictionary with HubSpot-ready fields (names normalized)
    """
    properties = notion_user.get("properties", {})
    
    # Extract mandatory fields
    email = ""
    first_name = ""
    last_name = ""
    
    # Email
    email_prop = properties.get("✅ Email", {})
    if email_prop.get("email"):
        email = email_prop["email"]
    
    # First Name
    first_name_prop = properties.get("✅ First Name", {})
    if first_name_prop.get("rich_text") and len(first_name_prop["rich_text"]) > 0:
        first_name = first_name_prop["rich_text"][0].get("text", {}).get("content", "")
    
    # Last Name
    last_name_prop = properties.get("✅ Last Name", {})
    if last_name_prop.get("rich_text") and len(last_name_prop["rich_text"]) > 0:
        last_name = last_name_prop["rich_text"][0].get("text", {}).get("content", "")
    
    # Normalize names (capitalize first letter)
    first_name = capitalize_name(first_name)
    last_name = capitalize_name(last_name)
    
    # Extract HubSpot Role from rollup
    hubspot_role = ""
    hubspot_role_prop = properties.get("✅ HubSpot Role", {})
    if hubspot_role_prop.get("rollup") and hubspot_role_prop["rollup"].get("rollup_property"):
        role_data = hubspot_role_prop["rollup"]["rollup_property"]
        if role_data and len(role_data) > 0:
            hubspot_role = role_data[0].get("select", {}).get("name", "")
    
    # Extract optional fields
    phone = ""
    phone_prop = properties.get("📝 Phone Number", {})
    if phone_prop.get("phone_number"):
        phone = phone_prop["phone_number"]
    
    # Get HubSpot tracking fields
    hubspot_created = False
    hubspot_created_prop = properties.get("📝 HubSpot Created", {})
    if hubspot_created_prop.get("checkbox"):
        hubspot_created = hubspot_created_prop["checkbox"]
    
    hubspot_user_id = ""
    hubspot_user_id_prop = properties.get("📝 HubSpot User ID", {})
    if hubspot_user_id_prop.get("rich_text") and len(hubspot_user_id_prop["rich_text"]) > 0:
        hubspot_user_id = hubspot_user_id_prop["rich_text"][0].get("text", {}).get("content", "")
    
    return {
        "email": email,
        "first_name": first_name,
        "last_name": last_name,
        "hubspot_role": hubspot_role,
        "phone": phone,
        "hubspot_created": hubspot_created,
        "hubspot_user_id": hubspot_user_id,
        "notion_page_id": notion_user.get("id")
    }


def create_user_in_hubspot(user_data: Dict) -> Optional[str]:
    """
    Create a user in HubSpot
    Returns the HubSpot user ID if successful
    """
    if not HUBSPOT_ACCESS_TOKEN:
        print("✗ Error: HUBSPOT_ACCESS_TOKEN not set in .env file")
        return None
    
    if not user_data.get("email"):
        print("✗ Error: Email is required to create user in HubSpot")
        return None
    
    if not user_data.get("first_name") and not user_data.get("last_name"):
        print("✗ Warning: First Name or Last Name should be provided")
    
    # HubSpot Users API endpoint
    url = f"{HUBSPOT_BASE_URL}/settings/v3/users"
    
    # Prepare payload
    payload = {
        "email": user_data["email"]
    }
    
    if user_data.get("first_name"):
        payload["firstName"] = user_data["first_name"]
    if user_data.get("last_name"):
        payload["lastName"] = user_data["last_name"]
    
    # Role mapping: Map Notion role names to HubSpot role IDs
    # Note: You'll need to get actual HubSpot role IDs from HubSpot API
    # This is a placeholder - you should map your roles to HubSpot role IDs
    if user_data.get("hubspot_role"):
        # HubSpot role mapping (update these with actual role IDs from HubSpot)
        role_mapping = {
            "Super Admin": None,  # Will need actual role ID
            "Admin": None,
            "Sales Hub User": None,
            "Marketing Hub User": None,
            "Service Hub User": None,
            "CRM User": None,
            "CMS Editor": None,
            "Content Author": None
        }
        # payload["roleId"] = role_mapping.get(user_data["hubspot_role"])
        # For now, we'll create the user and assign role later via HubSpot UI or separate API call
    
    response = requests.post(url, headers=HUBSPOT_HEADERS, json=payload)
    
    if response.status_code == 200 or response.status_code == 201:
        hubspot_user = response.json()
        hubspot_user_id = hubspot_user.get("id")
        print(f"✅ Created user in HubSpot: {user_data['email']} (ID: {hubspot_user_id})")
        return str(hubspot_user_id)
    elif response.status_code == 409:
        # User already exists
        error_data = response.json()
        message = error_data.get("message", "")
        print(f"⚠ User already exists in HubSpot: {user_data['email']}")
        print(f"  Message: {message}")
        # Try to get existing user ID
        return get_hubspot_user_id_by_email(user_data["email"])
    else:
        print(f"✗ Error creating user in HubSpot: {response.status_code}")
        print(f"  Response: {response.text}")
        return None


def get_hubspot_user_id_by_email(email: str) -> Optional[str]:
    """Get HubSpot user ID by email"""
    if not HUBSPOT_ACCESS_TOKEN:
        return None
    
    url = f"{HUBSPOT_BASE_URL}/settings/v3/users"
    params = {"email": email}
    
    response = requests.get(url, headers=HUBSPOT_HEADERS, params=params)
    
    if response.status_code == 200:
        users = response.json().get("results", [])
        if users and len(users) > 0:
            return str(users[0].get("id"))
    
    return None


def update_user_in_hubspot(user_data: Dict, hubspot_user_id: str) -> bool:
    """
    Update an existing user in HubSpot
    Returns True if successful
    """
    if not HUBSPOT_ACCESS_TOKEN:
        print("✗ Error: HUBSPOT_ACCESS_TOKEN not set in .env file")
        return False
    
    url = f"{HUBSPOT_BASE_URL}/settings/v3/users/{hubspot_user_id}"
    
    payload = {}
    if user_data.get("first_name"):
        payload["firstName"] = user_data["first_name"]
    if user_data.get("last_name"):
        payload["lastName"] = user_data["last_name"]
    if user_data.get("email"):
        payload["email"] = user_data["email"]
    
    if not payload:
        print("  ℹ️  No fields to update")
        return True
    
    response = requests.patch(url, headers=HUBSPOT_HEADERS, json=payload)
    
    if response.status_code == 200:
        print(f"✅ Updated user in HubSpot: {user_data.get('email', hubspot_user_id)}")
        return True
    else:
        print(f"✗ Error updating user in HubSpot: {response.status_code}")
        print(f"  Response: {response.text}")
        return False


def update_notion_sync_status(
    notion_page_id: str,
    hubspot_user_id: str,
    created: bool = False
):
    """
    Update Notion page with HubSpot sync status
    """
    if not NOTION_TOKEN:
        return
    
    url = f"{NOTION_BASE_URL}/pages/{notion_page_id}"
    
    now = datetime.now().isoformat()
    
    payload = {
        "properties": {
            "📝 HubSpot Created": {
                "checkbox": True
            },
            "📝 HubSpot User ID": {
                "rich_text": [
                    {
                        "text": {
                            "content": str(hubspot_user_id)
                        }
                    }
                ]
            },
            "📝 HubSpot Last Updated": {
                "date": {
                    "start": now
                }
            }
        }
    }
    
    if created:
        payload["properties"]["📝 HubSpot Created Date"] = {
            "date": {
                "start": now
            }
        }
    
    response = requests.patch(url, headers=NOTION_HEADERS, json=payload)
    
    if response.status_code == 200:
        print(f"  ✅ Updated Notion sync status")
    else:
        print(f"  ⚠ Warning: Could not update Notion sync status: {response.status_code}")


def sync_user_to_hubspot(notion_user_page_id: str) -> bool:
    """
    Main function to sync a single user from Notion to HubSpot
    Returns True if successful
    """
    print(f"\n🔄 Syncing user {notion_user_page_id[:8]}... to HubSpot")
    
    # Step 1: Get user from Notion
    notion_user = get_notion_user(notion_user_page_id)
    if not notion_user:
        return False
    
    # Step 2: Extract properties
    user_data = extract_user_properties(notion_user)
    
    # Validate required fields
    if not user_data.get("email"):
        print("✗ Error: User must have an email address")
        return False
    
    if not user_data.get("first_name") and not user_data.get("last_name"):
        print("✗ Error: User must have at least First Name or Last Name")
        return False
    
    # Step 3: Check if user already exists in HubSpot
    hubspot_user_id = user_data.get("hubspot_user_id")
    hubspot_created = user_data.get("hubspot_created", False)
    
    if hubspot_created and hubspot_user_id:
        # User already synced - update instead
        print(f"  ℹ️  User already exists in HubSpot (ID: {hubspot_user_id}), updating...")
        success = update_user_in_hubspot(user_data, hubspot_user_id)
        if success:
            update_notion_sync_status(notion_user_page_id, hubspot_user_id, created=False)
        return success
    else:
        # New user - create in HubSpot
        print(f"  ✨ Creating new user in HubSpot...")
        hubspot_user_id = create_user_in_hubspot(user_data)
        
        if hubspot_user_id:
            update_notion_sync_status(notion_user_page_id, hubspot_user_id, created=True)
            return True
        else:
            return False


def sync_all_users_from_notion(users_database_id: str) -> Dict:
    """
    Sync all users from Notion Users database to HubSpot
    Useful for initial sync or manual sync
    """
    if not NOTION_TOKEN:
        print("✗ Error: NOTION_TOKEN not set")
        return {"success": 0, "failed": 0}
    
    print("\n" + "=" * 60)
    print("Syncing all users from Notion to HubSpot")
    print("=" * 60)
    
    url = f"{NOTION_BASE_URL}/databases/{users_database_id}/query"
    
    all_users = []
    start_cursor = None
    
    # Get all users (paginated)
    while True:
        payload = {}
        if start_cursor:
            payload["start_cursor"] = start_cursor
        
        response = requests.post(url, headers=NOTION_HEADERS, json=payload)
        
        if response.status_code != 200:
            print(f"✗ Error querying database: {response.status_code}")
            print(f"  Response: {response.text}")
            break
        
        data = response.json()
        results = data.get("results", [])
        all_users.extend(results)
        
        if data.get("has_more"):
            start_cursor = data.get("next_cursor")
        else:
            break
    
    print(f"\n📊 Found {len(all_users)} user(s) in Notion")
    
    success_count = 0
    failed_count = 0
    
    for user in all_users:
        user_id = user.get("id")
        if sync_user_to_hubspot(user_id):
            success_count += 1
        else:
            failed_count += 1
    
    print("\n" + "=" * 60)
    print(f"Sync Complete: {success_count} succeeded, {failed_count} failed")
    print("=" * 60)
    
    return {"success": success_count, "failed": failed_count}


def main():
    """Main function - can be used for manual sync or testing"""
    print("=" * 60)
    print("Notion to HubSpot User Sync")
    print("=" * 60)
    print()
    
    # Check tokens
    if not NOTION_TOKEN:
        print("✗ ERROR: NOTION_TOKEN not set in .env file")
        return
    
    if not HUBSPOT_ACCESS_TOKEN:
        print("✗ ERROR: HUBSPOT_ACCESS_TOKEN not set in .env file")
        print("  Add this to your .env file:")
        print("  HUBSPOT_ACCESS_TOKEN=your_hubspot_token_here")
        return
    
    # Get Users database ID from environment or prompt
    users_db_id = os.getenv("NOTION_USERS_DATABASE_ID", None)
    
    if not users_db_id:
        print("ℹ To sync all users, set NOTION_USERS_DATABASE_ID in .env file")
        print("  Or call sync_user_to_hubspot(notion_user_page_id) for a specific user")
        return
    
    # Sync all users
    sync_all_users_from_notion(users_db_id)


if __name__ == "__main__":
    main()

