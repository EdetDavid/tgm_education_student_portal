from django.db import migrations


# Django's PostgreSQL icontains lookup uses UPPER(column) LIKE UPPER(pattern).
# Index the same expression, rather than an unused plain-column trigram index.
SEARCH_COLUMNS = {
    'portal_inquiry': ['full_name', 'email', 'phone', 'reference', 'student_location'],
    'portal_course': ['name', 'level', 'location'],
}


def add_indexes(apps, schema_editor):
    if schema_editor.connection.vendor != 'postgresql':
        return
    schema_editor.execute('CREATE EXTENSION IF NOT EXISTS pg_trgm')
    for table, columns in SEARCH_COLUMNS.items():
        for column in columns:
            schema_editor.execute(
                f'CREATE INDEX IF NOT EXISTS {table}_{column}_trgm '
                f'ON {table} USING gin (UPPER({column}) gin_trgm_ops)')


def remove_indexes(apps, schema_editor):
    if schema_editor.connection.vendor != 'postgresql':
        return
    for table, columns in SEARCH_COLUMNS.items():
        for column in columns:
            schema_editor.execute(f'DROP INDEX IF EXISTS {table}_{column}_trgm')


class Migration(migrations.Migration):
    dependencies = [('portal', '0003_student_and_search_indexes')]
    operations = [migrations.RunPython(add_indexes, remove_indexes)]
