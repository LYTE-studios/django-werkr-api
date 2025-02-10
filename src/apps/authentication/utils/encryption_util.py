import bcrypt


class EncryptionUtil:
    """
    Util for encryption
    """

    @staticmethod
    def encrypt(value: str):
        """
        Returns the encrypted password and the generated salt.
        """

        salt = bcrypt.gensalt()

        hashed_value = bcrypt.hashpw(bytes(value, "utf-8"), salt=salt)

        return hashed_value.decode("utf-8"), salt.decode("utf-8")

    @staticmethod
    def encrypt_for_salt(value: str, salt: str):
        """
        Returns the encrypted password with specified salt.
        """

        hashed_value = bcrypt.hashpw(bytes(value, "utf-8"), salt=bytes(salt, "utf-8"))

        return hashed_value.decode("utf-8")

    @staticmethod
    def check_value(value: str, salt: str, hashed_value: str) -> bool:
        """
        Returns boolean result of the given value, salt combination
        """

        if EncryptionUtil.encrypt_for_salt(value, salt) == hashed_value:
            return True

        return False
