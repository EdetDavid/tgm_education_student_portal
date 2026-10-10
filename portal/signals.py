from django.conf import settings
from django.db.models.signals import post_save
from django.dispatch import receiver

from .user_groups import assign_role_group, role_group_for_user


@receiver(post_save, sender=settings.AUTH_USER_MODEL)
def synchronize_portal_role_group(sender, instance, **kwargs):
    assign_role_group(instance, role_group_for_user(instance))
