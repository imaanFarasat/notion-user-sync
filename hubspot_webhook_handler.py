"""
HubSpot Webhook Handler
Handles webhook events from HubSpot to normalize contact/user names (capitalize first letters)

Primary use: Contact webhooks - when first name or last name is added/updated on a Contact
Supports:
- HubSpot Contacts (CRM) - PRIMARY TARGET - contact.created, contact.propertyChange
- HubSpot Users (Settings API) - internal team members (secondary support)
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


def get_hubspot_user(user_id: str, is_contact: bool = False) -> Optional[Dict]:
    """
    Get a user/contact from HubSpot by ID
    
    Args:
        user_id: HubSpot user or contact ID
        is_contact: If True, directly use Contacts API; if False, try Users API first
    """
    if not HUBSPOT_ACCESS_TOKEN:
        print("  ✗ Error: HUBSPOT_ACCESS_TOKEN not set")
        return None
    
    # If we know it's a contact, go directly to Contacts API
    if is_contact:
        print(f"  📞 Fetching Contact {user_id} from Contacts API...")
        contact_url = f"{HUBSPOT_BASE_URL}/crm/v3/objects/contacts/{user_id}"
        contact_response = requests.get(contact_url, headers=HUBSPOT_HEADERS)
        if contact_response.status_code == 200:
            contact_data = contact_response.json()
            # Convert contact format to user-like format
            props = contact_data.get("properties", {})
            return {
                "id": contact_data.get("id"),
                "firstName": props.get("firstname", ""),
                "lastName": props.get("lastname", ""),
                "firstname": props.get("firstname", ""),  # Keep lowercase too
                "lastname": props.get("lastname", ""),      # Keep lowercase too
                "email": props.get("email", "")
            }
        else:
            print(f"  ✗ Error getting Contact: {contact_response.status_code}")
            print(f"    Response: {contact_response.text}")
            return None
    
    # Try Users API first (Settings API)
    url = f"{HUBSPOT_BASE_URL}/settings/v3/users/{user_id}"
    response = requests.get(url, headers=HUBSPOT_HEADERS)
    
    if response.status_code == 200:
        return response.json()
    elif response.status_code == 404:
        # If not found as User, might be a Contact - try Contacts API
        print(f"  ⚠️  User {user_id} not found in Users API, trying Contacts API...")
        contact_url = f"{HUBSPOT_BASE_URL}/crm/v3/objects/contacts/{user_id}"
        contact_response = requests.get(contact_url, headers=HUBSPOT_HEADERS)
        if contact_response.status_code == 200:
            contact_data = contact_response.json()
            # Convert contact format to user-like format
            props = contact_data.get("properties", {})
            return {
                "id": contact_data.get("id"),
                "firstName": props.get("firstname", ""),
                "lastName": props.get("lastname", ""),
                "firstname": props.get("firstname", ""),
                "lastname": props.get("lastname", ""),
                "email": props.get("email", "")
            }
    
    print(f"  ✗ Error getting HubSpot user: {response.status_code}")
    print(f"    Response: {response.text}")
    return None


def update_hubspot_user_name(user_id: str, first_name: str, last_name: str, is_contact: bool = False) -> bool:
    """
    Update a user's first and last name in HubSpot
    Tries Users API first, falls back to Contacts API if needed
    
    Args:
        user_id: HubSpot user ID or Contact ID
        first_name: New first name
        last_name: New last name
    
    Returns:
        True if successful, False otherwise
    """
    if not HUBSPOT_ACCESS_TOKEN:
        print("  ✗ Error: HUBSPOT_ACCESS_TOKEN not set")
        return False
    
    # If we know it's a contact, use Contacts API directly
    if is_contact:
        contact_url = f"{HUBSPOT_BASE_URL}/crm/v3/objects/contacts/{user_id}"
        contact_payload = {
            "properties": {}
        }
        if first_name:
            contact_payload["properties"]["firstname"] = first_name
        if last_name:
            contact_payload["properties"]["lastname"] = last_name
        
        if not contact_payload["properties"]:
            print("  ℹ️  No names to update")
            return True
        
        response = requests.patch(contact_url, headers=HUBSPOT_HEADERS, json=contact_payload)
    else:
        # Try Users API first (Settings API)
        url = f"{HUBSPOT_BASE_URL}/settings/v3/users/{user_id}"
        
        payload = {}
        if first_name:
            payload["firstName"] = first_name
        if last_name:
            payload["lastName"] = last_name
        
        if not payload:
            print("  ℹ️  No names to update")
            return True
        
        # Try PATCH first, then PUT if needed
        response = requests.patch(url, headers=HUBSPOT_HEADERS, json=payload)
        
        if response.status_code == 405:
            # Try PUT method
            response = requests.put(url, headers=HUBSPOT_HEADERS, json=payload)
        
        if response.status_code == 404:
            # Not a User, try as Contact
            print(f"  ⚠️  User {user_id} not found, trying as Contact...")
            contact_url = f"{HUBSPOT_BASE_URL}/crm/v3/objects/contacts/{user_id}"
            contact_payload = {
                "properties": {}
            }
            if first_name:
                contact_payload["properties"]["firstname"] = first_name
            if last_name:
                contact_payload["properties"]["lastname"] = last_name
            
            response = requests.patch(contact_url, headers=HUBSPOT_HEADERS, json=contact_payload)
    
    if response.status_code == 200:
        print(f"  ✅ Updated name: {first_name} {last_name}")
        return True
    else:
        print(f"  ✗ Error updating: {response.status_code}")
        print(f"    Response: {response.text}")
        return False


def validate_expanded_object_payload(event: Dict) -> bool:
    """
    Validate that the webhook payload matches expanded object support format
    
    Expected format:
    {
        "subscriptionId": "...",
        "portalId": 12345,
        "occurredAt": timestamp,
        "objectId": "123",
        "objectType": "USER" or similar,
        "eventType": "object.creation" | "object.propertyChange" | "object.deletion",
        "propertyName": "firstName" (for propertyChange),
        "propertyValue": "john" (for propertyChange),
        "properties": {...} (optional)
    }
    
    Returns True if payload structure looks valid
    """
    # Check for expanded object format markers
    has_subscription_id = "subscriptionId" in event
    has_object_id = "objectId" in event
    has_event_type = "eventType" in event
    
    # At minimum, we need objectId to process
    if not has_object_id:
        return False
    
    # Expanded format should have subscriptionId and eventType
    if has_subscription_id and has_event_type:
        event_type = event.get("eventType", "").lower()
        # Should start with "object." for expanded format
        if event_type.startswith("object."):
            return True
    
    return True  # Don't reject if format is slightly different, be flexible


def handle_hubspot_user_webhook(event) -> Dict:
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
    
    # HubSpot can send either a single event (dict) or an array of events
    # Handle array case first
    if isinstance(event, list):
        print(f"   📦 Received array of {len(event)} event(s), processing each...")
        results = []
        for idx, single_event in enumerate(event):
            print(f"\n   🔄 Processing event {idx + 1}/{len(event)}...")
            if isinstance(single_event, dict):
                result = handle_single_hubspot_event(single_event)
                results.append(result)
            else:
                print(f"   ⚠️  Event {idx + 1} is not a dictionary, skipping")
        
        # Return summary
        success_count = sum(1 for r in results if r.get("status") == "success")
        ignored_count = sum(1 for r in results if r.get("status") == "ignored")
        error_count = sum(1 for r in results if r.get("status") == "error")
        
        return {
            "status": "success" if success_count > 0 else ("ignored" if error_count == 0 else "error"),
            "message": f"Processed {len(event)} event(s): {success_count} succeeded, {ignored_count} ignored, {error_count} errors",
            "results": results
        }
    
    # Validate payload structure for single event
    if not isinstance(event, dict):
        print(f"   ❌ Invalid payload: not a dictionary or array")
        return {
            "status": "error",
            "message": "Invalid webhook payload format"
        }
    
    # Process single event
    return handle_single_hubspot_event(event)


def handle_single_hubspot_event(event: Dict) -> Dict:
    
    # Log full event structure for debugging
    print(f"   📄 Event keys: {list(event.keys())}")
    
    # Validate expanded object format if applicable
    is_expanded_format = validate_expanded_object_payload(event)
    if is_expanded_format and ("subscriptionId" in event or "occurredAt" in event):
        print(f"   ✅ Detected expanded object support format")
    
    # HubSpot webhook structure varies, check common formats
    # Expanded object support uses standardized format with object.* event types
    event_type = (
        event.get("eventType") or 
        event.get("subscriptionType") or 
        event.get("type") or
        event.get("event") or
        event.get("event_id")
    )
    print(f"   📋 Event type: {event_type}")
    
    # Extract user information from different webhook formats
    # PRIORITY: Check expanded object support format FIRST (most common with enabled feature)
    user_id = None
    user_data = None
    
    # Format 0: Expanded object format with propertyChange - CHECK THIS FIRST
    # HubSpot expanded object format sends: subscriptionType, objectId, propertyName, propertyValue
    subscription_type = event.get("subscriptionType", "").lower()
    if subscription_type == "object.propertychange" and "objectId" in event:
        object_id = str(event.get("objectId"))
        property_name = event.get("propertyName", "").lower()
        
        # Only process firstname/lastname property changes
        if property_name in ["firstname", "lastname", "first name", "last name"]:
            user_id = object_id
            property_value = event.get("propertyValue", "")
            # Store the property name and value
            user_data = {
                "propertyName": property_name,
                "propertyValue": property_value,
                "objectTypeId": event.get("objectTypeId", ""),  # "0-1" = Contact
                "subscriptionType": subscription_type
            }
            print(f"   📦 Found expanded object propertyChange: {user_id} ({property_name}={property_value})")
    
    # Format 1: Contact-specific webhook format (contact.created, contact.updated, etc.)
    elif event.get("eventType", "").lower().startswith("contact.") or "contactId" in event:
        contact_id = event.get("contactId") or event.get("objectId")
        if contact_id:
            user_id = str(contact_id)
            # Contact properties use lowercase: firstname, lastname
            user_data = event.get("properties", {})
            if not user_data:
                user_data = {}
                for key in ["firstname", "lastname", "email"]:
                    if key in event:
                        user_data[key] = event[key]
            print(f"   📦 Found Contact webhook format: {user_id}")
    
    # Format 1: Expanded object support format (generic object model)
    # Expanded format has: subscriptionId, occurredAt, objectId, eventType (object.creation, object.propertyChange, etc.)
    elif "occurredAt" in event or "subscriptionId" in event:
        # Expanded object format structure
        if "objectId" in event:
            object_id = str(event.get("objectId"))
            object_type = event.get("objectType", "").upper()
            expanded_event_type = event.get("eventType", "").lower()
            
            # Check if it's a user-related object or contact
            # Support: object.creation, object.propertyChange, object.deletion
            # Also support contacts: contact.created, contact.propertyChange, etc.
            is_user_event = (
                "USER" in object_type or 
                "CONTACT" in object_type or
                expanded_event_type.startswith("object.") or
                expanded_event_type.startswith("contact.") or
                expanded_event_type in ["user.created", "user.updated", "user.propertychange", "user.deleted",
                                       "contact.created", "contact.updated", "contact.propertychange"]
            )
            
            if is_user_event:
                user_id = object_id
                # For propertyChange events, properties are in propertyName/propertyValue
                # For creation/update, properties might be in a separate object
                user_data = {}
                
                # Handle property change events
                if "propertyChange" in expanded_event_type or "propertychange" in expanded_event_type:
                    property_name = event.get("propertyName", "")
                    property_value = event.get("propertyValue", "")
                    if property_name:
                        user_data[property_name] = property_value
                
                # Also check for properties object
                if event.get("properties"):
                    user_data.update(event.get("properties", {}))
                
                print(f"   📦 Found expanded object format: {user_id} (type: {object_type}, event: {expanded_event_type})")
    
    # Format 2: Standard HubSpot subscription webhook (subscriptionId, portalId, eventType, objectId)
    if not user_id and "objectId" in event:
        user_id = str(event.get("objectId"))
        # Properties might be in event or need to fetch from API
        user_data = event.get("properties", {})
        print(f"   📦 Found standard objectId format: {user_id}")
    
    # Format 3: user.create or user.propertyChange (userId directly)
    elif not user_id and "userId" in event:
        user_id = str(event.get("userId"))
        user_data = event.get("properties", {})
        print(f"   📦 Found userId format: {user_id}")
    
    # Format 4: Full user object in response
    elif not user_id and "id" in event:
        # Check if this looks like a user object
        if event.get("type") == "USER" or "email" in event or "firstName" in event:
            user_id = str(event.get("id"))
            user_data = event
            print(f"   📦 Found user object format: {user_id}")
    
    # Format 5: HubSpot contact/object webhook with associations
    elif not user_id and "objectType" in event:
        object_type_val = event.get("objectType", "").upper()
        if object_type_val in ["USER", "USER_DEFINED", "CONTACT"]:
            user_id = str(event.get("objectId", ""))
            user_data = event.get("properties", {})
            print(f"   📦 Found objectType format: {user_id} (type: {object_type_val})")
    
    # Format 6: Nested object structure (expanded format variant)
    if not user_id and "object" in event:
        obj = event.get("object", {})
        if isinstance(obj, dict):
            obj_id = obj.get("id") or obj.get("objectId")
            obj_type = obj.get("type") or obj.get("objectType", "")
            # Support both Users and Contacts
            if obj_id and ("USER" in str(obj_type).upper() or "CONTACT" in str(obj_type).upper() or "firstName" in obj or "firstname" in obj or "email" in obj):
                user_id = str(obj_id)
                user_data = obj.get("properties", {}) or obj
                print(f"   📦 Found nested object format: {user_id} (type: {obj_type})")
    
    
    # If we found a propertyChange event, check if we should process it
    # Only process firstname/lastname changes - other properties are ignored
    if user_id and user_data and user_data.get("subscriptionType") == "object.propertychange":
        property_name = user_data.get("propertyName", "").lower()
        if property_name not in ["firstname", "lastname", "first name", "last name"]:
            print(f"   ⏭️  Property '{property_name}' is not firstname/lastname, ignoring")
            return {
                "status": "ignored",
                "message": f"Property '{property_name}' does not require name normalization"
            }
    
    if not user_id:
        print(f"   ⏭️  No user ID found in webhook event (may not be a name-related event)")
        print(f"   📄 Event keys: {list(event.keys())}")
        return {
            "status": "ignored",
            "message": "No user ID found in webhook event"
        }
    
    print(f"   🆔 Contact/User ID: {user_id}")
    
    # Check objectTypeId to determine if it's a Contact
    # "0-1" = Contact, need to use Contacts API
    object_type_id = user_data.get("objectTypeId", "") if user_data else event.get("objectTypeId", "")
    is_contact = (object_type_id == "0-1" or 
                  event.get("objectTypeId", "") == "0-1" or
                  "contact" in str(event.get("objectType", "")).lower())
    
    # Get current user/contact data from HubSpot API (more reliable than webhook payload)
    user = get_hubspot_user(user_id, is_contact=is_contact)
    if not user:
        print(f"   ❌ Could not retrieve user from HubSpot")
        return {
            "status": "error",
            "message": f"Could not retrieve user {user_id}"
        }
    
    # Extract current names from API response (most reliable)
    # Handle both User format (firstName/lastName) and Contact format (firstname/lastname)
    current_first = user.get("firstName", "") or user.get("firstname", "") or ""
    current_last = user.get("lastName", "") or user.get("lastname", "") or ""
    
    # If names are empty, try from webhook payload
    # Handle both standard format and expanded object format (propertyName/propertyValue)
    if user_data:
        # Standard property format (check both camelCase and lowercase)
        if not current_first:
            current_first = (
                user_data.get("firstName", "") or 
                user_data.get("firstname", "") or
                user_data.get("First Name", "") or
                ""
            )
        if not current_last:
            current_last = (
                user_data.get("lastName", "") or 
                user_data.get("lastname", "") or
                user_data.get("Last Name", "") or
                ""
            )
        
        # Expanded format: propertyName might be "firstName" or "firstname" and propertyValue contains the value
        # Also check if propertyName indicates which field changed
        property_name = (user_data.get("propertyName", "") or "").lower()
        property_value = user_data.get("propertyValue", "")
        
        if property_name in ["firstname", "first name"] and property_value:
            current_first = str(property_value)
        elif property_name in ["lastname", "last name"] and property_value:
            current_last = str(property_value)
    
    # Also check event directly for Contact-specific fields
    if not current_first or not current_last:
        # Check event payload directly for Contact properties
        event_props = event.get("properties", {})
        if isinstance(event_props, dict):
            if not current_first:
                current_first = (
                    event_props.get("firstname", "") or 
                    event_props.get("firstName", "") or
                    event_props.get("First Name", "") or
                    ""
                )
            if not current_last:
                current_last = (
                    event_props.get("lastname", "") or 
                    event_props.get("lastName", "") or
                    event_props.get("Last Name", "") or
                    ""
                )
    
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
    
    # Update user/contact in HubSpot
    print(f"   🔄 Updating names in HubSpot...")
    success = update_hubspot_user_name(user_id, normalized_first, normalized_last, is_contact=is_contact)
    
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

