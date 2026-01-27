#!/usr/bin/env python3
"""
Script to assign roles to a Clerk user via email address.

Usage:
    python scripts/assign_user_role.py <email> [role1] [role2] ...
    
Examples:
    python scripts/assign_user_role.py user@example.com admin
    python scripts/assign_user_role.py user@example.com user
"""

import os
import sys
from pathlib import Path

# Add parent directory to path to import from src/backend/api
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root / "src" / "backend" / "api" / "src"))

from clerk_backend_api import Clerk
from config import settings


def assign_role(email: str, roles: list[str]):
    """Assign roles to a user by email address"""
    
    if not settings.clerk_secret_key:
        print("ERROR: CLERK_SECRET_KEY is not set in environment variables")
        print("Please set CLERK_SECRET_KEY in your .env file or environment")
        sys.exit(1)
    
    clerk = Clerk(bearer_auth=settings.clerk_secret_key)
    
    # Find user by email
    print(f"Searching for user with email: {email}")
    users = clerk.users.list()
    
    user = None
    for u in users:
        if u.email_addresses and len(u.email_addresses) > 0:
            if u.email_addresses[0].email_address.lower() == email.lower():
                user = u
                break
    
    if not user:
        print(f"ERROR: User with email {email} not found in Clerk")
        print("\nAvailable users:")
        for u in users[:10]:  # Show first 10 users
            email_addr = u.email_addresses[0].email_address if u.email_addresses else "No email"
            print(f"  - {email_addr} (ID: {u.id})")
        if len(users) > 10:
            print(f"  ... and {len(users) - 10} more users")
        sys.exit(1)
    
    # Get current metadata
    current_metadata = user.public_metadata if hasattr(user, 'public_metadata') and user.public_metadata else {}
    current_roles = current_metadata.get("roles", []) if isinstance(current_metadata, dict) else []
    
    # Merge roles (avoid duplicates)
    new_roles = list(set(current_roles + roles))
    
    # Update user
    print(f"\nCurrent roles: {current_roles}")
    print(f"Adding roles: {roles}")
    print(f"New roles: {new_roles}")
    
    try:
        clerk.users.update(
            user_id=user.id,
            public_metadata={
                **(current_metadata if isinstance(current_metadata, dict) else {}),
                "roles": new_roles
            }
        )
        print(f"\n✓ Successfully assigned roles to {email}")
        print(f"  User ID: {user.id}")
        print(f"  Roles: {new_roles}")
        print("\n⚠️  IMPORTANT: User must sign out and sign back in for changes to take effect")
    except Exception as e:
        print(f"\nERROR: Failed to update user: {e}")
        sys.exit(1)


def main():
    if len(sys.argv) < 3:
        print(__doc__)
        print("\nERROR: Missing required arguments")
        print("Usage: python scripts/assign_user_role.py <email> <role1> [role2] ...")
        print("\nExample: python scripts/assign_user_role.py user@example.com admin")
        sys.exit(1)
    
    email = sys.argv[1]
    roles = sys.argv[2:]
    
    # Validate roles
    valid_roles = ["admin", "user"]
    invalid_roles = [r for r in roles if r not in valid_roles]
    
    if invalid_roles:
        print(f"WARNING: Invalid roles: {invalid_roles}")
        print(f"Valid roles are: {valid_roles}")
        response = input("Continue anyway? (y/N): ")
        if response.lower() != 'y':
            sys.exit(1)
    
    assign_role(email, roles)


if __name__ == "__main__":
    main()
