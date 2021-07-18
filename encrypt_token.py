from login.lib.cryptograpy import Crypto
import getpass

crypto = Crypto()
unencrypt_token = getpass.getpass('Enter your token:')
encrypted = crypto.encrypt_message(unencrypt_token)
print(encrypted.decode('utf-8'))
print("Token is encrypted.")
