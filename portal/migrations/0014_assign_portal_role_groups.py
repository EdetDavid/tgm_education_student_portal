from django.db import migrations


ROLE_GROUPS = ('Super Admin', 'Admin', 'Counsellor', 'Student')


def assign_existing_users(apps, schema_editor):
    User = apps.get_model('auth', 'User')
    Group = apps.get_model('auth', 'Group')
    StaffProfile = apps.get_model('portal', 'StaffProfile')
    database = schema_editor.connection.alias

    groups = {
        name: Group.objects.using(database).get_or_create(name=name)[0]
        for name in ROLE_GROUPS
    }
    for user in User.objects.using(database).all().iterator():
        if user.is_superuser:
            role = 'Super Admin'
        elif not user.is_staff:
            role = 'Student'
        else:
            profile = StaffProfile.objects.using(database).filter(user_id=user.pk).first()
            if profile and profile.role in ('Admin', 'Counsellor'):
                role = profile.role
            else:
                role = 'Counsellor' if user.groups.filter(name='Counsellor').exists() else 'Admin'

        other_role_ids = [group.pk for name, group in groups.items() if name != role]
        if other_role_ids:
            user.groups.remove(*other_role_ids)
        user.groups.add(groups[role])


class Migration(migrations.Migration):
    dependencies = [
        ('portal', '0013_portalaccesscode_code_encrypted'),
        ('auth', '0012_alter_user_first_name_max_length'),
    ]

    operations = [
        migrations.RunPython(assign_existing_users, migrations.RunPython.noop),
    ]
