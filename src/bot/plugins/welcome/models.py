from pydantic import BaseModel


class WelcomeConfig(BaseModel):
    enabled: bool = True
    welcome_channel_id: str | None = None
    welcome_message: str = ""
    embed_title: str = "Bienvenid@ {user_name} a Korosoft Community"
    embed_color: int = 2326507
    welcome_image_url: str = ""
    dm_enabled: bool = False
    delete_previous: bool = False
