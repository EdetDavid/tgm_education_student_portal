from django.contrib.auth.models import Group


ROLE_GROUP_NAMES = ('Super Admin', 'Admin', 'Counsellor', 'Student')


def assign_role_group(user, role):
    """Keep exactly one built-in portal role group without touching custom groups."""
    if role not in ROLE_GROUP_NAMES:
        raise ValueError(f'Unknown portal role: {role}')
    groups = list(Group.objects.filter(name__in=ROLE_GROUP_NAMES))
    remove = [group for group in groups if group.name != role]
    if remove:
        user.groups.remove(*remove)
    role_group, _ = Group.objects.get_or_create(name=role)
    user.groups.add(role_group)


def role_group_for_user(user):
    if user.is_superuser:
        return 'Super Admin'
    if not user.is_staff:
        return 'Student'
    profile = getattr(user, 'staff_profile', None)
    if profile and profile.role in ('Admin', 'Counsellor'):
        return profile.role
    if user.groups.filter(name='Counsellor').exists():
        return 'Counsellor'
    return 'Admin'
