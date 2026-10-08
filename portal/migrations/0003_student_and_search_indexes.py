import django.db.models.deletion
from django.db import migrations, models
from django.db.models.functions import Lower


def link_existing_students(apps, schema_editor):
    Student = apps.get_model('portal', 'Student')
    Inquiry = apps.get_model('portal', 'Inquiry')
    alias = schema_editor.connection.alias
    for inquiry in Inquiry.objects.using(alias).order_by('created_at', 'id').iterator():
        email = inquiry.email.strip().lower()
        student, _ = Student.objects.using(alias).update_or_create(email=email, defaults={
            'full_name': inquiry.full_name, 'phone': inquiry.phone, 'location': inquiry.student_location,
        })
        Inquiry.objects.using(alias).filter(pk=inquiry.pk).update(student_id=student.pk, email=email)


class Migration(migrations.Migration):
    dependencies = [('portal', '0002_inquiry_internal_notes_inquiry_status')]
    operations = [
        migrations.CreateModel(name='Student', fields=[
            ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
            ('email', models.EmailField(max_length=254)),
            ('full_name', models.CharField(max_length=120)),
            ('phone', models.CharField(max_length=30)),
            ('location', models.CharField(max_length=120)),
            ('created_at', models.DateTimeField(auto_now_add=True)),
            ('updated_at', models.DateTimeField(auto_now=True)),
        ], options={'constraints': [models.UniqueConstraint(Lower('email'), name='student_email_case_unique')]}),
        migrations.AddField(model_name='inquiry', name='student', field=models.ForeignKey(
            null=True, on_delete=django.db.models.deletion.PROTECT, related_name='inquiries', to='portal.student')),
        migrations.RunPython(link_existing_students, migrations.RunPython.noop),
        migrations.AlterField(model_name='inquiry', name='student', field=models.ForeignKey(
            on_delete=django.db.models.deletion.PROTECT, related_name='inquiries', to='portal.student')),
        migrations.RemoveIndex(model_name='inquiry', name='portal_inqu_email_39b296_idx'),
        migrations.RemoveIndex(model_name='inquiry', name='portal_inqu_full_na_a4cb0e_idx'),
        migrations.RemoveIndex(model_name='inquiry', name='portal_inqu_referen_6c3a47_idx'),
        migrations.AddIndex(model_name='inquiry', index=models.Index(fields=['student', 'course', 'event', '-created_at'], name='inquiry_duplicate_idx')),
        migrations.AddIndex(model_name='inquiry', index=models.Index(fields=['-created_at', '-id'], name='inquiry_recent_idx')),
        migrations.AddIndex(model_name='inquiry', index=models.Index(fields=['status', '-created_at'], name='inquiry_status_date_idx')),
        migrations.AddIndex(model_name='inquiry', index=models.Index(fields=['course', '-created_at'], name='inquiry_course_date_idx')),
        migrations.AddIndex(model_name='inquiry', index=models.Index(fields=['event', '-created_at'], name='inquiry_event_date_idx')),
        migrations.AddIndex(model_name='inquiry', index=models.Index(fields=['intake'], name='inquiry_intake_idx')),
        migrations.AddIndex(model_name='inquiry', index=models.Index(fields=['destination'], name='inquiry_destination_idx')),
    ]
