from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('home', '0063_community_membership_and_mute'),
    ]

    operations = [
        migrations.AddField(
            model_name='communitymessage',
            name='kind',
            field=models.CharField(
                choices=[
                    ('message', 'Message'),
                    ('join', 'Member joined'),
                    ('leave', 'Member left'),
                ],
                db_index=True,
                default='message',
                max_length=12,
            ),
        ),
    ]
