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
    def check_value(value: str, salt: str, hashed_value: str) -> bool:
        """
        Returns boolean result of the given value, salt combination
        """

        if EncryptionUtil.encrypt_for_salt(value, salt) == hashed_value:
            return True

        return False
