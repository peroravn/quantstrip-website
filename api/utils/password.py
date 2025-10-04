"""
Password hashing utilities for Quantstrip API
"""

import hashlib
import os

# Salt for password hashing
# In production, consider using environment variable and unique salt per user
PASSWORD_SALT = os.environ.get('PASSWORD_SALT', 'quantstrip_salt_2024')

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