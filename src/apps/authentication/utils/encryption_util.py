from django.contrib.auth.hashers import make_password, check_password


class EncryptionUtil:
    """
    Util for encryption
    """

    @staticmethod
    def encrypt(value: str):
        """
        Returns the encrypted password and the generated salt.
        """

        password = make_password(value)

        return password

    @staticmethod
    def check_value(value: str, hashed_value: str):
        """
        Returns boolean result of the given value, salt combination
        """

        return check_password(value, hashed_value)
