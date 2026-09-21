import factory
from django.contrib.auth import get_user_model
from django.utils import timezone

DEFAULT_PASSWORD = "correct-horse-battery"


class UserFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = get_user_model()
        skip_postgeneration_save = True

    username = factory.Sequence(lambda n: f"user{n}")
    email = factory.LazyAttribute(lambda o: f"{o.username}@example.org")
    first_name = "Prénom"
    last_name = factory.Sequence(lambda n: f"Nom{n}")
    email_verified_at = factory.LazyFunction(timezone.now)
    password = factory.django.Password(DEFAULT_PASSWORD)
