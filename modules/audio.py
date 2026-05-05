import os
import asyncio
import subprocess
import edge_tts
from mutagen.mp3 import MP3

# ─────────────────────────────────────────────────────────────────────
# ENGLISH VOICE POOL — mythology channel
#
# Much wider variety than Hindi — 4 male + 4 female voices
# All reliably support English text
#
# MALE:
#   en-US-GuyNeural        → deep, authoritative — NARRATOR
#   en-US-AndrewNeural     → bold, confident, warm — HERO
#   en-GB-RyanNeural       → British, cool, sharp — VILLAIN / ELDER
#   en-US-BrianNeural      → young, clear, friendly — CHILD / SIDEKICK
#
# FEMALE:
#   en-US-AriaNeural       → warm, expressive — main female
#   en-GB-SoniaNeural      → British, composed — wise/elder female
#   en-US-JennyNeural      → friendly, bright — young female
#   en-AU-NatashaNeural    → Australian, distinct accent — sidekick/varied
# ─────────────────────────────────────────────────────────────────────

MALE_VOICES = [
    "en-US-GuyNeural",      # slot 0 — NARRATOR (reserved)
    "en-US-AndrewNeural",   # slot 1 — Hero / lead male
    "en-GB-RyanNeural",     # slot 2 — Villain / British elder
    "en-US-BrianNeural",    # slot 3 — Young / sidekick male
]

FEMALE_VOICES = [
    "en-US-AriaNeural",     # slot 0 — Main female
    "en-GB-SoniaNeural",    # slot 1 — Elder / composed female
    "en-US-JennyNeural",    # slot 2 — Young / friendly female
    "en-AU-NatashaNeural",  # slot 3 — Distinct accent female
]

NARRATOR_VOICE = MALE_VOICES[0]   # en-US-GuyNeural — deep, epic

# ─────────────────────────────────────────────────────────────────────
# FEEL PRESETS — rate/pitch per character role
# ─────────────────────────────────────────────────────────────────────

FEEL_PRESETS = {
    "NARRATOR": {"rate": "+0%",  "pitch": "-4Hz",  "volume": "+5%"},   # slow, deep, epic
    "HERO":     {"rate": "+15%", "pitch": "+2Hz",  "volume": "+12%"},  # energetic, brave
    "VILLAIN":  {"rate": "-12%", "pitch": "-10Hz", "volume": "+15%"},  # slow, cold, menacing
    "ELDER":    {"rate": "-15%", "pitch": "-6Hz",  "volume": "+5%"},   # wise, measured
    "CHILD":    {"rate": "+25%", "pitch": "+8Hz",  "volume": "+10%"},  # fast, excited, high
    "SIDEKICK": {"rate": "+18%", "pitch": "+4Hz",  "volume": "+12%"},  # cheerful, warm
    "FEMALE":   {"rate": "+5%",  "pitch": "+0Hz",  "volume": "+8%"},   # natural, expressive
    "DEFAULT":  {"rate": "+5%",  "pitch": "+0Hz",  "volume": "+8%"},
}


def _canonical(name: str) -> str:
    return name.upper().strip().replace("_", " ")


def _assign_voice_slot(char_profiles: dict, char_name: str, gender: str) -> int:
    pool_size = len(MALE_VOICES)
    used_slots = set()
    for name, data in char_profiles.items():
        if name == "NARRATOR":
            continue
        if data.get("gender", "male").lower() == gender.lower():
            slot = data.get("voice_slot")
            if slot is not None:
                used_slots.add(slot)
    start = 1 if gender.lower() == "male" else 0
    for slot in range(start, pool_size):
        if slot not in used_slots:
            return slot
    return start


def _resolve_profile(gender: str, voice_type: str, voice_slot: int) -> dict:
    pool   = FEMALE_VOICES if gender.lower() == "female" else MALE_VOICES
    slot   = max(0, min(voice_slot, len(pool) - 1))
    voice  = pool[slot]
    preset = FEEL_PRESETS.get(voice_type.upper(), FEEL_PRESETS["DEFAULT"])
    return {"voice": voice, **preset}


