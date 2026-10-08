from django.db import migrations, models
import django.db.models.deletion


REGIONS = [
    ('Europe', 'University of Manchester', 'United Kingdom', 'Manchester'),
    ('North America', 'University of Toronto', 'Canada', 'Toronto'),
    ('Oceania', 'University of Melbourne', 'Australia', 'Melbourne'),
    ('Asia', 'National University of Singapore', 'Singapore', 'Singapore'),
    ('Africa', 'University of Cape Town', 'South Africa', 'Cape Town'),
]


def seed_offerings(apps, schema_editor):
    Course = apps.get_model('portal', 'Course')
    Offering = apps.get_model('portal', 'CourseOffering')
    for course in Course.objects.all():
        for region, institution, country, city in REGIONS:
            Offering.objects.get_or_create(course=course, institution=institution, city=city,
                                           defaults={'region': region, 'country': country, 'active': True})


class Migration(migrations.Migration):
    dependencies = [('portal', '0007_course_catalogue_details')]
    operations = [
        migrations.CreateModel(name='CourseOffering', fields=[
            ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
            ('region', models.CharField(max_length=80)),
            ('institution', models.CharField(max_length=160)),
            ('country', models.CharField(max_length=100)),
            ('city', models.CharField(max_length=100)),
            ('active', models.BooleanField(default=True)),
            ('course', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='offerings', to='portal.course')),
        ], options={'ordering': ['region', 'country', 'institution']}) ,
        migrations.AddConstraint(model_name='courseoffering', constraint=models.UniqueConstraint(fields=('course', 'institution', 'city'), name='course_offering_unique')),
        migrations.RunPython(seed_offerings, migrations.RunPython.noop),
    ]
