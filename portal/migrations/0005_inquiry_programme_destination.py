from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('portal', '0004_postgres_substring_indexes')]

    operations = [
        migrations.AddField(
            model_name='inquiry', name='programme_type',
            field=models.CharField(default='Undergraduate', max_length=40),
        ),
        migrations.AddField(
            model_name='inquiry', name='destination_city',
            field=models.CharField(blank=True, max_length=100),
        ),
    ]
