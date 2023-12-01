import random
import aiohttp
import asyncio
from utils import settings
from utils.voice import check_ratelimit

voices = [
    "Brian", "Emma", "Russell", "Joey", "Matthew", "Joanna", "Kimberly", "Amy", "Geraint",
    "Nicole", "Justin", "Ivy", "Kendra", "Salli", "Raveena",
]


# valid voices https://lazypy.ro/tts/


class StreamlabsPolly:
    def __init__(self):
        self.url = "https://streamlabs.com/polly/speak"
        self.max_chars = 550
        self.voices = voices

    async def run(self, text, filepath, random_voice: bool = False):
        voice = self.randomvoice() if random_voice else str(settings.config["settings"]["tts"]["streamlabs_polly_voice"]).capitalize()
        body = {"voice": voice, "text": text, "service": "polly"}

        async with aiohttp.ClientSession() as session:
            response = await session.post(self.url, data=body)

            if not check_ratelimit(response):
                return await self.run(text, filepath, random_voice)

            try:
                json_response = await response.json()
                voice_data = await session.get(json_response["speak_url"])
                with open(filepath, "wb") as f:
                    f.write(await voice_data.read())
            except (KeyError, aiohttp.ContentTypeError):
                # Handle JSONDecodeError and other errors
                print("Error occurred calling Streamlabs Polly")

    def randomvoice(self):
        return random.choice(self.voices)
