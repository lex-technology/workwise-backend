# app/routes/auth.py
from fastapi import APIRouter, HTTPException, Depends, Header, Request
from typing import Optional
from supabase import create_client
from fastapi import status
import os
import re
import logging
import asyncio
import jwt

router = APIRouter()
logger = logging.getLogger(__name__)

# Initialize Supabase client once
supabase = create_client(
    supabase_url=os.getenv("SUPABASE_URL"),
    supabase_key=os.getenv("SUPABASE_ANON_KEY")
)

supabase_admin = create_client(
    supabase_url=os.getenv("SUPABASE_URL"),
    supabase_key=os.getenv("SUPABASE_SERVICE_ROLE_KEY")  # For admin operations
)

def validate_email(email: str) -> bool:
    """Validate email format using regex"""
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return bool(re.match(pattern, email))

def validate_password(password: str) -> bool:
    """Validate password requirements"""
    # At least 6 characters (Supabase minimum requirement)
    return len(password) >= 6

async def check_existing_user(email: str) -> Optional[dict]:
    """
    Check if user exists in both auth and profiles
    """
    try:
        # Check user_profiles first (it's faster than checking auth)
        existing_profile = supabase.from_('user_profiles')\
            .select('*')\
            .eq('email', email)\
            .execute()
        
        if existing_profile.data:
            return {
                "exists": True,
                "message": "Email already registered"
            }

        return {"exists": False}
        
    except Exception as e:
        logger.error(f"Error checking existing user: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error checking user status"
        )


@router.post("/auth/login")
async def login(request: Request):
    try:
        data = await request.json()
        email = data.get('email')
        password = data.get('password')
        
        # Validate inputs
        if not email or not password:
            raise HTTPException(status_code=400, detail="Email and password are required")
        
        if not validate_email(email):
            raise HTTPException(status_code=400, detail="Invalid email format")
            
        if not validate_password(password):
            raise HTTPException(status_code=400, detail="Password must be at least 6 characters")

        try:
            # Sign in user
            response = supabase.auth.sign_in_with_password({
                "email": email,
                "password": password
            })
            
            return {
                "access_token": response.session.access_token,
                "user_id": response.user.id
            }
        except Exception as supabase_error:
            # Log the actual error for debugging
            print(f"Supabase login error: {str(supabase_error)}")
            raise HTTPException(status_code=401, detail="Invalid credentials")
            
    except HTTPException as he:
        raise he
    except Exception as e:
        print(f"Login error: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")

async def get_user_id(request: Request) -> Optional[str]:
    """Extract UUID from JWT token"""
    auth_header = request.headers.get('Authorization')
    
    logger.info(f"Authorization header received: {auth_header}")
    
    if not auth_header or not auth_header.startswith('Bearer '):
        raise HTTPException(status_code=401, detail="Authorization header missing")
        
    token = auth_header.split(' ')[1]
    logger.info(f"Token extracted: {token[:10]}...")
    
    try:
        # Decode JWT without verification since Supabase already verified it
        decoded = jwt.decode(token, options={"verify_signature": False})
        user_id = decoded.get('sub')  # 'sub' contains the user UUID in Supabase tokens
        logger.info(f"User ID retrieved: {user_id}")
        return user_id
    except Exception as e:
        logger.error(f"Error decoding JWT: {e}")
        raise HTTPException(status_code=401, detail="Invalid authentication token")


@router.post("/auth/signup", status_code=status.HTTP_201_CREATED)
async def signup(request: Request):
    try:
        # 1. Validate input
        data = await request.json()
        email = data.get('email')
        password = data.get('password')
        
        if not email or not password:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email and password are required"
            )
            
        # 2. Check if user already exists in user_profiles
        existing_profile = supabase.from_('user_profiles')\
            .select('*')\
            .eq('email', email)\
            .execute()
        
        if existing_profile.data:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Email already registered"
            )

        # 3. Start transaction (both operations should succeed or fail together)
        try:
            # Create auth user
            auth_response = supabase.auth.sign_up({
                "email": email,
                "password": password,
                "options": {
                    "email_confirm": True,
                    "data": {
                        "email": email,
                    }
                }
            })
            
            if not auth_response.user or not auth_response.user.id:
                raise Exception("Failed to create auth user")

            # Immediately create user profile
            try:
                supabase_admin.from_('user_profiles').insert({
                    'user_id': auth_response.user.id,
                    'email': email,
                    'monthly_ai_credits': 10,
                    'remaining_ai_credits': 10
                }).execute()
            except Exception as profile_error:
                # If profile creation fails, clean up auth user
                logger.error(f"Profile creation failed, cleaning up auth user: {profile_error}")
                try:
                    supabase_admin.auth.admin.delete_user(auth_response.user.id)
                except Exception as cleanup_error:
                    logger.error(f"Failed to cleanup auth user after profile creation failed: {cleanup_error}")
                raise Exception("Failed to complete user registration")

            return {
                "message": "Please check your email to verify your account",
                "user_id": auth_response.user.id,
                "redirect_url": "/auth/verify",
                "email_verification_required": True
            }

        except Exception as e:
            logger.error(f"Registration error: {e}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Registration failed. Please try again."
            )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred"
        )
    


@router.post("/auth/reset-password")
async def reset_password(request: Request):
    try:
        data = await request.json()
        email = data.get('email')
        
        if not email:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email is required"
            )

        # Send password reset email
        response = supabase.auth.reset_password_email(email)
        
        return {
            "message": "Password reset instructions sent to your email",
            "redirect_url": "/auth/reset-password-sent"
        }
        
    except Exception as e:
        logger.error(f"Password reset error: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Failed to send reset password email"
        )

# Route to handle the password update
@router.post("/auth/update-password")
async def update_password(request: Request):
    try:
        data = await request.json()
        new_password = data.get('password')
        
        if not new_password:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="New password is required"
            )

        # Update the password
        response = supabase.auth.update({
            "password": new_password
        })
        
        return {
            "message": "Password updated successfully",
            "redirect_url": "/auth/login"
        }
        
    except Exception as e:
        logger.error(f"Password update error: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Failed to update password"
        )