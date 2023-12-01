import re
import sys
from gpt4all import GPT4All
import json
import asyncio
import time as pytime
from datetime import datetime
from time import sleep

from requests import Response

from concurrent.futures import ThreadPoolExecutor

from utils import settings
from utils.console import print_substep
from cleantext import clean

if sys.version_info[0] >= 3:
    from datetime import timezone
    
# Initialize the GPT4All model
gpt_model = None

def load_text_replacements():
    text_replacements = {}
    # Load background videos
    with open("./utils/text_replacements.json") as json_file:
        text_replacements = json.load(json_file)
    del text_replacements["__comment"]
    return text_replacements

async def perform_text_replacements(text):
    updated_text = text
    
    for replacement in text_replacements['text-and-audio']:
        compiled = re.compile(r'\b' + re.escape(replacement[0]) + r'\b', re.IGNORECASE)  # Added word boundaries
        updated_text = compiled.sub(replacement[1], updated_text)
    for replacement in text_replacements['audio-only']:
        compiled = re.compile(r'\b' + re.escape(replacement[0]) + r'\b', re.IGNORECASE)  # Added word boundaries
        updated_text = compiled.sub(replacement[1], updated_text)
        
    updated_text = await ai_grammar_smooth(updated_text)
        
    return updated_text


async def ai_grammar_smooth(text):
    global gpt_model
    
    if not settings.config["ai"]["ai_grammar_fix"]:
        return text
    elif gpt_model == None:
        gpt_model = GPT4All(settings.config["ai"]["ai_model"])
        
    print("Before AI Enhancement: " + text + "\n")
    
    prompt = "Your task is to refine the following text for use in a Text-to-Speech program. This text comes from social media posts and comments and often contains informal language and expressions. Your goal is to correct any grammatical mistakes and improve the natural flow of the language, making it clearer and more suitable for TTS conversion. It's crucial that you do not change the original meaning or add any new content. Focus solely on enhancing the grammar and readability. Here's the text for refinement:"


    
    def synchronous_gpt4all_call(prompt):
        
        print("Prompt to AI: " + prompt + "\n")
        
        # This is the synchronous function call to GPT4All
        return gpt_model.generate(prompt=prompt, max_tokens=150)

    async def async_gpt4all_call(prompt):
        # This function makes the synchronous GPT4All call asynchronously
        loop = asyncio.get_event_loop()
        with ThreadPoolExecutor() as executor:
            result = await loop.run_in_executor(executor, synchronous_gpt4all_call, prompt)
            
        print("After AI Enhancement: " + result + "\n")
        
        return result
    
    result = await async_gpt4all_call((prompt + '"' + text + '"'))
    
    
    return result


async def check_ratelimit(response):
    """
    Checks if the response is a rate limit response.
    If it is, it sleeps for the time specified in the response.
    """
    if response.status == 429:
        try:
            time = int(response.headers["X-RateLimit-Reset"])
            print(f"Rate limit hit. Sleeping for {time - int(pytime.time())} seconds.")
            await asyncio.sleep(max(0, time - pytime.time()))
            return True
        except KeyError:
            return False
    return False



def sleep_until(time) -> None:
    """
    Pause your program until a specific end time.
    'time' is either a valid datetime object or unix timestamp in seconds (i.e. seconds since Unix epoch)
    """
    end = time

    # Convert datetime to unix timestamp and adjust for locality
    if isinstance(time, datetime):
        # If we're on Python 3 and the user specified a timezone, convert to UTC and get the timestamp.
        if sys.version_info[0] >= 3 and time.tzinfo:
            end = time.astimezone(timezone.utc).timestamp()
        else:
            zoneDiff = pytime.time() - (datetime.now() - datetime(1970, 1, 1)).total_seconds()
            end = (time - datetime(1970, 1, 1)).total_seconds() + zoneDiff

    # Type check
    if not isinstance(end, (int, float)):
        raise Exception("The time parameter is not a number or datetime object")

    # Now we wait
    while True:
        now = pytime.time()
        diff = end - now

        #
        # Time is up!
        #
        if diff <= 0:
            break
        else:
            # 'logarithmic' sleeping to minimize loop iterations
            sleep(diff / 2)


async def sanitize_text(text: str) -> str:
    """
    Sanitizes the text for tts.
        What gets removed:
     - following characters`^_~@!&;#:-%“”‘"%*/{}[]()\|<>?=+`
     - any http or https links

    Args:
        text (str): Text to be sanitized

    Returns:
        str: Sanitized text
    """

    # remove any urls from the text
    regex_urls = r"((http|https)\:\/\/)?[a-zA-Z0-9\.\/\?\:@\-_=#]+\.([a-zA-Z]){2,6}([a-zA-Z0-9\.\&\/\?\:@\-_=#])*"
    result = re.sub(regex_urls, " ", text)

    # note: not removing apostrophes
    regex_expr = r"\s['|’]|['|’]\s|[\^_~@!&;#:\-%—“”‘\"%\*/{}\[\]\(\)\\|<>=+]"
    result = re.sub(regex_expr, " ", result)
    result = result.replace("+", "plus").replace("&", "and")

    # emoji removal if the setting is enabled
    if settings.config["settings"]["tts"]["no_emojis"]:
        result = clean(result, no_emoji=True)

    # Perform text replacements asynchronously and wait for the result
    result = await perform_text_replacements(result)

    # remove extra whitespace
    return " ".join(result.split())

text_replacements = load_text_replacements()
