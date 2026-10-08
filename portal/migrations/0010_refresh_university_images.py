from django.db import migrations


def refresh_images(apps, schema_editor):
    University = apps.get_model('portal', 'University')
    fallback = 'https://images.unsplash.com/photo-1564981797816-1043664bf78d?auto=format&fit=crop&w=480&q=80'
    for university in University.objects.all():
        university.image_url = fallback
        university.save(update_fields=['image_url'])


class Migration(migrations.Migration):
    dependencies = [('portal', '0009_university_courseoffering_price_and_more')]
    operations = [migrations.RunPython(refresh_images, migrations.RunPython.noop)]
