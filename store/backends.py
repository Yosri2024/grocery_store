"""Backend d'authentification par email (insensible à la casse). 100% Python."""

from django.contrib.auth.backends import ModelBackend
from django.contrib.auth.models import User


class EmailBackend(ModelBackend):
    """Identifie le compte par email au lieu du pseudo.

    Refuse silencieusement (None) si 0 ou plusieurs comptes partagent
    l'email — anti-énumération et non-ambiguïté.
    """

    def authenticate(self, request, username=None, password=None, **kwargs):
        email = (username or kwargs.get("email") or "").strip()
        if not email or not password:
            return None
        try:
            user = User.objects.get(email__iexact=email)
        except (User.DoesNotExist, User.MultipleObjectsReturned):
            return None
        if user.check_password(password) and self.user_can_authenticate(user):
            return user
        return None
