"""
Clerk user seeding service for local development
"""
import logging
from typing import Optional, List

from config import settings
from services.clerk_service import clerk_service

logger = logging.getLogger(__name__)


def find_user_by_email(email: str):
    """Find a user by email address"""
    try:
        users = clerk_service.clerk.users.list()
        for u in users:
            if u.email_addresses and len(u.email_addresses) > 0:
                if u.email_addresses[0].email_address.lower() == email.lower():
                    return u
        return None
    except Exception as e:
        logger.error(f"Failed to list users: {e}")
        return None


def seed_clerk_user(
    email: Optional[str] = None,
    password: Optional[str] = None,
    roles: Optional[List[str]] = None,
) -> bool:
    """
    Seed a Clerk user account for local development.

    Args:
        email: Email address (defaults to settings.clerk_seed_email)
        password: Password (defaults to settings.clerk_seed_password)
        roles: List of roles (defaults to settings.clerk_seed_roles)

    Returns:
        True if successful, False otherwise
    """
    # Get configuration from settings or parameters
    seed_email = email or settings.clerk_seed_email
    seed_password = password or settings.clerk_seed_password
    seed_roles_str = settings.clerk_seed_roles
    seed_roles = [role.strip() for role in seed_roles_str.split(",") if role.strip()]

    if not seed_roles:
        seed_roles = ["admin", "user"]

    # Validate Clerk secret key
    if not settings.clerk_secret_key:
        logger.warning("CLERK_SECRET_KEY is not set. Cannot seed Clerk user.")
        return False

    try:
        clerk = clerk_service.clerk

        # Check if user already exists
        logger.info(f"Checking if user with email {seed_email} already exists...")
        existing_user = find_user_by_email(seed_email)

        if existing_user:
            logger.info(f"User {seed_email} already exists (ID: {existing_user.id})")
            user = existing_user
            user_created = False
            
            # Update password for existing user using create_password method
            logger.info(f"Setting password for existing user: {seed_email}")
            try:
                # Clerk's create_password method sets/updates the password
                # This is the correct way to set passwords on existing users
                clerk.users.create_password(
                    user_id=user.id,
                    password=seed_password,
                    skip_password_checks=True,  # Allow simple passwords for dev
                )
                logger.info(f"Password set successfully for user: {seed_email}")
            except AttributeError:
                # Fallback: try update method if create_password doesn't exist
                try:
                    clerk.users.update(
                        user_id=user.id,
                        password=seed_password,
                        skip_password_checks=True,
                    )
                    logger.info(f"Password updated via update method for user: {seed_email}")
                except Exception as e:
                    logger.warning(f"Could not set password for existing user: {e}")
                    logger.info("User exists but password may not be set. You may need to reset it manually via Clerk dashboard.")
            except Exception as e:
                logger.warning(f"Failed to set password: {e}")
                logger.info("Continuing with role assignment...")
        else:
            # Create new user
            logger.info(f"Creating new user with email: {seed_email}")
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
                logger.info(f"Successfully created user: {seed_email} (ID: {user.id})")
                user_created = True
            except Exception as e:
                logger.error(f"Failed to create user: {e}")
                return False
        
        # Ensure email is verified (required for password authentication)
        try:
            # Check if email is verified
            if user.email_addresses and len(user.email_addresses) > 0:
                email_address = user.email_addresses[0]
                is_verified = False
                
                # Check verification status
                if hasattr(email_address, 'verification'):
                    if email_address.verification:
                        if hasattr(email_address.verification, 'status'):
                            is_verified = email_address.verification.status == "verified"
                        elif isinstance(email_address.verification, dict):
                            is_verified = email_address.verification.get("status") == "verified"
                
                if not is_verified:
                    logger.info(f"Email {seed_email} is not verified, attempting to verify...")
                    # Try to verify email using Clerk's API
                    try:
                        # Use create_email_address_verification or verify_email_address
                        if hasattr(clerk.users, 'create_email_address_verification'):
                            verification = clerk.users.create_email_address_verification(
                                user_id=user.id,
                                email_address_id=email_address.id,
                            )
                            logger.info(f"Email verification initiated for user: {seed_email}")
                        elif hasattr(clerk.users, 'verify_email_address'):
                            clerk.users.verify_email_address(
                                user_id=user.id,
                                email_address_id=email_address.id,
                            )
                            logger.info(f"Email verified for user: {seed_email}")
                        else:
                            logger.warning("Email verification method not available - email may need manual verification in Clerk dashboard")
                    except Exception as e:
                        logger.warning(f"Could not verify email automatically: {e}")
                        logger.info("Note: You may need to verify the email manually in Clerk dashboard for password authentication to work")
                else:
                    logger.info(f"Email {seed_email} is already verified")
        except Exception as e:
            logger.warning(f"Could not check/verify email: {e}")

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
            logger.info(f"Updating user roles: {current_roles} -> {new_roles}")
            try:
                clerk.users.update(
                    user_id=user.id,
                    public_metadata={
                        **(current_metadata if isinstance(current_metadata, dict) else {}),
                        "roles": new_roles,
                    },
                )
                logger.info(f"Successfully assigned roles to {seed_email}")
            except Exception as e:
                logger.error(f"Failed to update user roles: {e}")
                return False
        else:
            logger.info(f"User already has required roles: {current_roles}")

        logger.info(f"Clerk user seeded successfully: {seed_email} (ID: {user.id}, Roles: {new_roles})")
        return True

    except Exception as e:
        logger.error(f"Error seeding Clerk user: {e}", exc_info=True)
        return False
