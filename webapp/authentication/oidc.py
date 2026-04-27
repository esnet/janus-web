from mozilla_django_oidc.auth import OIDCAuthenticationBackend
import unicodedata


def generate_username(email):
    # Using Python 3 and Django 1.11+, usernames can contain alphanumeric
    # (ascii and unicode), _, @, +, . and - characters. So we normalize
    # it and slice at 150 characters.
    return unicodedata.normalize("NFKC", email)[:150]


# In case we want to override in the future
class JanusWebOIDCBackend(OIDCAuthenticationBackend):
    def create_user(self, claims):
        user = super(JanusWebOIDCBackend, self).create_user(claims)
        user.save()
        return user

    def update_user(self, user, claims):
        user.save()
        return user
