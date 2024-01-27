from collections import namedtuple
from datetime import date, timedelta
import re
import requests
from requests.exceptions import HTTPError


ApititURLs = namedtuple("ApititURLs", ["homepage", "tla", "kasvc"])

ApiCredentials = namedtuple(
    "ApiCredentials", ["client_id", "reg_key", "header", "user", "password"]
)
ApiCredentials.client_id.__doc__ = "Client ID of card service app."
ApiCredentials.reg_key.__doc__ = "Reg key of card service app."
ApiCredentials.header.__doc__ = (
    "Base64 encoded credentials to put in basic auth header."
)
ApiCredentials.user.__doc__ = (
    "User to authenticate the application (not a personal card number)."
)
ApiCredentials.password.__doc__ = (
    "Password to authenticate the application (not a personal user password)."
)


class Apitit:
    """Class to access the online canteen card service."""

    # Base URLs following the same scheme (API urls can be generated)
    BASE_URLS = {
        "Aachen": "https://kartenservice.stw.rwth-aachen.de/",
        "Augsburg": "https://kartenservice.studentenwerk-augsburg.de/",
        "Dresden": "https://kartenservice.studentenwerk-dresden.de/",
        "Freiberg": "https://kartenservice.studentenwerk-freiberg.de/",
        "Freiburg": "https://www.swfr.de/",
        "Paderborn": "https://kartenservice.studentenwerk-pb.de/",
        "Stuttgart": "https://cardservice-sws.cpwas.de/",
    }
    # Special cases differing from scheme, hardcode API urls
    SPECIAL_URLS = {
        "Leipzig": ApititURLs(
            # homepage is at top level
            homepage="https://kartenservice.studentenwerk-leipzig.de/",
            tla="https://kartenservice.studentenwerk-leipzig.de/TL1/TLA",
            kasvc="https://kartenservice.studentenwerk-leipzig.de/TL1/TLM/KASVC",
        ),
        "Mannheim": ApititURLs(
            # homepage has additional path component
            homepage="https://app.stw-ma.de/nkp/KartenService",
            tla="https://app.stw-ma.de/TL1/TLA",
            kasvc="https://app.stw-ma.de/TL1/TLM/KASVC",
        ),
    }

    def __init__(
        self, location, card_number=None, user_password=None, api_credentials=None
    ):
        """Initialise Apitit.

        Args:
            location (str): Location of "Studierendenwerk"
            card_number: Number of payment card. If None, methods requiring
                login won't work.
            user_password: Password belonging to payment card. If None,
                methods requiring login won't work.
            api_credentials (ApiCredentials): Credentials to access the API
                (not personal ones). If None, Apitit will obtain them
                automatically. However, supplying them will reduce overhead.
                See get_api_credentials to get them.
        """
        self.card_number = card_number
        self.user_password = user_password
        self.location = location
        if location in self.BASE_URLS:
            base_url = self.BASE_URLS[location]
            self.urls = ApititURLs(
                homepage=f"{base_url}/KartenService",
                tla=f"{base_url}TL1/TLA",
                kasvc=f"{base_url}TL1/TLM/KASVC",
            )
        elif location in self.SPECIAL_URLS:
            self.urls = self.SPECIAL_URLS[location]
        else:
            raise ValueError(
                'Sorry, given location "{location}" is currently not supported.'
            )
        if not api_credentials:
            api_credentials = self.get_api_credentials()
        self.api_credentials = api_credentials

        # Populated on login
        self.transaction_retention_days = None
        self._auth_token = None

    @staticmethod
    def raise_for_status_with_content(response):
        """Raise Exception including content.

        The server just returns 500 (or 599 for Augsburg and Dresden) with
        details in the request's content. This method extends the exception
        message.
        """
        try:
            response.raise_for_status()
        except HTTPError as e:
            msg = str(e.args[0]) + " with content: " + response.text
            raise HTTPError(msg, response=response)

    @property
    def auth_token(self):
        """Auth token used to authenticate a card number."""
        if not self._auth_token:
            self.login()
        return self._auth_token

    def get_api_credentials(self):
        """Get API credentials by extracting them from the JavaScript source.

        Missing credentials are automatically added to self.api_credentials.
        Existing values are not overwritten.

        Returns:
            A dict with the API credentials.
        """
        # Download JavaScript code
        js_file_url = f"{self.urls.homepage}/scripts/dataprovider.js"
        r = requests.get(js_file_url)
        r.raise_for_status()
        js_src = r.text

        # Regular expressions for credentials
        re_cl_id = re.compile(r"authClientId:\s*([0-9]+),")
        re_reg_key = re.compile(r"authRegKey:\s*\"([a-zA-Z0-9]+)\"")
        re_header = re.compile(r"authHeader:\s*\"(Basic\s[a-zA-Z0-9=]+)\"")
        re_user = re.compile(r"authUsername:\s*\"([a-zA-Z0-9]+)\"")
        re_pw = re.compile(r"authPassword:\s*\"([a-zA-Z0-9]+)\"")

        # Extract credentials
        cl_id = re_cl_id.search(js_src).group(1)
        reg_key = re_reg_key.search(js_src).group(1)
        header = re_header.search(js_src).group(1)
        user = re_user.search(js_src).group(1)
        pw = re_pw.search(js_src).group(1)

        api_credentials = ApiCredentials(
            client_id=cl_id,
            reg_key=reg_key,
            header=header,
            user=user,
            password=pw,
        )

        return api_credentials

    def register_client(self):
        """Register a client.

        It is unclear what this function is needed for. The JavaScript app
        does this before login, but it is possible to login directly without
        registering a client.

        Note that this function needs no login.
        """
        url = f"{self.urls.tla}/ClientReg"
        params = {
            "ClientID": self.api_credentials.client_id,
            "RegKey": self.api_credentials.reg_key,
            "format": "JSON",
            "datenformat": "JSON",
        }
        r = requests.post(
            url,
            params=params,
            auth=(self.api_credentials.user, self.api_credentials.password),
        )
        self.raise_for_status_with_content(r)

    def get_texts(self):
        """Get verbose texts used throughout the JavaScript App.

        Note that this function needs no login.

        Returns:
            List with dicts, each with key "id" and "text".
        """
        url = f"{self.urls.kasvc}/TEXTRES"
        params = {
            "LangId": "de",
            "format": "JSON",
        }
        r = requests.get(
            url,
            params=params,
            auth=(self.api_credentials.user, self.api_credentials.password),
        )
        self.raise_for_status_with_content(r)
        return r.json()

    def login(self):
        """Login with self.card_number and self.user_password.

        Sets self._auth_token and self.transaction_retention_days. It is not
        necessary to call this function, login is performed automatically when
        an auth_token is needed.

        Returns:
            Dict with data returned by API.
        """
        if not self.card_number:
            raise ValueError("Please set self.card_number before logging in.")
        if not self.user_password:
            raise ValueError("Please set self.user_password before logging in.")
        login_url = f"{self.urls.kasvc}/LOGIN"
        params = {
            "karteNr": self.card_number,
            "format": "JSON",
            "datenformat": "JSON",
        }
        payload = {
            "BenutzerID": self.card_number,
            "Passwort": self.user_password,
        }
        r = requests.post(
            login_url,
            json=payload,
            params=params,
            auth=(self.api_credentials.user, self.api_credentials.password),
        )
        self.raise_for_status_with_content(r)
        ret_dict = r.json()[0]
        self.transaction_retention_days = ret_dict["lTransTage"]
        self._auth_token = ret_dict["authToken"]
        return ret_dict

    def get_card_info(self):
        """Get card info.

        Returns:
            A dict containing card info.
        """
        url = f"{self.urls.kasvc}/KARTE"
        params = {
            "format": "JSON",
            "authToken": self.auth_token,
            "karteNr": self.card_number,
        }
        r = requests.get(
            url,
            params=params,
            auth=(self.api_credentials.user, self.api_credentials.password),
        )
        self.raise_for_status_with_content(r)
        return r.json()[0]

    def get_transactions(self, from_date=None, to_date=None):
        """Get transactions in the given timeframe.

        Args:
            from_date (datetime.date): Date from which transactions should be
                shown. Defaults to earliest date with data available.
            to_date (datetime.date): Date to which transactions should be
                shown. Defaults to today.

        Returns:
            List with dicts, each containing a single transaction.
        """
        if not to_date:
            to_date = date.today()
        if not from_date:
            from_date = to_date - timedelta(days=self.transaction_retention_days - 1)
        from_date_str = from_date.strftime("%d.%m.%Y")
        to_date_str = to_date.strftime("%d.%m.%Y")

        url = f"{self.urls.kasvc}/TRANS"
        params = {
            "format": "JSON",
            "authToken": self.auth_token,
            "karteNr": self.card_number,
            "datumVon": from_date_str,
            "datumBis": to_date_str,
        }
        r = requests.get(
            url,
            params=params,
            auth=(self.api_credentials.user, self.api_credentials.password),
        )
        self.raise_for_status_with_content(r)
        return r.json()

    def get_transaction_positions(self, from_date=None, to_date=None):
        """Get transaction positions in the given timeframe.

        Transaction positions are the individual positions of transactions.
        Positions can be mapped to transactions via the dict entry
        "transFullId".

        Args:
            from_date (datetime.date): Date from which transactions should be
                shown. Defaults to earliest date with data available.
            to_date (datetime.date): Date to which transactions should be
                shown. Defaults to today.

        Returns:
            List with dicts, each containing a single transaction position.
        """
        if not to_date:
            to_date = date.today()
        if not from_date:
            from_date = to_date - timedelta(days=self.transaction_retention_days - 1)
        from_date_str = from_date.strftime("%d.%m.%Y")
        to_date_str = to_date.strftime("%d.%m.%Y")

        url = f"{self.urls.kasvc}/TRANSPOS"
        params = {
            "format": "JSON",
            "authToken": self.auth_token,
            "karteNr": self.card_number,
            "datumVon": from_date_str,
            "datumBis": to_date_str,
        }
        r = requests.get(
            url,
            params=params,
            auth=(self.api_credentials.user, self.api_credentials.password),
        )
        self.raise_for_status_with_content(r)
        return r.json()
