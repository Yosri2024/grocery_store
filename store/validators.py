"""Validateurs de mot de passe — 100% Python (s'appliquent à l'inscription)."""

from django.core.exceptions import ValidationError


class ComplexPasswordValidator:
    """Exige : 8+ caractères, chiffre, majuscule, minuscule, symbole."""

    def validate(self, password, user=None):
        errors = []
        if len(password or "") < 8:
            errors.append("8 caractères minimum.")
        if not any(c.isdigit() for c in password):
            errors.append("Au moins un chiffre (0-9).")
        if not any(c.isupper() for c in password):
            errors.append("Au moins une majuscule (A-Z).")
        if not any(c.islower() for c in password):
            errors.append("Au moins une minuscule (a-z).")
        if not any(not c.isalnum() for c in password):
            errors.append("Au moins un symbole (!@#…).")
        if errors:
            raise ValidationError(errors)

    def get_help_text(self):
        return "8+ caractères : majuscule, minuscule, chiffre et symbole."
