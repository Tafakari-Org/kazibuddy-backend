from django.db import transaction
from django.db.models import Count, Q
from rest_framework import permissions, serializers
from rest_framework.response import Response
from rest_framework.views import APIView

from auditlogs.models import AuditLog
from auditlogs.service import log_action
from utils.custom_error import error_response
from jobs.models import Job, JobCategory

from .models import FooterCategory, FooterSettings, FooterSocialLink

MAX_SOCIAL_LINKS = 10
MAX_CATEGORIES = 12


class FooterContactSerializer(serializers.Serializer):
    phone = serializers.CharField(max_length=32, allow_blank=True, required=False, default='')
    email = serializers.EmailField(allow_blank=True, required=False, default='')
    location = serializers.CharField(max_length=255, allow_blank=True, required=False, default='')


class FooterSocialLinkSerializer(serializers.Serializer):
    platform = serializers.ChoiceField(choices=FooterSocialLink.Platform.choices)
    url = serializers.URLField(max_length=500)


class FooterCategoryInputSerializer(serializers.Serializer):
    category_id = serializers.PrimaryKeyRelatedField(queryset=JobCategory.objects.all(), source='category')
    icon = serializers.ChoiceField(choices=FooterCategory.Icon.choices, required=False,
                                   default=FooterCategory.Icon.BRIEFCASE)


class FooterUpdateSerializer(serializers.Serializer):
    contact = FooterContactSerializer()
    social_links = FooterSocialLinkSerializer(many=True, max_length=MAX_SOCIAL_LINKS)
    categories = FooterCategoryInputSerializer(many=True, max_length=MAX_CATEGORIES)

    def validate_categories(self, value):
        ids = [item['category'].pk for item in value]
        if len(ids) != len(set(ids)):
            raise serializers.ValidationError("Each category can only appear once.")
        return value


def _flatten_errors(errors, prefix=''):
    """{'social_links': [{}, {'url': [...]}]} -> {'social_links.1.url': [...]} so the client can show one message."""
    if isinstance(errors, dict):
        flat = {}
        for key, value in errors.items():
            flat.update(_flatten_errors(value, f"{prefix}.{key}" if prefix else str(key)))
        return flat
    if isinstance(errors, list) and errors and not all(isinstance(e, str) for e in errors):
        flat = {}
        for i, value in enumerate(errors):
            if value:
                flat.update(_flatten_errors(value, f"{prefix}.{i}"))
        return flat
    return {prefix: [str(e) for e in errors] if isinstance(errors, list) else [str(errors)]}


def footer_payload():
    """The footer content as the public site renders it."""
    contact = FooterSettings.load()
    open_jobs = Q(category__jobs__admin_approved=True, category__jobs__is_assigned=False) \
        & ~Q(category__jobs__status=Job.Status.CANCELLED)
    entries = (
        FooterCategory.objects
        .select_related('category')
        .filter(category__is_active=True)
        .annotate(job_count=Count('category__jobs', filter=open_jobs))
        .order_by('order', 'id')
    )
    return {
        "contact": {
            "phone": contact.phone,
            "email": contact.email,
            "location": contact.location,
        },
        "social_links": [
            {"id": link.id, "platform": link.platform, "url": link.url}
            for link in FooterSocialLink.objects.all()
        ],
        "categories": [
            {
                "id": entry.id,
                "category_id": str(entry.category_id),
                "name": entry.category.name,
                "icon": entry.icon,
                "job_count": entry.job_count,
            }
            for entry in entries
        ],
        "updated_at": contact.updated_at,
    }


class FooterView(APIView):
    """
    GET /api/adminpanel/footer/ — public; contact details, social links and featured categories.
    PUT /api/adminpanel/footer/ — admin; replaces all three sections. List order is display order.
    Body: {"contact": {...}, "social_links": [{"platform", "url"}], "categories": [{"category_id", "icon"}]}
    """

    def get_permissions(self):
        if self.request.method == 'GET':
            return [permissions.AllowAny()]
        return [permissions.IsAdminUser()]

    def get(self, request):
        return Response(footer_payload())

    def put(self, request):
        serializer = FooterUpdateSerializer(data=request.data)
        if not serializer.is_valid():
            return error_response("Please fix the highlighted footer fields.", _flatten_errors(serializer.errors))
        data = serializer.validated_data

        with transaction.atomic():
            contact = FooterSettings.load()
            for field, value in data['contact'].items():
                setattr(contact, field, value)
            contact.save()

            FooterSocialLink.objects.all().delete()
            FooterSocialLink.objects.bulk_create([
                FooterSocialLink(platform=link['platform'], url=link['url'], order=i)
                for i, link in enumerate(data['social_links'])
            ])

            FooterCategory.objects.all().delete()
            FooterCategory.objects.bulk_create([
                FooterCategory(category=item['category'], icon=item['icon'], order=i)
                for i, item in enumerate(data['categories'])
            ])

        log_action(request, AuditLog.Action.FOOTER_UPDATED, AuditLog.TargetType.SITE, 'footer', 'Site footer', {
            "contact": data['contact'],
            "social_links": [link['platform'] for link in data['social_links']],
            "categories": [item['category'].name for item in data['categories']],
        })
        return Response(footer_payload())
