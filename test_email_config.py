#!/usr/bin/env python3
"""
Email Configuration Test Script
Run this to verify your email settings before deployment
"""

import os
from dotenv import load_dotenv
from email_service import EmailService

def test_email_configuration():
    """Test email configuration and send a test email"""
    load_dotenv()
    
    # Check if email is enabled
    if not os.getenv('ENABLE_EMAIL', 'false').lower() == 'true':
        print("❌ ENABLE_EMAIL is not set to true")
        return False
    
    # Check required email settings
    required_settings = [
        'SMTP_HOST', 'SMTP_PORT', 'SMTP_USER', 
        'SMTP_PASS', 'EMAIL_FROM', 'EMAIL_TO'
    ]
    
    missing_settings = []
    for setting in required_settings:
        if not os.getenv(setting):
            missing_settings.append(setting)
    
    if missing_settings:
        print(f"❌ Missing email settings: {', '.join(missing_settings)}")
        return False
    
    print("✅ All email settings present")
    
    # Test email service initialization
    try:
        email_service = EmailService()
        print("✅ Email service initialized successfully")
    except Exception as e:
        print(f"❌ Failed to initialize email service: {e}")
        return False
    
    # Send test email
    try:
        print("\n📧 Sending test email...")
        success = email_service.send_test_email()
        
        if success:
            print("✅ Test email sent successfully!")
            print(f"📬 Check inboxes: {os.getenv('EMAIL_TO')}")
            return True
        else:
            print("❌ Failed to send test email")
            return False
            
    except Exception as e:
        print(f"❌ Error sending test email: {e}")
        return False

if __name__ == "__main__":
    print("🔧 Testing Email Configuration for Barbados Radio Synopsis")
    print("=" * 60)
    
    if test_email_configuration():
        print("\n🎉 Email configuration is working correctly!")
        print("✅ Ready for production deployment")
    else:
        print("\n⚠️  Email configuration needs attention")
        print("❌ Fix issues before deploying to production")
