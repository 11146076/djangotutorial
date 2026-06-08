from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("posts", "0004_commentlike_postcomment_like_count"),
    ]

    operations = [
        migrations.AddField(
            model_name="post",
            name="image2",
            field=models.ImageField(blank=True, null=True, upload_to="posts/", verbose_name="圖片 2"),
        ),
        migrations.AddField(
            model_name="post",
            name="image3",
            field=models.ImageField(blank=True, null=True, upload_to="posts/", verbose_name="圖片 3"),
        ),
        migrations.AlterField(
            model_name="post",
            name="image",
            field=models.ImageField(
                blank=True,
                db_column="image_url",
                null=True,
                upload_to="posts/",
                verbose_name="圖片 1",
            ),
        ),
    ]
