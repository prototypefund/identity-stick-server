# This is a modification of an example for an hmac-secret extension used by Yubico AB
# 
#
# Copyright (c) 2018 Yubico AB
# All rights reserved.
#
#   Redistribution and use in source and binary forms, with or
#   without modification, are permitted provided that the following
#   conditions are met:
#
#    1. Redistributions of source code must retain the above copyright
#       notice, this list of conditions and the following disclaimer.
#    2. Redistributions in binary form must reproduce the above
#       copyright notice, this list of conditions and the following
#       disclaimer in the documentation and/or other materials provided
#       with the distribution.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS
# "AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT
# LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS
# FOR A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE
# COPYRIGHT HOLDER OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT,
# INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING,
# BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES;
# LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER
# CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT
# LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN
# ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE
# POSSIBILITY OF SUCH DAMAGE.

"""
Connects to the first FIDO device found which supports the identity-stick extension, 
checks the data provided by the extension and will then receive the data.
"""
from __future__ import print_function, absolute_import, unicode_literals

from fido2.hid import CtapHidDevice
from fido2_adapted.client import Fido2Client
from fido2_adapted.identity_extension import IdentityStickExtension
from getpass import getpass
from binascii import b2a_hex
from identity_data import load_key_from_url, check_sig
import sys
import os
import json
from Crypto.Hash import SHA256


"""
####################
###   CONSTANTS  ###
####################
"""
IDENT_ABBREVIATIONS = {"uN": "userName","n": "name", "n-f": "formatted", "n-fN": "familyName", "n-gN": "givenName", "n-mN": "middleName", "n-hP": "honoricPrefix", "n-hS": "honoricSuffix","dP": "displayName","nN": "nickName","pU": "profileUrl","t": "title","uT": "userType","pL": "preferredLanguage","l": "locale","tz": "timezone","a": "active","p": "password","e": "emails","pNs": "phoneNumbers","ims": "ims","phs": "photos","add": "addresses","gr": "groups","en": "entitlements","r": "roles","x": "x509Certificates", "g-dN": "displayname","g-m": "members","eN": "employeeNumber","cC": "costCenter","o": "organization","d": "division","dpm": "department","m": "manager","aI": "additionalInfo","bD": "birthdate"}
KEY_URL = None 
DEFAULT_KEY_URL = "<SET A DEFAULT URL HERE>"
"""
##################
###   METHODS  ###
##################
"""
def update_progress(progress):
    sys.stdout.write('\rReceiving data [{0}] {1}%'.format('#'*(progress), progress))
    sys.stdout.flush()

def get_identity_data(client, wanted_data, rp, challenge, allow_list, ident_ext, user_presence, pin):
    # Get the number of
    assertions, client_data = client.get_assertion(
            {
                "rpId": rp["id"],
                "challenge": challenge,
                "allowCredentials": allow_list,
                "extensions": ident_ext.get_dict(2,wanted_data, 0),
                "user_presence": user_presence
            },
            pin=pin,
        )




    # Identity extension result:
    assertion = assertions[0]  # Only one cred in allowList, only one response.
    number_of_msg = ident_ext.results_for(assertion.auth_data)
    received_data = ""

    for i in range(0,number_of_msg):

        assertions, client_data = client.get_assertion(
            {
                "rpId": rp["id"],
                "challenge": challenge,
                "allowCredentials": allow_list,
                "extensions": ident_ext.get_dict(4,wanted_data, i),
                "user_presence": "discouraged"
            },
            pin=pin,
        )


        # Identity extension result:
        assertion = assertions[0]  # Only one cred in allowList, only one response.
        ident_result = ident_ext.results_for(assertion.auth_data)

        received_data += str(ident_result)
        update_progress(int(i/number_of_msg * 100))

    update_progress(100)
    return received_data

def check_data(received_data, public_key_url):
    hash_val = SHA256.new(received_data['value'].encode('utf-8'))
    signature = bytes.fromhex(received_data['sign'])
    public_key = load_key_from_url(public_key_url)
    print("Signature is checked: " + str(check_sig(public_key, hash_val, signature)))

