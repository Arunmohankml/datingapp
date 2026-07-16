from django.db import migrations


def drop_stale_device_id(apps, schema_editor):
    table_name = 'home_fcmtoken'
    column_name = 'device_id'
    with schema_editor.connection.cursor() as cursor:
        existing_columns = [
            column.name
            for column in schema_editor.connection.introspection.get_table_description(cursor, table_name)
        ]
        if column_name not in existing_columns:
            return
        schema_editor.execute(f'ALTER TABLE {schema_editor.quote_name(table_name)} DROP COLUMN {schema_editor.quote_name(column_name)}')


class Migration(migrations.Migration):

    dependencies = [
        ('home', '0064_community_message_kind'),
    ]

    operations = [
        migrations.RunPython(drop_stale_device_id, migrations.RunPython.noop),
    ]
