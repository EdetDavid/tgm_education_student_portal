from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('portal', '0006_staffprofile_portalaccesscode')]
    operations = [
        migrations.AddField(model_name='course', name='institution', field=models.CharField(default='TGM Education Partner University', max_length=160)),
        migrations.AddField(model_name='course', name='region', field=models.CharField(default='United Kingdom', max_length=80)),
        migrations.AddField(model_name='course', name='study_country', field=models.CharField(default='United Kingdom', max_length=100)),
        migrations.AddField(model_name='course', name='study_city', field=models.CharField(default='London', max_length=100)),
        migrations.RunPython(
            lambda apps, schema_editor: populate_catalogue(apps),
            migrations.RunPython.noop,
        ),
    ]


def populate_catalogue(apps):
    Course = apps.get_model('portal', 'Course')
    rows = [
        ('Business Management', 'University of Manchester', 'Europe', 'United Kingdom', 'Manchester'),
        ('Computer Science', 'University of Birmingham', 'Europe', 'United Kingdom', 'Birmingham'),
        ('Data Science', 'University of Edinburgh', 'Europe', 'United Kingdom', 'Edinburgh'),
        ('Cyber Security', 'University of Toronto', 'North America', 'Canada', 'Toronto'),
        ('International Relations', 'McGill University', 'North America', 'Canada', 'Montreal'),
        ('Engineering Management', 'University of British Columbia', 'North America', 'Canada', 'Vancouver'),
        ('Accounting and Finance', 'University of Melbourne', 'Oceania', 'Australia', 'Melbourne'),
        ('Marketing', 'UNSW Sydney', 'Oceania', 'Australia', 'Sydney'),
        ('Artificial Intelligence', 'University of Sydney', 'Oceania', 'Australia', 'Sydney'),
        ('Public Health', 'Trinity College Dublin', 'Europe', 'Ireland', 'Dublin'),
        ('Architecture', 'University College Dublin', 'Europe', 'Ireland', 'Dublin'),
        ('Law', 'University of Amsterdam', 'Europe', 'Netherlands', 'Amsterdam'),
        ('Psychology', 'Technical University of Munich', 'Europe', 'Germany', 'Munich'),
        ('Media and Communications', 'Sorbonne University', 'Europe', 'France', 'Paris'),
        ('Project Management', 'University of California, Berkeley', 'North America', 'United States', 'Berkeley'),
        ('Biomedical Science', 'University of Washington', 'North America', 'United States', 'Seattle'),
        ('Hospitality Management', 'Northeastern University', 'North America', 'United States', 'Boston'),
        ('Education', 'University of Glasgow', 'Europe', 'United Kingdom', 'Glasgow'),
        ('Software Engineering', 'University of Leeds', 'Europe', 'United Kingdom', 'Leeds'),
        ('Economics', 'University of Nottingham', 'Europe', 'United Kingdom', 'Nottingham'),
    ]
    for name, institution, region, country, city in rows:
        Course.objects.filter(name=name).update(institution=institution, region=region, study_country=country, study_city=city)
