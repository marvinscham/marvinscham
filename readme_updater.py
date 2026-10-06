# -*- coding: utf-8 -*-
import base64
import datetime
import html
import json
import math
import os

import matplotlib.colors as mcolors
import pytz
import requests
from dotenv import load_dotenv
from jinja2 import Environment, FileSystemLoader

load_dotenv()

def hex_to_rgb(hex_color):
    # Helper function to convert hex to RGB
    return tuple(int(hex_color[i : i + 2], 16) / 255.0 for i in (1, 3, 5))


def shift_hue(obj, hue_shift):
    # Shift hue to determine rainbow start
    hue = mcolors.rgb_to_hsv(hex_to_rgb(obj["color"]))[0] + hue_shift
    if hue > 1:
        hue -= 1.0
    return hue


def calc_darkness_bias(obj, threshold):
    # Threshold 1: No bias
    brightness = mcolors.rgb_to_hsv(hex_to_rgb(obj["color"]))[2]
    if brightness < threshold:
        return 2 - brightness
    else:
        return 0


def language_key(name):
    return "".join(character.lower() for character in name if character.isalnum())


def duration_string(seconds):
    hours, remaining_seconds = divmod(int(seconds), 3600)
    minutes = remaining_seconds // 60
    return f"{hours}h {minutes}m"


def bubble_chart(languages, language_colors):
    languages = [language for language in languages if language["total"] >= 10 * 60]
    if not languages:
        return ""

    languages.sort(key=lambda language: language["total"], reverse=True)
    largest_total = languages[0]["total"]
    for index, language in enumerate(languages):
        language["radius"] = max(24, 96 * math.sqrt(language["total"] / largest_total))
        language["color"] = language_colors.get(language_key(language["key"]), "#6b7280")

        angle = index * 2.399963
        distance = 1.5 * math.sqrt(index) * language["radius"]
        language["x"] = distance * math.cos(angle)
        language["y"] = distance * math.sin(angle)

    # deterministic force layout
    for _ in range(180):
        for language in languages:
            language["x"] *= 0.985
            language["y"] *= 0.985
        for index, first in enumerate(languages):
            for second in languages[index + 1 :]:
                dx = second["x"] - first["x"]
                dy = second["y"] - first["y"]
                distance = math.hypot(dx, dy) or 0.001
                minimum = first["radius"] + second["radius"] + 8
                if distance < minimum:
                    push = (minimum - distance) / distance / 2
                    first["x"] -= dx * push
                    first["y"] -= dy * push
                    second["x"] += dx * push
                    second["y"] += dy * push

    min_x = min(language["x"] - language["radius"] for language in languages)
    max_x = max(language["x"] + language["radius"] for language in languages)
    min_y = min(language["y"] - language["radius"] for language in languages)
    max_y = max(language["y"] + language["radius"] for language in languages)
    center_x = (min_x + max_x) / 2
    center_y = (min_y + max_y) / 2
    size = max(720, math.ceil(2 * max(max_x - center_x, max_y - center_y) + 24))
    for language in languages:
        language["x"] += size / 2 - center_x
        language["y"] += size / 2 - center_y

    bubbles = []
    for language in languages:
        radius = language["radius"]
        text_color = "#ffffff" if mcolors.rgb_to_hsv(hex_to_rgb(language["color"]))[2] < 0.65 else "#111827"
        name = html.escape(language["key"])
        time = html.escape(duration_string(language["total"]))
        color = html.escape(language["color"], quote=True)
        name_size = min(14, max(8, 1.8 * radius / max(len(language["key"]), 1)))
        bubbles.append(
            f'<g><title>{name}: {time}</title>'
            f'<circle cx="{language["x"]:.1f}" cy="{language["y"]:.1f}" r="{radius:.1f}" fill="{color}"/>'
            f'<text x="{language["x"]:.1f}" y="{language["y"] - 4:.1f}" text-anchor="middle" '
            f'font-family="sans-serif" font-size="{name_size:.1f}" font-weight="600" fill="{text_color}">{name}</text>'
            f'<text x="{language["x"]:.1f}" y="{language["y"] + 16:.1f}" text-anchor="middle" '
            f'font-family="sans-serif" font-size="12" fill="{text_color}">{time}</text></g>'
        )

    return f'<svg xmlns="http://www.w3.org/2000/svg" width="100%" viewBox="0 0 {size} {size}">{"".join(bubbles)}</svg>'


