from cryptography.fernet import Fernet
import time

class Crypto(object):
    def generate_key(self):
        """
        Generates a key and save it into a file.
        Need to change the key name to secret.key when in use
        """
        timestamp = time.time()
        filename = "login/key/secret_" + str(round(timestamp)) + ".key"
        key = Fernet.generate_key()
        with open(filename, "wb") as key_file:
            key_file.write(key)

        return True

    def load_key(self):
        """
        Load the previously generated key
        """
        return open("login/key/secret.key", "rb").read()

    def encrypt_message(self, message):
        """
        Encrypts a message
        """
        key = self.load_key()
        encoded_message = message.encode()
        f = Fernet(key)
        encrypted_message = f.encrypt(encoded_message)

        return encrypted_message

    def decrypt_message(self, encrypted_message):
        """
        Decrypts an encrypted message
        """
        key = self.load_key()
        f = Fernet(key)
        decrypted_message = f.decrypt(encrypted_message)
        
        return decrypted_message.decode()
