#!/usr/bin/env python3
"""
Script to seed a Clerk user account for local development.

This script creates a Clerk user with email/password authentication and assigns
default roles (admin, user). It is idempotent - safe to run multiple times.

Usage:
    # With defaults (dev@localhost / dev123)
    python scripts/seed_clerk_user.py

    # With custom credentials via environment variables
    CLERK_SEED_EMAIL=admin@localhost CLERK_SEED_PASSWORD=admin123 python scripts/seed_clerk_user.py

    # With custom roles
    CLERK_SEED_ROLES=admin,user python scripts/seed_clerk_user.py

Environment Variables:
    CLERK_SEED_EMAIL: Email address for the seed user (default: dev@localhost)
    CLERK_SEED_PASSWORD: Password for the seed user (default: dev123)
    CLERK_SEED_ROLES: Comma-separated list of roles (default: admin,user)
"""

import os
import sys
from pathlib import Path

# Add parent directory to path to import from src/backend/api
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root / "src" / "backend" / "api" / "src"))

from clerk_backend_api import Clerk
from config import settings


def find_user_by_email(clerk: Clerk, email: str):
    """Find a user by email address"""
    users = clerk.users.list()
    for u in users:
        if u.email_addresses and len(u.email_addresses) > 0:
            if u.email_addresses[0].email_address.lower() == email.lower():
                return u
    return None


def seed_clerk_user(
    email: str = None,
    password: str = None,
    roles: list[str] = None,
):
    """
    Seed a Clerk user account for local development.

    Args:
        email: Email address (defaults to CLERK_SEED_EMAIL or dev@localhost)
        password: Password (defaults to CLERK_SEED_PASSWORD or dev123)
        roles: List of roles (defaults to CLERK_SEED_ROLES or ["admin", "user"])
    """
    # Get configuration from environment or defaults
    seed_email = email or os.getenv("CLERK_SEED_EMAIL", "dev@localhost")
    seed_password = password or os.getenv("CLERK_SEED_PASSWORD", "dev123")
    seed_roles_str = os.getenv("CLERK_SEED_ROLES", "admin,user")
    seed_roles = [role.strip() for role in seed_roles_str.split(",") if role.strip()]

    if not seed_roles:
        seed_roles = ["admin", "user"]

    # Validate Clerk secret key
    if not settings.clerk_secret_key:
        print("ERROR: CLERK_SECRET_KEY is not set in environment variables")
        print("Please set CLERK_SECRET_KEY in your .env file or environment")
        sys.exit(1)

    clerk = Clerk(bearer_auth=settings.clerk_secret_key)

    # Check if user already exists
    print(f"Checking if user with email {seed_email} already exists...")
    existing_user = find_user_by_email(clerk, seed_email)

    if existing_user:
        print(f"✓ User {seed_email} already exists (ID: {existing_user.id})")
        user = existing_user
        user_created = False
    else:
        # Create new user
        print(f"Creating new user with email: {seed_email}")
        try:
            # Create user with email and password
            # Note: Clerk Python SDK uses email_address (singular) for list of emails
            # and skip_password_checks may not be available in all versions
            try:
                user = clerk.users.create(
                    email_address=[seed_email],
                    password=seed_password,
                    skip_password_checks=True,  # Allow simple passwords for dev
                )
            except TypeError:
                # Fallback if skip_password_checks is not supported
                user = clerk.users.create(
                    email_address=[seed_email],
                    password=seed_password,
                )
            print(f"✓ Successfully created user: {seed_email} (ID: {user.id})")
            user_created = True
        except Exception as e:
            print(f"ERROR: Failed to create user: {e}")
            print(f"Error details: {type(e).__name__}: {str(e)}")
            sys.exit(1)

    # Get current metadata
    current_metadata = (
        user.public_metadata
        if hasattr(user, "public_metadata") and user.public_metadata
        else {}
    )
    current_roles = (
        current_metadata.get("roles", [])
        if isinstance(current_metadata, dict)
        else []
    )

    # Merge roles (avoid duplicates)
    new_roles = list(set(current_roles + seed_roles))

    # Update user with roles if needed
    if set(current_roles) != set(new_roles) or user_created:
        print(f"\nUpdating user roles...")
        print(f"  Current roles: {current_roles}")
        print(f"  Adding roles: {seed_roles}")
        print(f"  New roles: {new_roles}")

        try:
            clerk.users.update(
                user_id=user.id,
                public_metadata={
                    **(current_metadata if isinstance(current_metadata, dict) else {}),
                    "roles": new_roles,
                },
            )
            print(f"✓ Successfully assigned roles to {seed_email}")
        except Exception as e:
            print(f"ERROR: Failed to update user roles: {e}")
            sys.exit(1)
    else:
        print(f"✓ User already has required roles: {current_roles}")

    # Print success message with credentials
    print("\n" + "=" * 60)
    print("✓ Clerk user seeded successfully!")
    print("=" * 60)
    print(f"\nCredentials:")
    print(f"  Email:    {seed_email}")
    print(f"  Password: {seed_password}")
    print(f"  Roles:    {', '.join(new_roles)}")
    print(f"  User ID:  {user.id}")
    print("\nYou can now sign in to the dashboard using these credentials.")
    if not user_created:
        print("\n⚠️  NOTE: User already existed. Roles were updated if needed.")
    print("\n⚠️  IMPORTANT: If the user is already signed in, they must sign out")
    print("   and sign back in for role changes to take effect.")
    print("=" * 60)


def main():
    """Main entry point"""
    seed_clerk_user()


if __name__ == "__main__":
    main()
