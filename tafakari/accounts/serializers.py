from rest_framework import serializers
from django.contrib.auth import authenticate
from django.contrib.auth.password_validation import validate_password
from django.contrib.auth.tokens import PasswordResetTokenGenerator
from django.utils.http import urlsafe_base64_decode
from django.utils.encoding import force_str
from django.db import transaction
from .models import CustomUser
from dj_rest_auth.registration.serializers import RegisterSerializer
from utils.logger import get_logger

logger = get_logger(__name__)


class RegisterUserSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True)
    

    class Meta:
        model = CustomUser
        fields = ['phone_number', 'email', 'password', 'user_type', 'full_name','username']
        

    

    def create(self, validated_data):
        password = validated_data.pop('password')
        # Atomic: user creation + password set must succeed or fail together
        logger.debug(f"Creating new user with email: {validated_data.get('email')}")
        with transaction.atomic():
            user = CustomUser.objects.create_user(**validated_data)
            user.set_password(password)
            user.save()
        logger.info(f"Successfully created user ID: {user.id}")
        return user
    
class LoginSerializer(serializers.Serializer):
    identifier = serializers.CharField()  # Can be phone_number or email
    password = serializers.CharField(write_only=True)

    def validate(self, data):
        identifier = data.get('identifier')
        password = data.get('password')

        try:
            user = CustomUser.objects.get(phone_number=identifier)
        except CustomUser.DoesNotExist:
            try:
                user = CustomUser.objects.get(email=identifier)
            except CustomUser.DoesNotExist:
                raise serializers.ValidationError("Invalid phone number or email")

        if not user.check_password(password):
            logger.warning(f"Login validation failed: Incorrect password for identifier {identifier}")
            raise serializers.ValidationError("Incorrect password")
        if not user.is_active:
            logger.warning(f"Login validation failed: Account inactive for identifier {identifier}")
            raise serializers.ValidationError("User account is inactive")

        logger.debug(f"Login validation successful for user: {user.email}")
        return {"user": user}


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = CustomUser
        fields = ['id', 'full_name', 'email']
        read_only_fields = ['id', 'full_name', 'email']
    




class CustomRegisterSerializer(RegisterSerializer):
    username = None  # Explicitly remove the username field

    def get_cleaned_data(self):
        data = super().get_cleaned_data()
        data['email'] = self.validated_data.get('email', '')
        data['password1'] = self.validated_data.get('password', '')
        return data

class GoogleOAuthUserSerializer(serializers.ModelSerializer):
    class Meta:
        model = CustomUser
        fields = ['email', 'user_type', 'full_name', 'profile_photo_url']
    
    def create(self, validated_data):
        # Atomic: OAuth user creation + flag updates must succeed or fail together
        email = validated_data.get('email')
        logger.debug(f"Creating new Google OAuth user: {email}")
        with transaction.atomic():
            user = CustomUser.objects.create_user(
                email=validated_data['email'],
                phone_number=None,  # No phone number for OAuth users
                password=None,
                **{k: v for k, v in validated_data.items() if k != 'email'}
            )
            user.set_unusable_password()
            user.is_oauth_user = True
            user.email_verified = True
            user.save()
        return user


# ---------------------------------------------------------------------------
# Password Reset (token-based, secure)
# ---------------------------------------------------------------------------

class PasswordResetRequestSerializer(serializers.Serializer):
    """
    Accepts an email address. Validation only checks the format; the view
    is responsible for the user lookup so that we never reveal whether an
    email exists in the system (enumeration protection).
    """
    email = serializers.EmailField(required=True)


class PasswordResetConfirmSerializer(serializers.Serializer):
    """
    Accepts uidb64, token, and new_password.
    Performs full token validation and password strength checks inside
    validate() so the view only needs to call set_password().
    """
    uidb64 = serializers.CharField(required=True)
    token = serializers.CharField(required=True)
    new_password = serializers.CharField(
        required=True,
        write_only=True,
        min_length=8,
        style={'input_type': 'password'},
    )

    def validate_new_password(self, value):
        """Run Django's AUTH_PASSWORD_VALIDATORS against the new password."""
        try:
            validate_password(value)
        except Exception as e:
            raise serializers.ValidationError(list(e.messages))
        return value

    def validate(self, data):
        # Decode the user PK
        try:
            uid = force_str(urlsafe_base64_decode(data['uidb64']))
            user = CustomUser.objects.get(pk=uid)
        except (TypeError, ValueError, OverflowError, CustomUser.DoesNotExist):
            raise serializers.ValidationError(
                {'uidb64': 'Invalid or expired reset link.'}
            )

        # Verify the token
        token_generator = PasswordResetTokenGenerator()
        if not token_generator.check_token(user, data['token']):
            raise serializers.ValidationError(
                {'token': 'Invalid or expired reset link.'}
            )

        # Attach the user so the view can retrieve it from validated_data
        data['user'] = user
        return data