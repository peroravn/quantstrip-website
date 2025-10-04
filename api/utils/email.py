"""
Shared email utilities for Quantstrip API
Provides email sending functions with Gmail SMTP
"""

import smtplib
import os
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

# Gmail SMTP configuration
SMTP_HOST = os.environ.get('SMTP_HOST', 'smtp.gmail.com')
SMTP_PORT = int(os.environ.get('SMTP_PORT', 587))
SMTP_USER = os.environ.get('SMTP_USER', 'quantstrip@gmail.com')
SMTP_PASSWORD = os.environ.get('SMTP_PASSWORD', 'svvpsmnmfcwccrsy')
FROM_EMAIL = SMTP_USER

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