from django.contrib import admin

from .models import FooterCategory, FooterSettings, FooterSocialLink

admin.site.register(FooterSettings)
admin.site.register(FooterSocialLink)
admin.site.register(FooterCategory)
