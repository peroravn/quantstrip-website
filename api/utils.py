"""
Quantstrip API Utilities
Consolidated utilities for database, email, authentication, and password management
"""

import hashlib
import smtplib
import os
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime
from supabase import create_client, Client

# =============================================================================
# CONFIGURATION
# =============================================================================

# Supabase configuration
SUPABASE_URL = os.environ.get('SUPABASE_URL', 'https://ozamqnegrjquvwfzxocf.supabase.co')
SUPABASE_KEY = os.environ.get('SUPABASE_KEY', 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Im96YW1xbmVncmpxdXZ3Znp4b2NmIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc1Nzk0NzQ5OCwiZXhwIjoyMDczNTIzNDk4fQ.pxyJuiPZ9NZdspKVOlgSlLk1_Dgm5QNTuypSMy4gI_o')

# Email configuration
SMTP_HOST = os.environ.get('SMTP_HOST', 'smtp.gmail.com')
SMTP_PORT = int(os.environ.get('SMTP_PORT', 587))
SMTP_USER = os.environ.get('SMTP_USER', 'quantstrip@gmail.com')
SMTP_PASSWORD = os.environ.get('SMTP_PASSWORD', 'svvpsmnmfcwccrsy')
FROM_EMAIL = SMTP_USER

# Password hashing configuration
PASSWORD_SALT = os.environ.get('PASSWORD_SALT', 'quantstrip_salt_2024')

# Singleton instance for Supabase client
_supabase_client: Client = None


# =============================================================================
# DATABASE UTILITIES
# =============================================================================

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


# =============================================================================
# EMAIL UTILITIES
# =============================================================================

def send_email(to_email: str, subject: str, text_content: str, html_content: str):
    """
    Send an email via Gmail SMTP
    
    Args:
        to_email: Recipient email address
        subject: Email subject
        text_content: Plain text version of email
        html_content: HTML version of email
        
    Returns:
        tuple: (success: bool, message: str)
    """
    try:
        print(f"Sending email to {to_email}: {subject}")
        
        # Create message
        msg = MIMEMultipart('alternative')
        msg['Subject'] = subject
        msg['From'] = FROM_EMAIL
        msg['To'] = to_email
        
        # Attach both versions
        msg.attach(MIMEText(text_content, 'plain'))
        msg.attach(MIMEText(html_content, 'html'))
        
        # Send via SMTP
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=10) as server:
            server.starttls()
            server.login(SMTP_USER, SMTP_PASSWORD)
            server.send_message(msg)
        
        print(f"Email sent successfully to {to_email}")
        return True, "Email sent successfully"
        
    except smtplib.SMTPAuthenticationError as e:
        error_msg = f"Authentication failed: {str(e)}"
        print(error_msg)
        return False, error_msg
    except smtplib.SMTPException as e:
        error_msg = f"SMTP error: {str(e)}"
        print(error_msg)
        return False, error_msg
    except Exception as e:
        error_msg = f"Unexpected error: {type(e).__name__} - {str(e)}"
        print(error_msg)
        return False, error_msg


def send_activation_email(to_email: str, first_name: str, last_name: str, activation_token: str):
    """
    Send account activation email
    
    Args:
        to_email: Recipient email
        first_name: User's first name
        last_name: User's last name
        activation_token: Activation token UUID
        
    Returns:
        tuple: (success: bool, message: str)
    """
    activation_link = f"https://quantstrip.com/api/activate?token={activation_token}"
    
    text_content = f"""
    Hello {first_name},
    
    Thank you for registering at Quantstrip!
    
    Please activate your account by clicking the following link:
    {activation_link}
    
    If you didn't register for this account, please ignore this email.
    
    Best regards,
    The Quantstrip Team
    """
    
    html_content = f"""
    <html>
    <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
        <h2>Hello {first_name},</h2>
        <p>Thank you for registering at Quantstrip!</p>
        <p>Please activate your account by clicking the button below:</p>
        <p style="margin: 30px 0;">
            <a href="{activation_link}" 
               style="background-color: #4CAF50; 
                      color: white; 
                      padding: 12px 24px; 
                      text-decoration: none; 
                      border-radius: 4px;
                      display: inline-block;">
                Activate my account
            </a>
        </p>
        <p style="color: #666; font-size: 14px;">
            Or copy and paste this link into your browser:<br>
            <a href="{activation_link}">{activation_link}</a>
        </p>
        <p style="color: #666; font-size: 12px; margin-top: 30px;">
            If you didn't register for this account, please ignore this email.
        </p>
        <p>Best regards,<br>The Quantstrip Team</p>
    </body>
    </html>
    """
    
    return send_email(to_email, 'Activate Your Quantstrip Account', text_content, html_content)


