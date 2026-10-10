from .models import ActivityLog


def role_for_user(user):
    if not user or not user.is_authenticated:
        return 'Student'
    if user.is_superuser:
        return 'Super Admin'
    if user.groups.filter(name='Counsellor').exists():
        return 'Counsellor'
    return 'Admin' if user.is_staff else 'Student'


def record_activity(request, action, entity_type, summary, *, entity_id='',
                    details=None, actor=None, actor_label=None, actor_role=None):
    """Store a concise audit event; never pass passwords, secrets or private notes."""
    actor = actor or getattr(request, 'user', None)
    is_authenticated = bool(actor and actor.is_authenticated)
    return ActivityLog.objects.create(
        actor=actor if is_authenticated else None,
        actor_label=actor_label or (actor.get_username() if is_authenticated else 'Student application form'),
        actor_role=actor_role or role_for_user(actor),
        action=action,
        entity_type=entity_type,
        entity_id=str(entity_id or ''),
        summary=summary,
        details=details or {},
    )