def enumerate_devices():
    for dev in CtapHidDevice.list_devices():
        yield dev
    if CtapPcscDevice:
        for dev in CtapPcscDevice.list_devices():
            yield dev

def find_device():
    for dev in enumerate_devices():
        client = Fido2Client(dev, "https://beispieldienst.de")
        if IdentityStickExtension.NAME in client.info.extensions:
            break
    else:
        print("No Authenticator with the IdentityStickExtension extension found!")
        sys.exit(1)

    return client

def prepare_parameters():
    rp = {"id": "beispieldienst.de", "name": "Beispieldienst"}
    user = {"id": b"user_id", "name": "A. User"}
    challenge = b"Y2hhbGxlbmdl"
    
    return (rp,user,challenge)

def get_pin(client):
    pin = None
    if client.info.options.get("clientPin"):
        pin = getpass("Please enter PIN:")
    else:
        print("No pin needed")
    return pin

def retrieve_data(req_attribute, message, up_option, key_url, rp, challenge, allow_list, ident_ext, pin, client, use_nfc):
    # Authenticate the credential
    if not use_nfc and up_option == "required":
        print("\nWe are now accessing your " + message + ". Touch your authenticator device now to authenticate that process...\n")

    received_data = get_identity_data(client, req_attribute, rp, challenge, allow_list, ident_ext, up_option, pin)
    print(received_data)
    received_data = json.loads(received_data)
    print("\nReceived "+ message + ": " + str(received_data['value']))
    check_data(received_data, key_url)
"""
###############
###   MAIN  ###
###############
"""
def main():
    try:
        from fido2.pcsc import CtapPcscDevice
    except ImportError:
        CtapPcscDevice = None

    # Locate a device
    client = find_device()

    use_nfc = CtapPcscDevice and isinstance(dev, CtapPcscDevice)

    # Prepare parameters for makeCredential
    rp, user, challenge = prepare_parameters()

    # Prompt for PIN if needed
    pin = get_pin(client)

    # Initialize identity stick extension
    ident_ext = IdentityStickExtension(client.ctap2)

    # Check the data available on the identity stick
    if not use_nfc:
        print("\nWe want to access your identity stick to check, what information would be available.\nTouch your authenticator device now to approve this step...\n")
    attestation_object, client_data = client.make_credential(
        {
            "rp": rp,
            "user": user,
            "challenge": challenge,
            "pubKeyCredParams": [{"type": "public-key", "alg": -7}],
            "extensions": ident_ext.create_dict()
        },
        pin=pin,
    )

    # Retrieve data from result
    ident_result = ident_ext.results_for(attestation_object.auth_data)

    # Show the available data on the identity stick
    print("You have the following attributes available for access: ")
    for abbreviation in ident_result['available-data']:
        print(IDENT_ABBREVIATIONS[abbreviation])
    
    # Prepare parameters for getAssertion
    credential = attestation_object.auth_data.credential_data
    challenge = b"Q0hBTExFTkdF"  # Use a new challenge for each call.
    allow_list = [{"type": "public-key", "id": credential.credential_id}]

    # Get the key, if it needs to be requested seperately, do so
    try:
        KEY_URL = ident_result['pub_key']
        if KEY_URL == "REQUEST":
            if not use_nfc:
                print("\nWe are now accessing the publickey. Touch your authenticator device now to authenticate that process...\n")

            received_data = get_identity_data(client, "pubkey", rp, challenge, allow_list, ident_ext, "required", pin)
            received_data = json.loads(received_data)
            KEY_URL = received_data['value']
            print("Received key:")
    except:
        print("No key was transported. Trying default key:")
        KEY_URL = DEFAULT_KEY_URL
    
    print(KEY_URL)
   

    # Retrieve first name
    retrieve_data("n-fN", "first name", "required", KEY_URL, rp, challenge, allow_list, ident_ext, pin, client, use_nfc)
    
    # Retrieve last name
    retrieve_data("n-gN", "given name", "required", KEY_URL, rp, challenge, allow_list, ident_ext, pin, client, use_nfc)
    
    # Retrieve birthdate
    retrieve_data("bD", "birthdate", "required", KEY_URL, rp, challenge, allow_list, ident_ext, pin, client, use_nfc)

if __name__ == "__main__":
    main()