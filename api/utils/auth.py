"""
Shared authentication and validation utilities for Quantstrip API
"""

from datetime import datetime
from .db import get_supabase_client, get_user_by_email, get_user_licenses

def validate_user_license(email: str, required_product: str = None):
    """
    Validate that user has an active, non-expired license.
    Optionally check for a specific product (e.g., 'Pro').
    
    Args:
        email: User's email address
        required_product: Optional product name to check for (e.g., 'Pro')
        
    Returns:
        tuple: (is_valid: bool, error_message: str or None)
        
    Example:
        is_valid, error = validate_user_license('user@example.com', 'Pro')
        if not is_valid:
            return {'success': False, 'error': error}
    """
    try:
        # Get user
        user = get_user_by_email(email)
        if not user:
            return False, 'User not found'
        
        # Get user's active licenses with product info
        licenses = get_user_licenses(user['id'], active_only=True)
        
        if not licenses:
            return False, 'No active licenses found'
        
        # Check if any license is still valid (not expired)
        has_valid_license = False
        has_required_product = False
        
        for license_data in licenses:
            # Parse expiration date
            expires_at = datetime.fromisoformat(
                license_data['expires_at'].replace('Z', '+00:00')
            )
            is_not_expired = datetime.now(expires_at.tzinfo) < expires_at
            
            if is_not_expired:
                has_valid_license = True
                
                # Check for specific product if required
                if required_product:
                    product_name = (license_data.get('products', {}).get('name') 
                                  if license_data.get('products') else None)
                    if product_name == required_product:
                        has_required_product = True
                        break
                else:
                    # No specific product required, any valid license is fine
                    return True, None
        
        if not has_valid_license:
            return False, 'All licenses have expired'
        
        if required_product and not has_required_product:
            return False, f'{required_product} license required'
        
        return True, None
        
    except Exception as e:
        print(f"Error validating license: {str(e)}")
        return False, f'Validation error: {str(e)}'

def check_email_exists(email: str):
    """
    Check if email already exists in database
    
    Args:
        email: Email address to check
        
    Returns:
        bool: True if email exists, False otherwise
    """
    user = get_user_by_email(email)
    return user is not None

def validate_activation_token(activation_token: str):
    """
    Validate activation token and get user info
    
    Args:
        activation_token: Activation token to validate
        
    Returns:
        dict: User data if valid, None otherwise
    """
    client = get_supabase_client()
    result = client.table('users')\
        .select('*')\
        .eq('activation_token', activation_token)\
        .execute()
    
    return result.data[0] if result.data and len(result.data) > 0 else None

def get_product_by_id(product_id: int):
    """
    Get product information by ID
    
    Args:
        product_id: Product ID
        
    Returns:
        dict: Product data or None
    """
    client = get_supabase_client()
    result = client.table('products')\
        .select('*')\
        .eq('id', product_id)\
        .eq('is_active', True)\
        .execute()
    
    return result.data[0] if result.data and len(result.data) > 0 else None

def validate_coupon(coupon_code: str, product_id: int = None):
    """
    Validate a coupon code
    
    Args:
        coupon_code: Coupon code to validate
        product_id: Optional product ID to check compatibility
        
    Returns:
        tuple: (is_valid: bool, coupon_data: dict or None, error_message: str or None)
    """
    try:
        client = get_supabase_client()
        
        # Look up coupon
        result = client.table('coupons')\
            .select('*')\
            .eq('code', coupon_code.upper())\
            .eq('is_active', True)\
            .execute()
        
        if not result.data or len(result.data) == 0:
            return False, None, 'Invalid coupon code'
        
        coupon = result.data[0]
        
        # Check expiration
        expires_at = datetime.fromisoformat(coupon['expires_at'].replace('Z', '+00:00'))
        if datetime.now(expires_at.tzinfo) > expires_at:
            return False, None, 'This coupon has expired'
        
        # Check usage limits
        if coupon['times_used'] >= coupon['max_uses']:
            return False, None, 'This coupon has reached its usage limit'
        
        # Check product compatibility
        if coupon['product_id'] is not None and coupon['product_id'] != product_id:
            return False, None, 'This coupon is not valid for this product'
        
        return True, coupon, None
        
    except Exception as e:
        print(f"Error validating coupon: {str(e)}")
        return False, None, f'Validation error: {str(e)}'