resource_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "resources")
env = Environment(loader=FileSystemLoader(resource_dir))

# Load template
template = env.get_template("README.md.jinja")

# Load metadata files
with open(os.path.join(resource_dir, "technologies.jsonl")) as f:
    technologies = [json.loads(line) for line in f if line.strip()]
with open(os.path.join(resource_dir, "projects.json")) as f:
    projects = json.load(f)
with open(os.path.join(resource_dir, "socials.json")) as f:
    socials = json.load(f)
with open(os.path.join(resource_dir, "language_colors.json")) as f:
    language_colors = {
        language_key(name): details["color"]
        for name, details in json.load(f).items()
        if details.get("color")
    }
for technology in technologies:
    language_colors.setdefault(language_key(technology["name"]), technology["color"])

# Sort to build rainbow
hue_shift = 0.8
darkness_bias = 0.2

technologies = sorted(
    technologies,
    key=lambda obj: shift_hue(obj, hue_shift) + calc_darkness_bias(obj, darkness_bias),
)

blog_entries = {}
try:
    ghost_base_url = os.getenv("GHOST_URL").rstrip("/")
    ghost_api_key = os.getenv("GHOST_API_KEY")
    response = requests.get(
        f"{ghost_base_url}/ghost/api/content/posts/?key={ghost_api_key}"
    )
    blog_entries = response.json()["posts"][:3]
except Exception as e:
    print(e)
    pass

waka_chart = ""
try:
    waka_token = base64.b64encode(os.getenv("WAKAPI_KEY").encode("ascii")).decode(
        "ascii"
    )
    wakapi_base_url = os.getenv("WAKAPI_URL").rstrip("/")
    response = requests.get(
        f"{wakapi_base_url}/api/summary?interval=30_days",
        headers={"Authorization": f"Basic {waka_token}"},
    )
    waka_info = response.json()

    waka_chart = bubble_chart(waka_info["languages"], language_colors)
    if waka_chart:
        with open(os.path.join(resource_dir, "wakapi-chart.svg"), "w", encoding="utf-8") as f:
            f.write(waka_chart)
except Exception as e:
    waka_chart = ""
    print(e)
    pass

duolingo_stats = {}
try:
    response = requests.get(os.getenv("DUOLINGO_URL"))
    duolingo_stats = response.json()

    for lang in duolingo_stats["lang_data"]:
        if (
            duolingo_stats["lang_data"][lang]["learningLanguage"]
            == duolingo_stats["learning_language"]
        ):
            current_lang = duolingo_stats["lang_data"][lang]["learningLanguageFull"]

    duolingo_stats["current_lang"] = current_lang
except Exception as e:
    print(e)
    pass

berlin_timezone = pytz.timezone("Europe/Berlin")
berlin_time = datetime.datetime.now(berlin_timezone)
last_update = berlin_time.strftime("%A, %e %B %H:%M %Z")

# Variables to pass to the template
data = {
    "technologies": technologies,
    "projects": projects,
    "blog_entries": blog_entries,
    "waka_chart": waka_chart,
    "duolingo_stats": duolingo_stats,
    "socials": socials,
    "last_update": last_update,
}

# Render the template with data
output = template.render(data)

# Write the output to README.md
with open("README.md", "w", encoding="utf-8") as f:
    f.write(output)

print("README.md generated successfully.")