def send_license_email(to_email: str, first_name: str, product_name: str, 
                       license_key: str, expires_at_formatted: str):
    """
    Send license key email after purchase
    
    Args:
        to_email: Recipient email
        first_name: User's first name
        product_name: Name of purchased product
        license_key: Generated license key
        expires_at_formatted: Formatted expiration date (e.g., "December 31, 2025")
        
    Returns:
        tuple: (success: bool, message: str)
    """
    text_content = f"""
    Hello {first_name},
    
    Thank you for your purchase!
    
    Your {product_name} license has been generated successfully.
    
    LICENSE KEY: {license_key}
    
    License Details:
    - Product: {product_name}
    - Valid Until: {expires_at_formatted}
    
    To activate your software:
    1. Copy the license key above
    2. Open your Quantstrip software
    3. Enter the license key when prompted
    
    If you have any questions, please don't hesitate to contact our support team.
    
    Best regards,
    The Quantstrip Team
    """
    
    html_content = f"""
    <html>
    <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
        <div style="max-width: 600px; margin: 0 auto; padding: 20px;">
            <h2 style="color: #4CAF50;">Thank You for Your Purchase!</h2>
            <p>Hello {first_name},</p>
            <p>Your <strong>{product_name}</strong> license has been generated successfully.</p>
            
            <div style="background-color: #f5f5f5; padding: 20px; border-radius: 8px; margin: 20px 0;">
                <h3 style="margin-top: 0; color: #333;">Your License Key</h3>
                <div style="background-color: white; padding: 15px; border: 2px solid #4CAF50; border-radius: 4px; font-family: monospace; font-size: 18px; text-align: center; letter-spacing: 1px;">
                    {license_key}
                </div>
            </div>
            
            <div style="background-color: #e8f5e9; padding: 15px; border-radius: 4px; margin: 20px 0;">
                <h4 style="margin-top: 0; color: #2e7d32;">License Details</h4>
                <p style="margin: 5px 0;"><strong>Product:</strong> {product_name}</p>
                <p style="margin: 5px 0;"><strong>Valid Until:</strong> {expires_at_formatted}</p>
            </div>
            
            <h3>How to Activate</h3>
            <ol>
                <li>Copy the license key above</li>
                <li>Open your Quantstrip software</li>
                <li>Enter the license key when prompted</li>
            </ol>
            
            <p style="margin-top: 30px; color: #666; font-size: 14px;">
                If you have any questions, please contact our support team.
            </p>
            
            <p style="margin-top: 20px;">Best regards,<br><strong>The Quantstrip Team</strong></p>
        </div>
    </body>
    </html>
    """
    
    return send_email(to_email, f'Your {product_name} License Key - Quantstrip', 
                     text_content, html_content)


# =============================================================================
# PASSWORD UTILITIES
# =============================================================================

def hash_password(password: str) -> str:
    """
    Hash a password using SHA-256 with salt
    
    Args:
        password: Plain text password
        
    Returns:
        str: Hashed password (hex digest)
        
    Note:
        For production, consider upgrading to bcrypt or argon2 for better security
    """
    salted_password = password + PASSWORD_SALT
    return hashlib.sha256(salted_password.encode()).hexdigest()


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Verify a password against its hash
    
    Args:
        plain_password: Plain text password to verify
        hashed_password: Stored hashed password
        
    Returns:
        bool: True if password matches, False otherwise
    """
    return hash_password(plain_password) == hashed_password


# =============================================================================
# AUTHENTICATION & VALIDATION UTILITIES
# =============================================================================

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