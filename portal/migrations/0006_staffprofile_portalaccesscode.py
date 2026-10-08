from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [('portal', '0005_inquiry_programme_destination')]
    operations = [
        migrations.CreateModel(name='PortalAccessCode', fields=[
            ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
            ('name', models.CharField(default='super_admin', max_length=40, unique=True)),
            ('code_hash', models.CharField(max_length=128)),
            ('updated_at', models.DateTimeField(auto_now=True)),
        ]),
        migrations.CreateModel(name='StaffProfile', fields=[
            ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
            ('role', models.CharField(choices=[('Admin', 'Admin'), ('Counsellor', 'Counsellor')], max_length=20)),
            ('staff_id', models.CharField(max_length=80, unique=True)),
            ('organisation_code_hash', models.CharField(max_length=128)),
            ('user', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='staff_profile', to='auth.user')),
        ]),
    ]
