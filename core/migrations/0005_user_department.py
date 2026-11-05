from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0004_user_has_ai_access'),
    ]

    operations = [
        migrations.AddField(
            model_name='user',
            name='department',
            field=models.CharField(blank=True, default='Manufacturing', max_length=100),
        ),
    ]
