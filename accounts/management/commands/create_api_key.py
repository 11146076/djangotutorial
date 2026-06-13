from django.core.management.base import BaseCommand

from accounts.models import ApiKey, User


class Command(BaseCommand):
    help = "為指定使用者建立 API Key（並存認證）。"

    def add_arguments(self, parser):
        parser.add_argument("username", type=str)
        parser.add_argument("--name", type=str, default="default")
        parser.add_argument("--role", type=str, default="member")

    def handle(self, *args, **options):
        user = User.objects.get(username=options["username"])
        key = ApiKey.objects.create(
            user=user,
            name=options["name"],
            key=ApiKey.generate_key(),
            role=options["role"],
        )
        self.stdout.write(self.style.SUCCESS(f"API Key created for {user.username}"))
        self.stdout.write(key.key)
