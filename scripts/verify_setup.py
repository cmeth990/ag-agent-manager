#!/usr/bin/env python3
"""Verify that the setup is correct before deployment."""
import os
import sys
from dotenv import load_dotenv

load_dotenv()

def check_env_var(name: str, required: bool = True) -> bool:
    """Check if an environment variable is set."""
    value = os.getenv(name)
    if required and not value:
        print(f"❌ {name} is not set (required)")
        return False
    elif value:
        if name == "TELEGRAM_BOT_TOKEN":
            # Mask token for security
            masked = value[:10] + "..." + value[-4:] if len(value) > 14 else "***"
            print(f"✅ {name} is set: {masked}")
        else:
            print(f"✅ {name} is set")
        return True
    else:
        print(f"⚠️  {name} is not set (optional)")
        return True


def main():
    """Run setup verification."""
    print("🔍 Verifying setup...\n")
    
    errors = []
    
    # Required variables
    if not check_env_var("TELEGRAM_BOT_TOKEN", required=True):
        errors.append("TELEGRAM_BOT_TOKEN")
    
    if not check_env_var("DATABASE_URL", required=True):
        errors.append("DATABASE_URL")
    
    # Optional variables
    check_env_var("OPENAI_API_KEY", required=False)
    check_env_var("ANTHROPIC_API_KEY", required=False)
    check_env_var("PORT", required=False)
    
    print()
    
    if errors:
        print(f"❌ Setup incomplete. Missing required variables: {', '.join(errors)}")
        print("\nPlease set these in your .env file or environment.")
        sys.exit(1)
    else:
        print("✅ All required environment variables are set!")
        print("\nNext steps:")
        print("1. Ensure Postgres database is accessible")
        print("2. Run: uvicorn app.main:app --reload --port 8000")
        print("3. Set webhook: python scripts/set_webhook.py set <url>")


if __name__ == "__main__":
    main()
