"""
Shared database utilities for Quantstrip API
Provides singleton Supabase client instance
"""

from supabase import create_client, Client
import os

# Supabase configuration
SUPABASE_URL = os.environ.get('SUPABASE_URL', 'https://ozamqnegrjquvwfzxocf.supabase.co')
SUPABASE_KEY = os.environ.get('SUPABASE_KEY', 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Im96YW1xbmVncmpxdXZ3Znp4b2NmIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc1Nzk0NzQ5OCwiZXhwIjoyMDczNTIzNDk4fQ.pxyJuiPZ9NZdspKVOlgSlLk1_Dgm5QNTuypSMy4gI_o')

# Singleton instance
_supabase_client: Client = None

def get_supabase_client() -> Client:
    """
    Get or create Supabase client singleton
    
    Returns:
        Client: Supabase client instance
    """
    global _supabase_client
    
    if _supabase_client is None:
        _supabase_client = create_client(SUPABASE_URL, SUPABASE_KEY)
    
    return _supabase_client

def get_user_by_email(email: str):
    """
    Fetch user by email address
    
    Args:
        email: User's email address
        
    Returns:
        dict: User data or None if not found
    """
    client = get_supabase_client()
    result = client.table('users')\
        .select('*')\
        .eq('email', email)\
        .execute()
    
    return result.data[0] if result.data and len(result.data) > 0 else None

def get_user_licenses(user_id: int, active_only: bool = False):
    """
    Fetch user's licenses with product information
    
    Args:
        user_id: User ID
        active_only: If True, only return active licenses
        
    Returns:
        list: List of license records with product info
    """
    client = get_supabase_client()
    query = client.table('licenses')\
        .select('*, products(name, description)')\
        .eq('user_id', user_id)
    
    if active_only:
        query = query.eq('status', 'active')
    
    result = query.order('created_at', desc=True).execute()
    return result.data if result.data else []

def create_user(first_name: str, last_name: str, email: str, 
                password_hash: str, activation_token: str):
    """
    Create a new user
    
    Args:
        first_name: User's first name
        last_name: User's last name
        email: User's email address
        password_hash: Hashed password
        activation_token: Account activation token
        
    Returns:
        dict: Created user record
        
    Raises:
        Exception: If user creation fails
    """
    client = get_supabase_client()
    result = client.table('users').insert({
        'first_name': first_name,
        'last_name': last_name,
        'email': email,
        'password_hash': password_hash,
        'activation_token': activation_token,
        'status': 'pending_activation'
    }).execute()
    
    if not result.data:
        raise Exception('Failed to create user')
    
    return result.data[0]

def update_user_status(activation_token: str, status: str):
    """
    Update user status and clear activation token
    
    Args:
        activation_token: User's activation token
        status: New status (e.g., 'active')
        
    Returns:
        dict: Updated user record or None
    """
    client = get_supabase_client()
    result = client.table('users')\
        .update({
            'status': status,
            'activation_token': None
        })\
        .eq('activation_token', activation_token)\
        .execute()
    
    return result.data[0] if result.data and len(result.data) > 0 else None

def create_license(user_id: int, product_id: int, license_key: str, 
                   expires_at: str, coupon_code: str = None):
    """
    Create a new license
    
    Args:
        user_id: User ID
        product_id: Product ID
        license_key: Generated license key
        expires_at: License expiration datetime (ISO format)
        coupon_code: Optional coupon code used
        
    Returns:
        dict: Created license record
    """
    client = get_supabase_client()
    result = client.table('licenses').insert({
        'user_id': user_id,
        'product_id': product_id,
        'license_key': license_key,
        'expires_at': expires_at,
        'status': 'active',
        'coupon_used': coupon_code
    }).execute()
    
    return result.data[0] if result.data and len(result.data) > 0 else None

def increment_coupon_usage(coupon_code: str):
    """
    Increment coupon usage counter
    
    Args:
        coupon_code: Coupon code to increment
        
    Returns:
        bool: True if successful
    """
    try:
        client = get_supabase_client()
        
        # Get current coupon
        coupon_result = client.table('coupons')\
            .select('*')\
            .eq('code', coupon_code.upper())\
            .execute()
        
        if coupon_result.data and len(coupon_result.data) > 0:
            coupon = coupon_result.data[0]
            
            # Increment usage
            client.table('coupons')\
                .update({'times_used': coupon['times_used'] + 1})\
                .eq('id', coupon['id'])\
                .execute()
            
            return True
    except Exception as e:
        print(f"Error incrementing coupon usage: {str(e)}")
    
    return False