from django.contrib.auth import get_user_model

User = get_user_model()


def get_user_with_profile(user: User) -> dict:
    return {
        "id": user.id,
        "full_name": user.get_full_name(),
        "image": user.image,
        "email": user.email,
        "identity_verification_status": user.identity_verification_status,
        "status": user.status,
        "bio": user.userprofile.bio,
        "date_joined": str(user.date_joined),
        "languages": user.userprofile.languages,
        "address": user.userprofile.address,
        "phone_number": user.phone_number,
        "current_superhost_tier": user.current_superhost_tier,
    }
