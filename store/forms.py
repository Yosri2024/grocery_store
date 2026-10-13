"""Formulaire checkout — rendu manuel premium (checkout.html), adresse stockée en JSONField."""

from django import forms
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError as CoreValidationError
from django.core.validators import MinLengthValidator, RegexValidator

INPUT = {"class": "field-input"}


class EmailLoginForm(AuthenticationForm):
    """Connexion par email + mot de passe (le backend cherche par email)."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["username"].label = "Email"
        self.fields["username"].widget = forms.EmailInput(
            attrs={"placeholder": "vous@exemple.com", "autocomplete": "email"}
        )
        self.fields["password"].widget.attrs.update({"placeholder": "Mot de passe"})

    error_messages = {
        **AuthenticationForm.error_messages,
        "invalid_login": "Email ou mot de passe incorrect. Vérifiez vos identifiants.",
    }


class SignupForm(UserCreationForm):
    """Création de compte client (inscription). 100% Django."""

    email = forms.EmailField(
        label="Email", required=True,
        widget=forms.EmailInput(attrs={**INPUT, "placeholder": "vous@exemple.com", "autocomplete": "email"}),
    )

    class Meta(UserCreationForm.Meta):
        model = User
        fields = ("username", "email")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["username"].widget.attrs.update({**INPUT, "placeholder": "Nom d'utilisateur", "autocomplete": "username"})
        self.fields["username"].label = "Nom d'utilisateur"
        self.fields["password1"].widget.attrs.update({"class": "field-input pr-12", "placeholder": "Mot de passe", "autocomplete": "new-password"})
        self.fields["password2"].widget.attrs.update({**INPUT, "placeholder": "Confirmer le mot de passe", "autocomplete": "new-password"})

    def clean_email(self):
        # Email unique : garantit une identification non ambiguë au login.
        email = self.cleaned_data["email"].strip()
        if User.objects.filter(email__iexact=email).exists():
            raise CoreValidationError("Un compte existe déjà avec cet email. Connectez-vous.")
        return email

    def _post_clean(self):
        super()._post_clean()
        # Django colle les erreurs de complexité sur password2 : on les affiche
        # sous le champ mot de passe (mismatch/vide restent sur confirmation).
        data = self.errors.as_data()
        pw2 = data.get("password2")
        if not pw2:
            return
        move = [e for e in pw2 if e.code not in ("password_mismatch", "required")]
        if not move:
            return
        keep = [e for e in pw2 if e.code in ("password_mismatch", "required")]
        del self.errors["password2"]
        if keep:
            self.add_error("password2", CoreValidationError(keep))
        self.add_error("password1", CoreValidationError(move))


class CheckoutForm(forms.Form):
    email = forms.EmailField(
        label="Email",
        widget=forms.EmailInput(attrs={**INPUT, "placeholder": "vous@exemple.com", "autocomplete": "email"}),
    )
    first_name = forms.CharField(
        label="Prénom", max_length=100, validators=[MinLengthValidator(2)],
        widget=forms.TextInput(attrs={**INPUT, "placeholder": "Votre prénom", "autocomplete": "given-name"}),
    )
    last_name = forms.CharField(
        label="Nom", max_length=100, validators=[MinLengthValidator(2)],
        widget=forms.TextInput(attrs={**INPUT, "placeholder": "Votre nom", "autocomplete": "family-name"}),
    )
    street = forms.CharField(
        label="Rue", max_length=200, validators=[MinLengthValidator(5)],
        widget=forms.TextInput(attrs={**INPUT, "placeholder": "Rue, numéro, appartement", "autocomplete": "street-address"}),
    )
    city = forms.CharField(
        label="Ville", max_length=120, validators=[MinLengthValidator(2)],
        widget=forms.TextInput(attrs={**INPUT, "placeholder": "Ville", "autocomplete": "address-level2"}),
    )
    zip_code = forms.CharField(
        label="Code postal", max_length=20,
        validators=[RegexValidator(r"^[0-9A-Za-z\- ]{3,20}$", "Code postal invalide.")],
        widget=forms.TextInput(attrs={**INPUT, "placeholder": "XXXX", "autocomplete": "postal-code", "inputmode": "numeric"}),
    )
    phone = forms.CharField(
        label="Téléphone", max_length=30, required=False,
        widget=forms.TextInput(attrs={**INPUT, "placeholder": "XX XXX XXX", "autocomplete": "tel", "inputmode": "tel"}),
    )
    payment_method = forms.ChoiceField(
        label="Moyen de paiement",
        choices=[
            ("cash", "Espèces à la livraison"),
            ("card", "Carte bancaire"),
            ("transfer", "Virement bancaire"),
        ],
        widget=forms.RadioSelect(attrs={"class": "peer sr-only"}),
        initial="cash",
    )
    # --- Détails carte (requis seulement si paiement par carte, jamais stockés) ---
    card_number = forms.CharField(
        label="Numéro de carte", max_length=23, required=False,
        widget=forms.TextInput(attrs={**INPUT, "placeholder": "4242 4242 4242 4242", "autocomplete": "cc-number", "inputmode": "numeric"}),
    )
    card_expiry = forms.CharField(
        label="Expiration", max_length=5, required=False,
        widget=forms.TextInput(attrs={**INPUT, "placeholder": "MM/AA", "autocomplete": "cc-exp", "inputmode": "numeric"}),
    )
    card_cvc = forms.CharField(
        label="CVC", max_length=4, required=False,
        widget=forms.TextInput(attrs={**INPUT, "placeholder": "123", "autocomplete": "cc-csc", "inputmode": "numeric"}),
    )
    # --- Détails virement (référence optionnelle, conservée avec la commande) ---
    transfer_ref = forms.CharField(
        label="Référence du virement", max_length=60, required=False,
        widget=forms.TextInput(attrs={**INPUT, "placeholder": "Ex. VIR-2026-001 (optionnel)"}),
    )

    @staticmethod
    def _luhn_ok(number):
        """Contrôle de Luhn (clé de carte). 100% Python."""
        total = 0
        for i, ch in enumerate(reversed(number)):
            d = int(ch)
            if i % 2 == 1:
                d *= 2
                if d > 9:
                    d -= 9
            total += d
        return total % 10 == 0

    def clean_card_number(self):
        raw = (self.cleaned_data.get("card_number") or "").replace(" ", "")
        if not raw:
            return ""
        if not raw.isdigit() or not 13 <= len(raw) <= 19:
            raise CoreValidationError("Numéro de carte invalide (13 à 19 chiffres).")
        if not self._luhn_ok(raw):
            raise CoreValidationError("Numéro de carte invalide (clé de contrôle).")
        return raw

    def clean_card_expiry(self):
        import datetime
        import re

        raw = (self.cleaned_data.get("card_expiry") or "").strip()
        if not raw:
            return ""
        if not re.fullmatch(r"(0[1-9]|1[0-2])/\d{2}", raw):
            raise CoreValidationError("Format MM/AA exigé (ex. 09/28).")
        mm, yy = int(raw[:2]), int(raw[3:])
        now = datetime.date.today()
        if (2000 + yy, mm) < (now.year, now.month):
            raise CoreValidationError("Carte expirée.")
        return raw

    def clean_card_cvc(self):
        import re

        raw = (self.cleaned_data.get("card_cvc") or "").strip()
        if not raw:
            return ""
        if not re.fullmatch(r"\d{3,4}", raw):
            raise CoreValidationError("CVC : 3 ou 4 chiffres.")
        return raw

    def clean_phone(self):
        """8 chiffres, espaces tolérés. 100% Python."""
        raw = (self.cleaned_data.get("phone") or "").replace(" ", "")
        if not raw:
            return ""
        if not raw.isdigit() or len(raw) != 8:
            raise CoreValidationError("8 chiffres exigés.")
        return raw

    def clean(self):
        cleaned = super().clean()
        if cleaned.get("payment_method") == "card":
            for field in ("card_number", "card_expiry", "card_cvc"):
                if not cleaned.get(field):
                    self.add_error(field, "Requis pour le paiement par carte.")
        return cleaned

    def to_order_kwargs(self):
        d = self.cleaned_data
        return {
            "email": d["email"],
            "first_name": d["first_name"],
            "last_name": d["last_name"],
            "payment_method": d["payment_method"],
            "shipping_address": {
                "street": d["street"],
                "city": d["city"],
                "zip_code": d["zip_code"],
                "phone": d.get("phone", ""),
                "transfer_ref": d.get("transfer_ref", ""),
                # Données carte volontairement NON conservées (démo).
            },
        }
