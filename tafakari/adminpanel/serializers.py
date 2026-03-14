from rest_framework import serializers
from django.contrib.auth.password_validation import validate_password
from accounts.models import CustomUser


class ApproveUserSerializer(serializers.ModelSerializer):
    class Meta:
        model = CustomUser
        fields = ['id', 'phone_number', 'is_verified', 'email_verified', 'phone_verified']


class UserStatusSerializer(serializers.ModelSerializer):
    class Meta:
        model = CustomUser
        fields = ['id', 'full_name', 'phone_number', 'email', 'is_active', 'is_verified']


# ---------------------------------------------------------------------------
# Admin / SuperAdmin management
# ---------------------------------------------------------------------------

ADMIN_USER_TYPES = ('admin', 'super_admin')


class CreateAdminSerializer(serializers.Serializer):
    """
    Validates input for creating an admin or super_admin account.
    The `user_type` is NOT accepted from the request body — it is
    injected by the view so each endpoint controls its own role.
    """
    full_name = serializers.CharField(max_length=255)
    email = serializers.EmailField()
    phone_number = serializers.CharField(max_length=20, required=False, allow_blank=True, default=None)
    password = serializers.CharField(write_only=True, min_length=8, style={'input_type': 'password'})

    def validate_email(self, value):
        if CustomUser.objects.filter(email=value).exists():
            raise serializers.ValidationError("A user with this email already exists.")
        return value

    def validate_phone_number(self, value):
        if value and CustomUser.objects.filter(phone_number=value).exists():
            raise serializers.ValidationError("A user with this phone number already exists.")
        return value or None

    def validate_password(self, value):
        try:
            validate_password(value)
        except Exception as exc:
            raise serializers.ValidationError(list(exc.messages))
        return value


class AdminDetailSerializer(serializers.ModelSerializer):
    """Read / partial-update representation of an admin user."""

    class Meta:
        model = CustomUser
        fields = [
            'id', 'full_name', 'email', 'phone_number',
            'user_type', 'is_active', 'is_verified',
            'email_verified', 'phone_verified',
            'profile_photo_url', 'last_login', 'created_at',
        ]
        read_only_fields = ['id', 'user_type', 'email_verified', 'phone_verified', 'last_login', 'created_at']

    def validate_email(self, value):
        instance = self.instance
        qs = CustomUser.objects.filter(email=value)
        if instance:
            qs = qs.exclude(pk=instance.pk)
        if qs.exists():
            raise serializers.ValidationError("A user with this email already exists.")
        return value

    def validate_phone_number(self, value):
        if not value:
            return value
        instance = self.instance
        qs = CustomUser.objects.filter(phone_number=value)
        if instance:
            qs = qs.exclude(pk=instance.pk)
        if qs.exists():
            raise serializers.ValidationError("A user with this phone number already exists.")
        return value