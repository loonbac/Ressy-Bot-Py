import os
import requests
from cryptography.fernet import Fernet

GAME_DATA = {
    "hk4e_global": {
        "game_name": "Genshin Impact",
        "act_id": "e202102251931481",
        "info_url": "https://sg-hk4e-api.hoyolab.com/event/sol/info",
        "reward_url": "https://sg-hk4e-api.hoyolab.com/event/sol/home",
        "sign_url": "https://sg-hk4e-api.hoyolab.com/event/sol/sign"
    }
}

class GameAccount:
    def __init__(self, game_biz, region_name, game_uid, level, nickname, region, **kwargs):
        self._game_biz = game_biz
        self._region_name = region_name.split(" ")[0]
        self._game_uid = game_uid
        self._level = level
        self._nickname = nickname
        self._region = region
        self.claimed_reward = None

    def get_game_biz(self):
        return self._game_biz

    def get_region_name(self):
        return self._region_name

    def get_game_uid(self):
        return self._game_uid

    def get_level(self):
        return self._level

    def get_nickname(self):
        return self._nickname

    def get_region(self):
        return self._region

    def get_claimed_reward(self):
        return self.claimed_reward

class ApiClient:
    def __init__(self, headers):
        self.session = requests.Session()
        self.headers = headers

    def _request(self, url):
        try:
            response = self.session.get(url, headers=self.headers)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            print(f"Request failed for {url}: {e}")
            return None

class HoyolabClient(ApiClient):
    def __init__(self, cookie):
        headers = {
            "Cookie": cookie,
            "User-Agent": os.environ.get("USER_AGENT", "Mozilla/5.0"),
        }
        super().__init__(headers)

    def get_game_accounts(self):
        url = "https://api-os-takumi.hoyolab.com/binding/api/getUserGameRolesByCookie"
        res = self._request(url)
        if res and "data" in res:
            return [GameAccount(**account) for account in res["data"]["list"]]
        return []

    def check_in(self, account):
        if account.get_game_biz() not in GAME_DATA:
            raise Exception("Juego no soportado")

        data = GAME_DATA[account.get_game_biz()]
        act_id = data["act_id"]

        info_res = self._request(f"{data['info_url']}?act_id={act_id}")
        rewards_res = self._request(f"{data['reward_url']}?act_id={act_id}")

        if info_res and rewards_res:
            if not info_res["data"]["is_sign"]:
                sign_res = self.session.post(f"{data['sign_url']}?act_id={act_id}", headers=self.headers)
                if sign_res.json().get("retcode") == 0:
                    reward = rewards_res["data"]["awards"][info_res["data"]["total_sign_day"]]
                    account.claimed_reward = reward
            else:
                account.claimed_reward = None

def decrypt_cookie(encrypted_cookie: str, key: str) -> str:
    fernet = Fernet(key)
    decrypted = fernet.decrypt(encrypted_cookie.encode()).decode()
    return decrypted

def encrypt_cookie(cookie: str, key: str) -> str:
    fernet = Fernet(key)
    encrypted = fernet.encrypt(cookie.encode()).decode()
    return encrypted

def get_encrypted_cookies():
    try:
        with open("cookies.txt", "r") as file:
            encrypted_cookies = file.read().strip()
            return encrypted_cookies.split('|') if encrypted_cookies else []
    except FileNotFoundError:
        return []
