# -*- coding: utf-8 -*-
import base64
import datetime
import json
from dotenv import load_dotenv
from jinja2 import Environment, FileSystemLoader
import matplotlib.colors as mcolors
import os

import pytz
import requests

load_dotenv()

# Constants for the progress bar
MAX_BAR_LENGTH = 40
BAR_CHAR = '█'
EMPTY_BAR_CHAR = '-'


def hex_to_rgb(hex_color):
    # Helper function to convert hex to RGB
    return tuple(int(hex_color[i:i+2], 16) / 255.0 for i in (1, 3, 5))


def shift_hue(obj, hue_shift):
    # Shift hue to determine rainbow start
    hue = mcolors.rgb_to_hsv(hex_to_rgb(obj['color']))[0] + hue_shift
    if hue > 1:
        hue -= 1.0
    return hue


def calc_darkness_bias(obj, threshold):
    # Threshold 1: No bias
    brightness = mcolors.rgb_to_hsv(hex_to_rgb(obj['color']))[2]
    if brightness < threshold:
        return 2 - brightness
    else:
        return 0


def seconds_to_string(seconds):
    days = seconds // 86400
    remaining_seconds = seconds % 86400
    hours = remaining_seconds // 3600
    remaining_minutes = (remaining_seconds % 3600) // 60
    
    time_string = ""
    if days > 0:
        time_string += f"{days}:{hours:02}"
    else:
        time_string += f"{hours}"
    time_string += f":{remaining_minutes:02}"
    
    return time_string


resource_dir = os.path.join(os.path.dirname(
    os.path.abspath(__file__)), "resources")
env = Environment(loader=FileSystemLoader(resource_dir))

# Load template
template = env.get_template('README.md.jinja')

# Load metadata files
with open(os.path.join(resource_dir, "technologies.json")) as f:
    technologies = json.load(f)
with open(os.path.join(resource_dir, "projects.json")) as f:
    projects = json.load(f)
with open(os.path.join(resource_dir, "socials.json")) as f:
    socials = json.load(f)

# Sort to build rainbow
hue_shift = 0.37
darkness_bias = 0.2

technologies = sorted(
    technologies,
    key=lambda obj: shift_hue(obj, hue_shift) +
    calc_darkness_bias(obj, darkness_bias)
)

blog_entries = {}
try:
    response = requests.get(
        f"{os.getenv("GHOST_URL")}/ghost/api/content/posts/?key={os.getenv("GHOST_KEY")}")
    blog_entries = response.json()['posts'][:3]
except Exception as e:
    print(e)
    pass

waka_projects = ""
waka_langs = ""
try:
    waka_token = base64.b64encode(
        os.getenv("WAKAPI_KEY").encode("ascii")).decode("ascii")
    response = requests.get(
        f"{os.getenv("WAKAPI_URL")}/api/summary?interval=30_days",
        headers={'Authorization': f"Basic {waka_token}"}
    )
    waka_info = response.json()
    
    total_duration = sum(item["total"] for item in waka_info["machines"])
    
    project_list = waka_info["projects"][:5]
    lang_list = waka_info["languages"][:5]
        
    max_name_len = max(len(entry["key"]) for entry in project_list)
    max_lang_len = max(len(entry["key"]) for entry in lang_list)
    max_key_len = max(max_name_len, max_lang_len)
    
    max_proj_time_len = max(len(seconds_to_string(entry["total"])) for entry in project_list)
    max_lang_time_len = max(len(seconds_to_string(entry["total"])) for entry in lang_list)
    max_total_len = max(max_proj_time_len, max_lang_time_len)
    
    waka_projects += "```\n"
    for project in project_list:
        filled_length = int((project["total"] / total_duration) * MAX_BAR_LENGTH)
        progress_bar = BAR_CHAR * filled_length + EMPTY_BAR_CHAR * (MAX_BAR_LENGTH - filled_length)
        percentage_str = str(int((project["total"] / total_duration * 100))) + "%"
        
        waka_projects += f"{project['key']:<{max_key_len}}   "
        waka_projects += f"{seconds_to_string(project["total"]):>{max_total_len}}   "
        waka_projects += f"{progress_bar}   "
        waka_projects += f"{percentage_str:>3}\n"
    waka_projects += "```"
    
    waka_langs += "```\n"
    for lang in lang_list:
        filled_length = int((lang["total"] / total_duration) * MAX_BAR_LENGTH)
        progress_bar = BAR_CHAR * filled_length + EMPTY_BAR_CHAR * (MAX_BAR_LENGTH - filled_length)
        percentage_str = str(int((lang["total"] / total_duration * 100))) + "%"
        
        waka_langs += f"{lang['key']:<{max_key_len}}   "
        waka_langs += f"{seconds_to_string(lang["total"]):>{max_total_len}}   "
        waka_langs += f"{progress_bar}   "
        waka_langs += f"{percentage_str:>3}\n"
    waka_langs += "```"
except Exception as e:
    waka_projects = ""
    waka_langs = ""
    print(e)
    pass

duolingo_stats = {}
try:
    response = requests.get(os.getenv("DUOLINGO_URL"))
    duolingo_stats = response.json()
    
    for lang in duolingo_stats["lang_data"]:
        if duolingo_stats["lang_data"][lang]["learningLanguage"] == duolingo_stats["learning_language"]:
            current_lang = duolingo_stats["lang_data"][lang]["learningLanguageFull"]
    
    duolingo_stats["current_lang"] = current_lang
except Exception as e:
    print(e)
    pass

berlin_timezone = pytz.timezone('Europe/Berlin')
berlin_time = datetime.datetime.now(berlin_timezone)
last_update = berlin_time.strftime('%A, %e %B %H:%M %Z')

# Variables to pass to the template
data = {
    "technologies": technologies,
    "projects": projects,
    "blog_entries":  blog_entries,
    "waka_projects": waka_projects,
    "waka_langs": waka_langs,
    "duolingo_stats": duolingo_stats,
    "socials": socials,
    "last_update": last_update
}

# Render the template with data
output = template.render(data)

# Write the output to README.md
with open('README.md', 'w', encoding='utf-8') as f:
    f.write(output)

print("README.md generated successfully.")
