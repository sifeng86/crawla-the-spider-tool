from login.lib.cryptograpy import Crypto

crypto = Crypto()
if crypto.generate_key():
    print("Key is generated. Please keep it safe.")
    print("Need to change the key name to secret.key when in use")