class AudioEngine:

    def __init__(self):
        self.output_dir = os.path.join(os.getcwd(), "assets", "audio_clips")
        os.makedirs(self.output_dir, exist_ok=True)

    async def _generate_clip(self, text, profile, filename, retries=3):
        output_path = os.path.join(self.output_dir, filename)
        for attempt in range(retries):
            try:
                comm = edge_tts.Communicate(
                    text=text,
                    voice=profile["voice"],
                    rate=profile["rate"],
                    pitch=profile["pitch"],
                    volume=profile["volume"],
                )
                await comm.save(output_path)
                return output_path
            except Exception as e:
                print(f"      TTS error attempt {attempt+1}: {e}")
                if attempt < retries - 1:
                    await asyncio.sleep(2)
                else:
                    raise

    def get_audio_duration(self, path):
        try:
            return MP3(path).info.length
        except Exception:
            return 0.0

    def _merge_clips(self, clip_paths, output_path):
        list_file = output_path.replace(".mp3", "_list.txt")
        with open(list_file, "w", encoding="utf-8") as f:
            for p in clip_paths:
                f.write(f"file '{p}'\n")
        cmd = [
            "ffmpeg", "-y", "-f", "concat", "-safe", "0",
            "-i", list_file,
            "-acodec", "libmp3lame", "-q:a", "2",
            output_path,
        ]
        r = subprocess.run(cmd, capture_output=True, text=True)
        try:
            os.remove(list_file)
        except Exception:
            pass
        if r.returncode != 0:
            print(f"   Merge failed: {r.stderr[-200:]}")
            return False
        return True

    async def process_scene(self, scene):
        scene_id      = scene.get("id", 1)
        script_lines  = scene.get("script_lines", [])
        raw_profiles  = scene.get("character_profiles", {})
        char_profiles = {_canonical(k): v for k, v in raw_profiles.items()}
        scene["character_profiles"] = char_profiles

        if not script_lines and scene.get("text"):
            script_lines = [{"tag": "NARRATOR", "voice_type": "NARRATOR",
                              "gender": "male", "text": scene["text"]}]
        if not script_lines:
            print(f"   Scene {scene_id}: no lines")
            return scene

        # Assign voice slots to new characters
        for name, data in char_profiles.items():
            if name == "NARRATOR":
                continue
            if "voice_slot" not in data:
                gender = data.get("gender", "male").lower()
                data["voice_slot"] = _assign_voice_slot(char_profiles, name, gender)

        print(f"   Scene {scene_id} — {len(script_lines)} lines")
        for name, data in char_profiles.items():
            if name == "NARRATOR":
                continue
            g    = data.get("gender", "male")
            vt   = data.get("voice", "HERO")
            slot = data.get("voice_slot", 1)
            pool = FEMALE_VOICES if g == "female" else MALE_VOICES
            vname = pool[min(slot, len(pool) - 1)]
            print(f"      {name}: {g} | {vt} | {vname}")

        clip_paths   = []
        char_timings = []
        current_time = 0.0

        for i, line in enumerate(script_lines):
            raw_tag    = str(line.get("tag", "NARRATOR")).upper().strip()
            tag        = _canonical(raw_tag)
            voice_type = str(line.get("voice_type", "DEFAULT")).upper().strip()
            text       = str(line.get("text", "")).strip()
            if not text:
                continue

            if tag == "NARRATOR":
                profile = {"voice": NARRATOR_VOICE, **FEEL_PRESETS["NARRATOR"]}
            else:
                cp     = char_profiles.get(tag, {})
                gender = str(cp.get("gender", "male")).lower().strip()
                slot   = cp.get("voice_slot", 1)
                profile = _resolve_profile(gender, voice_type, slot)

            safe_tag = tag.replace(" ", "_")[:20]
            filename = f"line_{scene_id}_{i:03d}_{safe_tag}.mp3"

            try:
                path = await self._generate_clip(text, profile, filename)
                dur  = self.get_audio_duration(path)
                clip_paths.append(path)
                char_timings.append({
                    "tag":   tag,
                    "voice": profile["voice"],
                    "feel":  voice_type,
                    "text":  text,
                    "start": current_time,
                    "end":   current_time + dur,
                })
                current_time += dur
                print(f"      [{tag}|{profile['voice'].split('-')[2][:10]}] ({dur:.1f}s): {text[:45]}{'...' if len(text) > 45 else ''}")
                await asyncio.sleep(0.4)
            except Exception as e:
                print(f"      Skipping [{tag}]: {e}")

        if not clip_paths:
            return scene

        if len(clip_paths) == 1:
            final_path = clip_paths[0]
        else:
            final_path = os.path.join(self.output_dir, f"voice_{scene_id}.mp3")
            if not self._merge_clips(clip_paths, final_path):
                final_path = clip_paths[0]

        scene["audio_path"]        = final_path
        scene["duration"]          = self.get_audio_duration(final_path)
        scene["char_timings"]      = char_timings
        scene["character_profiles"] = char_profiles

        print(f"   ✅ {scene['duration']:.1f}s | {len(char_timings)} lines")
        return scene

    async def process_script(self, script_data):
        print(f"🎙️ English Voice Engine — {len(script_data)} scene(s)...")
        for i, scene in enumerate(script_data):
            try:
                script_data[i] = await self.process_scene(scene)
            except Exception as e:
                print(f"   Scene {i} failed: {e}")
        return script_data