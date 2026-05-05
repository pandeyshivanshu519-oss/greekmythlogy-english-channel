import os
import json
import time
from dotenv import load_dotenv
from google import genai

load_dotenv()

client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

MOVIES_FILE            = "movies_list.json"
STORY_STATE_FILE       = "story_state.json"
PARTS_PER_MOVIE        = 100
AUTO_EXPAND_THRESHOLD  = 5

# ── Disney Pixar style suffix — added to EVERY image prompt ──────────
PIXAR_STYLE = (
    "Disney Pixar 3D animated style, "
    "epic mythological lighting, "
    "big expressive eyes, "
    "smooth rounded textures, "
    "vibrant rich colors, "
    "Pixar movie render quality, "
    "cinematic depth of field, "
    "ultra detailed, 8k"
)




class ContentBrain:

    def __init__(self):
        self.movies_data = self._load_movies()
        self.state       = self._load_state()

    # ─────────────────────────────────────────────────────────────────
    # MOVIES LIST
    # ─────────────────────────────────────────────────────────────────

    def _load_movies(self):
        if os.path.exists(MOVIES_FILE):
            with open(MOVIES_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        return {"movies": [], "parts_per_movie": PARTS_PER_MOVIE,
                "current_movie_index": 0, "auto_expand": True}

    def _save_movies(self):
        with open(MOVIES_FILE, "w", encoding="utf-8") as f:
            json.dump(self.movies_data, f, indent=2, ensure_ascii=False)

    def _remaining_movies(self):
        return len(self.movies_data["movies"]) - self.movies_data.get("current_movie_index", 0)

    def _auto_expand_movies(self):
        if not self.movies_data.get("auto_expand", True):
            return
        existing     = self.movies_data["movies"]
        completed    = self.state.get("completed_movies", [])
        done_str     = ", ".join((completed or existing)[-10:])
        existing_str = ", ".join(existing)
        print(f"🤖 Auto-expanding movie list ({len(existing)} currently)...")

        prompt = f"""
You are a content planner for an English mythology YouTube Shorts channel targeting US and global family audiences.
Already covered: {done_str}
Full existing list (NO repeats allowed): {existing_str}

Generate exactly 30 NEW mythology story arcs. PRIORITY ORDER:

TIER 1 — at least 12 from these (US school curriculum + Marvel fanbase):
- Greek mythology (Zeus, heroes, monsters, Olympus, Troy, Odyssey)
- Norse mythology (Thor, Loki, Odin, Ragnarok, Vikings, Valkyries)
- Roman mythology (Jupiter, Mars, Aeneas, founding of Rome)

TIER 2 — at least 10 from these (universally fascinating):
- Egyptian mythology (Ra, Osiris, Horus, Pharaohs, pyramids)
- Arthurian legends (King Arthur, Merlin, knights, Camelot)
- Celtic/Irish mythology (Cuchulainn, Dagda, Morrigan)

TIER 3 — at least 8 from these (exotic appeal, growing global audience):
- Hindu mythology (Rama, Krishna, Shiva, Hanuman, Mahabharat)
- Japanese mythology (Amaterasu, Susanoo)
- Chinese mythology (Sun Wukong, Nu Wa)
- Aztec/Mayan, African, Mesopotamian mythology

Rules:
- Title must feel EPIC and clickable — "[Name] — [dramatic subtitle]"
- Every story needs clear hero, villain, emotional journey
- Family-friendly — dramatic but not gory
- NO repeats from existing list

Return ONLY a JSON array of 30 strings: ["Title 1", ..., "Title 30"]
"""
        for model_name in ["gemini-2.5-flash", "gemini-2.5-flash-lite" , "gemini-1.5-flash" , "gemini-1.5-flash-8b" , "gemini-1.5-pro" , ]:
            try:
                resp     = client.models.generate_content(
                    model=model_name, contents=prompt,
                    config={"response_mime_type": "application/json"}
                )
                clean    = resp.text.strip().replace("```json","").replace("```","").strip()
                new_list = json.loads(clean)
                if not isinstance(new_list, list):
                    continue
                existing_lower = [m.lower().strip() for m in existing]
                added = []
                for title in new_list:
                    if isinstance(title, str) and title.lower().strip() not in existing_lower:
                        self.movies_data["movies"].append(title)
                        added.append(title)
                self._save_movies()
                print(f"   ✅ Added {len(added)} new movies")
                for m in added:
                    print(f"      • {m}")
                return
            except Exception as e:
                print(f"   ⚠️ Expand failed ({model_name}): {e}")

    # ─────────────────────────────────────────────────────────────────
    # STORY STATE
    # ─────────────────────────────────────────────────────────────────

    def _load_state(self):
        if os.path.exists(STORY_STATE_FILE):
            with open(STORY_STATE_FILE, "r", encoding="utf-8") as f:
                state = json.load(f)
            # Normalize character_profiles keys on load — fixes NED STARK / NED_STARK duplicates
            if "character_profiles" in state:
                raw = state["character_profiles"]
                clean = {}
                for k, v in raw.items():
                    canonical = k.upper().strip().replace("_", " ")
                    if canonical not in clean:
                        clean[canonical] = v
                    else:
                        if not clean[canonical].get("look") and v.get("look"):
                            clean[canonical]["look"] = v["look"]
                state["character_profiles"] = clean
            return state
        first = self.movies_data["movies"][0] if self.movies_data["movies"] else "Harry Potter and the Sorcerer's Stone"
        return {
            "current_movie": first, "current_movie_index": 0,
            "current_part": 0, "total_parts": PARTS_PER_MOVIE,
            "story_so_far": "", "last_scene_ending": "",
            "characters_introduced": [], "key_events_covered": [],
            "completed_movies": [], "character_profiles": {}
        }

    def _save_state(self):
        with open(STORY_STATE_FILE, "w", encoding="utf-8") as f:
            json.dump(self.state, f, indent=2, ensure_ascii=False)

    def _advance_to_next_movie(self):
        completed = self.state.get("completed_movies", [])
        if self.state["current_movie"] not in completed:
            completed.append(self.state["current_movie"])
        self.state["completed_movies"] = completed
        print(f"🎉 '{self.state['current_movie']}' complete!")

        if self._remaining_movies() <= AUTO_EXPAND_THRESHOLD:
            self._auto_expand_movies()

        next_idx = self.state["current_movie_index"] + 1
        movies   = self.movies_data["movies"]
        if next_idx >= len(movies):
            print("🔁 All movies done — restarting!")
            next_idx = 0
            self.state["completed_movies"] = []

        next_movie = movies[next_idx]
        print(f"🎬 Next movie: '{next_movie}'")
        self.state.update({
            "current_movie": next_movie, "current_movie_index": next_idx,
            "current_part": 0, "story_so_far": "", "last_scene_ending": "",
            "characters_introduced": [], "key_events_covered": [],
            "character_profiles": {},   # fresh slate for new movie
        })
        self.movies_data["current_movie_index"] = next_idx
        self._save_state()
        self._save_movies()

    # ─────────────────────────────────────────────────────────────────
    # SCRIPT GENERATION
    # ─────────────────────────────────────────────────────────────────

    def generate_script(self):
        if self._remaining_movies() <= AUTO_EXPAND_THRESHOLD:
            self._auto_expand_movies()
        if self.state["current_part"] >= PARTS_PER_MOVIE:
            self._advance_to_next_movie()

        self.state["current_part"] += 1
        part_number  = self.state["current_part"]
        movie_name   = self.state["current_movie"]
        story_so_far = self.state.get("story_so_far", "")
        last_ending  = self.state.get("last_scene_ending", "")
        events       = self.state.get("key_events_covered", [])
        progress_pct = (part_number / PARTS_PER_MOVIE) * 100

        # character_profiles: {"HARRY": {"look": "...", "voice": "HERO"}, ...}
        char_profiles = self.state.get("character_profiles", {})
        events_str    = ", ".join(events[-8:]) if events else "None yet"

        # Build character reference block from saved profiles
        if char_profiles:
            char_ref = "\n".join(
                f"  {name}: gender={data.get('gender','male')} | voice={data.get('voice','HERO')} | look={data.get('look','?')[:80]}"
                for name, data in list(char_profiles.items())[-8:]
            )
        else:
            char_ref = "None yet — define all characters fresh this part"

        story_context = ""
        if story_so_far:
            story_context = f"\nSTORY SO FAR:\n{story_so_far[-600:]}\n\nLAST SCENE:\n{last_ending}\n"

        if part_number == 1:
            part_instr = "PART 1 — Introduction. Paint the world vividly, introduce the protagonist with power. End with a dramatic hook that makes viewers NEED to watch Part 2."
        elif part_number == PARTS_PER_MOVIE:
            movies    = self.movies_data["movies"]
            nxt       = movies[(self.state["current_movie_index"] + 1) % len(movies)]
            part_instr = f"PART {PARTS_PER_MOVIE} — GRAND FINALE. Resolve every thread. The final NARRATOR line MUST say: \"And so ends the legend of {movie_name}... Next, we uncover the untold story of {nxt} — subscribe so you don't miss it!\""
        else:
            part_instr = f"PART {part_number}/{PARTS_PER_MOVIE} ({progress_pct:.0f}% complete). Continue EXACTLY from last scene. Build tension. End on a gripping cliffhanger — viewers must come back."

        prompt = f"""
You are a master mythology storyteller creating a {PARTS_PER_MOVIE}-part English YouTube Shorts series.
Your tone: epic campfire narrator — dramatic, vivid, emotional. Like a movie trailer voice-over meets a bedtime story for all ages.

STORY: {movie_name}
PART: {part_number}/{PARTS_PER_MOVIE}
EVENTS SO FAR: {events_str}
{story_context}
CHARACTERS SO FAR:
{char_ref}

INSTRUCTION: {part_instr}

━━━ CHARACTERS ━━━

Define ALL characters from your knowledge of "{movie_name}".
For EVERY character appearing in this part, return in "character_profiles":

  "look"   → detailed visual description (hair, eyes, skin, clothing, weapon, expression)
  "gender" → "male" OR "female"  ← MANDATORY
  "voice"  → one of: HERO / VILLAIN / ELDER / CHILD / SIDEKICK / FEMALE

Voice guide:
  HERO     → brave protagonist, fast energetic confident speech
  VILLAIN  → antagonist, slow menacing cold voice
  ELDER    → wise god or elder, slow deep authoritative
  CHILD    → young character, fast excited high
  SIDEKICK → funny/loyal companion, cheerful warm
  FEMALE   → female character (use if no stronger role fits)

gender controls which English voice actor is used:
  male   → deep English male voice
  female → warm English female voice

Keep character "look" EXACTLY the same across all parts — visual consistency is critical.

━━━ SCRIPT — ENGLISH ONLY ━━━

Write in PURE ENGLISH. No Hindi. No Hinglish.
Mix NARRATOR lines + CHARACTER dialogue lines.

Rules:
- [NARRATOR] = epic storyteller narration (third person, dramatic, vivid imagery)
- [CHARACTER NAME] = ALL CAPS actual name, e.g. [RAMA], [ZEUS], [ACHILLES]
- 4-6 NARRATOR lines + 4-8 CHARACTER dialogue lines
- ~130 words total (50-60 seconds when read aloud)
- NARRATOR must be first AND last line always
- End on a gripping cliffhanger (except final part)
- Language: rich English — "The heavens trembled", "His eyes burned with fury"
- Dialogue should feel real — gods speak with power, heroes with heart, villains with cold menace

━━━ IMAGES ━━━

7 image_prompts — different dramatic shots from this scene.
Each prompt MUST end with: "{PIXAR_STYLE}"
Use character's exact "look" from character_profiles.

━━━ PEXELS MOOD CLIPS ━━━
2 pexels_moods — 3-4 word English search terms for atmospheric clips.
Examples: "temple fire dramatic", "ancient war battlefield", "ocean storm lightning"

━━━ RETURN ONLY THIS JSON ━━━
[
  {{
    "id": 1,
    "movie": "{movie_name}",
    "part_number": {part_number},
    "total_parts": {PARTS_PER_MOVIE},
    "title": "{movie_name} | Part {part_number} — [catchy dramatic English scene title]",
    "scene_title": "[3-5 word dramatic English scene name]",
    "character_profiles": {{
      "RAMA": {{
        "look": "tall noble young man, dark hair, sharp jawline, golden royal armor, radiant brown eyes, kind but determined expression, holding divine bow",
        "gender": "male",
        "voice": "HERO"
      }},
      "RAVANA": {{
        "look": "ten-headed demon king, towering muscular build, dark golden crown, fierce red eyes, black war armor with jewels, terrifying yet regal",
        "gender": "male",
        "voice": "VILLAIN"
      }},
      "SITA": {{
        "look": "beautiful divine woman, long black hair with flowers, golden silk saree, calm fearless eyes, gentle warm expression",
        "gender": "female",
        "voice": "FEMALE"
      }}
    }},
    "script_lines": [
      {{"tag": "NARRATOR", "text": "The golden city of Lanka blazed under a blood-red sky..."}},
      {{"tag": "RAMA",     "text": "I will burn every stone of Lanka before I let her suffer one more day!"}},
      {{"tag": "NARRATOR", "text": "Ravana laughed from his throne, ten crowns gleaming..."}},
      {{"tag": "RAVANA",   "text": "You dare challenge a god, mortal? Come then — meet your end."}},
      {{"tag": "NARRATOR", "text": "And with that, the greatest war in history... had begun."}}
    ],
    "hook_text": "Part {part_number}: [5 dramatic English words]",
    "image_prompts": [
      "[char look + action + setting + mood + {PIXAR_STYLE}]",
      "[shot 2]", "[shot 3]", "[shot 4]", "[shot 5]", "[shot 6]", "[shot 7]"
    ],
    "pexels_moods": ["ancient temple fire night", "war battlefield smoke"],
    "new_characters": ["names of NEW characters introduced in this part only"],
    "new_events": ["2-3 key plot points from this part"],
    "story_summary": "2-3 sentence English summary of story so far",
    "scene_ending": "Exact last moment of this part for Part {part_number + 1} continuity"
  }}
]

RULES:
- ALL text must be in English — narrator, dialogue, titles, everything
- gender is MANDATORY for every character
- scene_title must be dramatic English (not Hindi)
- character_profiles must include ALL characters who speak or appear
"""

        models = ["gemini-2.5-flash", "gemini-2.5-flash-lite", "gemini-3.1-flash"]

        for model_name in models:
            for attempt in range(3):
                try:
                    print(f"   🔄 {model_name} (attempt {attempt+1})")
                    response = client.models.generate_content(
                        model=model_name, contents=prompt,
                        config={"response_mime_type": "application/json"}
                    )
                    clean  = response.text.strip().replace("```json","").replace("```","").strip()
                    result = json.loads(clean)
                    if isinstance(result, dict):
                        result = [result]

                    scene = result[0]

                    # Validate image prompts have Pixar style
                    prompts_list = scene.get("image_prompts", [])
                    fixed = []
                    for p in prompts_list:
                        if "Pixar" not in p and "pixar" not in p:
                            p = p.rstrip(" ,") + f", {PIXAR_STYLE}"
                        fixed.append(p)
                    scene["image_prompts"] = fixed

                    # Validate / normalise script_lines
                    VOICE_TYPES = {"NARRATOR","HERO","VILLAIN","FEMALE","CHILD","ELDER","SIDEKICK"}

                    def _canonical(name):
                        return name.upper().strip().replace("_", " ")

                    # character_profiles from Gemini
                    raw_profiles   = scene.get("character_profiles", {})
                    saved_profiles = self.state.get("character_profiles", {})

                    for char_name, data in raw_profiles.items():
                        key = _canonical(char_name)   # normalize: "NED_STARK" == "NED STARK"
                        if not isinstance(data, dict):
                            continue
                        voice  = str(data.get("voice",  "HERO")).upper().strip()
                        gender = str(data.get("gender", "male")).lower().strip()
                        look   = str(data.get("look",   "")).strip()
                        if voice not in VOICE_TYPES:
                            voice = "HERO"
                        if gender not in ("male", "female"):
                            gender = "male"
                        if key not in saved_profiles:
                            saved_profiles[key] = {"look": look, "gender": gender, "voice": voice}
                        else:
                            if not saved_profiles[key].get("look"):
                                saved_profiles[key]["look"] = look
                            saved_profiles[key]["gender"] = gender
                            saved_profiles[key]["voice"]  = voice

                    self.state["character_profiles"] = saved_profiles
                    scene["character_profiles"] = saved_profiles

                    raw_lines   = scene.get("script_lines", [])
                    clean_lines = []
                    for ln in raw_lines:
                        if not isinstance(ln, dict):
                            continue
                        tag = _canonical(str(ln.get("tag", "NARRATOR")))
                        txt = str(ln.get("text", "")).strip()
                        if not txt:
                            continue
                        if tag == "NARRATOR":
                            voice_type = "NARRATOR"
                        elif tag in VOICE_TYPES:
                            voice_type = tag
                        else:
                            voice_type = saved_profiles.get(tag, {}).get("voice", "HERO")
                        clean_lines.append({
                            "tag":        tag,
                            "voice_type": voice_type,
                            "text":       txt,
                        })

                    # Fallback: old-style plain "text" field
                    if not clean_lines and scene.get("text"):
                        clean_lines = [{"tag": "NARRATOR", "voice_type": "NARRATOR", "text": scene["text"]}]
                    scene["script_lines"] = clean_lines
                    scene["text"] = " ".join(ln["text"] for ln in clean_lines)

                    result[0] = scene

                    tags_used = [(ln["tag"], ln["voice_type"]) for ln in clean_lines if ln["tag"] != "NARRATOR"]
                    print(f"   ✅ Part {part_number} | {len(fixed)} images | chars: {tags_used}")

                    # Update story state
                    for c in scene.get("new_characters", []):
                        c_upper = c.upper().strip()
                        if c_upper not in self.state.get("characters_introduced", []):
                            self.state.setdefault("characters_introduced", []).append(c_upper)
                    self.state["key_events_covered"].extend(scene.get("new_events", []))
                    self.state["key_events_covered"] = self.state["key_events_covered"][-30:]
                    if scene.get("story_summary"):
                        self.state["story_so_far"]      = scene["story_summary"]
                    if scene.get("scene_ending"):
                        self.state["last_scene_ending"] = scene["scene_ending"]
                    self._save_state()
                    return result

                except Exception as e:
                    err = str(e)
                    print(f"   ❌ {model_name}: {err[:150]}")
                    if "503" in err or "high demand" in err:
                        time.sleep(10)
                        continue
                    else:
                        break

        self.state["current_part"] -= 1
        self._save_state()
        print("❌ All models failed.")
        return None


if __name__ == "__main__":
    brain = ContentBrain()
    out   = brain.generate_script()
    if out:
        with open("latest_script.json", "w", encoding="utf-8") as f:
            json.dump(out, f, indent=4, ensure_ascii=False)
        print("✅ latest_script.json saved")