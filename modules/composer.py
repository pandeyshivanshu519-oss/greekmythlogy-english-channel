import os
import shutil
import random
import subprocess
import requests
import ffmpeg
from PIL import Image, ImageDraw, ImageFont


class Composer:

    def __init__(self):
        self.temp_dir      = os.path.join(os.getcwd(), "assets", "temp")
        self.final_dir     = os.path.join(os.getcwd(), "assets", "final")
        self.bg_music_path = "bgmusic.mp3"
        self.font_path     = self._resolve_font()

        # ── Pexels loop video keywords (brainrot style) ──────────────
        self.loop_keywords = [
            "satisfying sand", "water flow relaxing", "lava lamp",
            "soap bubbles", "rain window", "fire burning",
            "ocean waves", "clouds timelapse", "marble run",
            "kinetic sand", "waterfall nature", "snow falling"
        ]
        self.pexels_api_key = os.environ.get("PEXELS_API_KEY", "")

        os.makedirs(self.temp_dir,  exist_ok=True)
        os.makedirs(self.final_dir, exist_ok=True)

        if self.font_path:
            print(f"✅ Font: {self.font_path}")
        else:
            print("⚠️  No font — PIL default")

    # ─────────────────────────────────────────────────────────────────
    # FONT
    # ─────────────────────────────────────────────────────────────────

    def _resolve_font(self):
        for p in [
            os.path.join(os.getcwd(), "assets", "fonts", "NotoSans-Bold.ttf"),
            "/usr/share/fonts/truetype/noto/NotoSans-Bold.ttf",
            "/usr/share/fonts/truetype/noto/NotoSansDevanagari-Bold.ttf",
            "/usr/share/fonts/noto/NotoSansDevanagari-Bold.ttf",
        ]:
            if os.path.exists(p) and os.path.getsize(p) > 10_000:
                return p
        return None

    def _pil_font(self, size):
        if self.font_path:
            try:
                return ImageFont.truetype(self.font_path, size)
            except Exception:
                pass
        return ImageFont.load_default()

    # ─────────────────────────────────────────────────────────────────
    # UTILITIES
    # ─────────────────────────────────────────────────────────────────

    def get_duration(self, filepath):
        try:
            return float(ffmpeg.probe(filepath)["format"]["duration"])
        except Exception:
            return 0.0

    def _run_cmd(self, cmd, label):
        r = subprocess.run(cmd, capture_output=True, text=True)
        if r.returncode != 0:
            print(f"   ⚠️ {label}:\n{r.stderr[-250:]}")
            return False
        return True

    # ─────────────────────────────────────────────────────────────────
    # PEXELS LOOP VIDEO FETCH
    # ─────────────────────────────────────────────────────────────────

    def _fetch_loop_video(self, part_num):
        """
        Pexels API se random satisfying/loop video fetch karta hai.
        Har scene ke liye alag keyword use karta hai for variety.
        Returns: local path of downloaded loop video, or None
        """
        if not self.pexels_api_key:
            print("   ⚠️ PEXELS_API_KEY not set — skipping split screen")
            return None

        # Har part ke liye alag keyword — variety ke liye
        keyword = self.loop_keywords[part_num % len(self.loop_keywords)]
        out_path = os.path.join(self.temp_dir, f"loop_{part_num}.mp4")

        # Agar already downloaded hai toh reuse karo
        if os.path.exists(out_path) and os.path.getsize(out_path) > 100_000:
            print(f"   ♻️  Loop video reused: {keyword}")
            return out_path

        try:
            print(f"   🔍 Fetching loop video: '{keyword}'")
            headers = {"Authorization": self.pexels_api_key}
            params  = {
                "query":       keyword,
                "orientation": "landscape",
                "size":        "medium",
                "per_page":    10,
            }
            resp = requests.get(
                "https://api.pexels.com/videos/search",
                headers=headers,
                params=params,
                timeout=15
            )
            if resp.status_code != 200:
                print(f"   ⚠️ Pexels error: {resp.status_code}")
                return None

            videos = resp.json().get("videos", [])
            if not videos:
                print(f"   ⚠️ No videos found for: {keyword}")
                return None

            # Random video choose karo
            video   = random.choice(videos)
            # HD ya SD file prefer karo
            files   = sorted(
                video.get("video_files", []),
                key=lambda x: x.get("width", 0),
                reverse=True
            )
            # 1080p ya usse kam prefer karo (bade files skip karo)
            chosen  = None
            for f in files:
                if f.get("width", 0) <= 1920 and f.get("file_type", "") == "video/mp4":
                    chosen = f
                    break
            if not chosen and files:
                chosen = files[-1]

            if not chosen:
                return None

            url = chosen["link"]
            print(f"   ⬇️  Downloading loop video ({chosen.get('width')}x{chosen.get('height')})...")

            vid_resp = requests.get(url, timeout=60, stream=True)
            with open(out_path, "wb") as fp:
                for chunk in vid_resp.iter_content(chunk_size=8192):
                    fp.write(chunk)

            print(f"   ✅ Loop video saved: {keyword}")
            return out_path

        except Exception as e:
            print(f"   ⚠️ Loop video fetch failed: {e}")
            return None

    # ─────────────────────────────────────────────────────────────────
    # SPLIT SCREEN — main (top) + loop (bottom)
    # ─────────────────────────────────────────────────────────────────

    def _apply_split_screen(self, main_video, loop_video, part_num):
        """
        Final video ko brainrot split-screen format mein convert karta hai:
        - Top 50%  : main video (story/content)
        - Bottom 50%: loop video (satisfying clip, auto-looped)

        Output: 1080x1920 vertical video
        """
        out_path     = os.path.join(self.temp_dir, f"split_{part_num}.mp4")
        main_dur     = self.get_duration(main_video)
        half_h       = 960  # 1920 / 2

        print(f"   🎬 Applying split screen (top+bottom 960px each)...")

        cmd = [
            "ffmpeg", "-y",
            "-i", main_video,
            "-stream_loop", "-1",       # loop video ko infinitely loop karo
            "-i", loop_video,
            "-filter_complex",
            f"""
            [0:v]scale=1080:{half_h}:force_original_aspect_ratio=increase,
                  crop=1080:{half_h},
                  setsar=1[top];

            [1:v]scale=1080:{half_h}:force_original_aspect_ratio=increase,
                  crop=1080:{half_h},
                  setsar=1[bottom];

            [top][bottom]vstack=inputs=2[outv];

            [0:a]volume=1.0[outa]
            """,
            "-map", "[outv]",
            "-map", "[outa]",
            "-t",   str(main_dur),      # main video ki duration tak hi chale
            "-c:v", "libx264",
            "-preset", "fast",
            "-crf",    "23",
            "-c:a",    "aac",
            "-b:a",    "192k",
            "-r",      "30",
            "-pix_fmt", "yuv420p",
            "-movflags", "faststart",
            out_path
        ]

        ok = self._run_cmd(cmd, "Split screen")
        if ok and os.path.exists(out_path):
            print(f"   ✅ Split screen done → {os.path.basename(out_path)}")
            return out_path
        else:
            print(f"   ⚠️ Split screen failed — using original video")
            return main_video

    # ─────────────────────────────────────────────────────────────────
    # INTRO CLIP — 2 seconds, same design as thumbnail
    # ─────────────────────────────────────────────────────────────────

    def _make_intro_clip(self, intro_frame_path, part_num):
        out = os.path.join(self.temp_dir, f"intro_{part_num}.mp4")
        cmd = [
            "ffmpeg", "-y",
            "-loop", "1", "-i", intro_frame_path,
            "-t", "2.0",
            "-vf", "scale=1080:1920,fps=25",
            "-c:v", "libx264",
            "-pix_fmt", "yuv420p",
            "-preset", "fast",
            "-an",
            out,
        ]
        ok = self._run_cmd(cmd, "Intro clip")
        return out if ok else None

    # ─────────────────────────────────────────────────────────────────
    # SUBTITLE — voice-synced SRT
    # ─────────────────────────────────────────────────────────────────

    @staticmethod
    def _srt_ts(seconds):
        seconds  = max(0.0, seconds)
        total_ms = int(round(seconds * 1000))
        ms = total_ms % 1000
        s  = (total_ms // 1000) % 60
        m  = (total_ms // 60000) % 60
        h  = total_ms // 3600000
        return f"{h:02}:{m:02}:{s:02},{ms:03}"

    def _make_synced_srt(self, char_timings, intro_offset=2.0, scene_id=1):
        if not char_timings:
            return None

        srt_path = os.path.join(self.temp_dir, f"sub_{scene_id}.srt")
        entries  = []
        idx      = 1

        for timing in char_timings:
            tag   = timing.get("tag", "NARRATOR")
            text  = timing.get("text", "").strip()
            start = timing.get("start", 0.0) + intro_offset
            end   = timing.get("end",   0.0) + intro_offset

            if not text or end <= start:
                continue

            name_line = "" if tag == "NARRATOR" else f"[ {tag.title()} ]"

            words = text.split()
            chunks, cur = [], []
            for w in words:
                cur.append(w)
                if len(cur) >= 5:
                    chunks.append(" ".join(cur))
                    cur = []
            if cur:
                chunks.append(" ".join(cur))

            dur_per_chunk = max((end - start) / len(chunks), 0.5)

            for ci, chunk in enumerate(chunks):
                cs = start + ci * dur_per_chunk
                ce = min(cs + dur_per_chunk - 0.05, end)
                sub_text = f"{name_line}\n{chunk}" if name_line else chunk
                entries.append((idx, cs, ce, sub_text))
                idx += 1

        if not entries:
            return None

        with open(srt_path, "w", encoding="utf-8") as f:
            for i, cs, ce, sub_text in entries:
                f.write(f"{i}\n{self._srt_ts(cs)} --> {self._srt_ts(ce)}\n{sub_text}\n\n")

        return srt_path

    def _burn_subtitles(self, src, srt_path, dst):
        if not self.font_path:
            shutil.copy2(src, dst)
            return False

        safe_srt  = srt_path.replace("\\", "/")
        safe_font = self.font_path.replace("\\", "/")
        if len(safe_srt) >= 2 and safe_srt[1] == ":":
            safe_srt = safe_srt[0] + "\\:" + safe_srt[2:]

        style = (
            f"fontfile={safe_font},"
            "FontSize=20,"
            "PrimaryColour=&H00FFFFFF,"
            "SecondaryColour=&H0000FFFF,"
            "OutlineColour=&H00000000,"
            "BackColour=&H90000000,"
            "Bold=1,"
            "Outline=3,"
            "Shadow=1,"
            "Alignment=2,"
            "MarginV=130,"
            "MarginL=40,"
            "MarginR=40"
        )
        cmd = [
            "ffmpeg", "-y", "-i", src,
            "-vf", f"subtitles='{safe_srt}':force_style='{style}'",
            "-c:v", "libx264", "-c:a", "copy",
            "-pix_fmt", "yuv420p", "-preset", "fast", dst,
        ]
        ok = self._run_cmd(cmd, "Subtitles")
        if not ok:
            shutil.copy2(src, dst)
        return ok

    # ─────────────────────────────────────────────────────────────────
    # PIL BADGE — top bar on each image
    # ─────────────────────────────────────────────────────────────────

    def _burn_badge_on_image(self, img_path, out_path, top_text, part_num, total_parts):
        img  = Image.open(img_path).convert("RGB")
        W, H = img.size
        draw = ImageDraw.Draw(img, "RGBA")

        draw.rectangle([(0,0),(W,82)], fill=(0,0,0,215))

        mf = self._pil_font(26)
        for dx, dy in [(-2,0),(2,0),(0,-2),(0,2)]:
            draw.text((20+dx, 24+dy), top_text, font=mf, fill=(0,0,0,255))
        draw.text((20, 24), top_text, font=mf, fill=(255,255,255,255))

        part_str = f"PART {part_num}"
        pf       = self._pil_font(22)
        pb       = draw.textbbox((0,0), part_str, font=pf)
        pw, ph   = pb[2]-pb[0], pb[3]-pb[1]
        bx       = W - pw - 36
        by       = 16
        draw.rounded_rectangle(
            [bx-10, by-6, bx+pw+10, by+ph+6],
            radius=8,
            fill=(255, 210, 0, 255)
        )
        draw.text((bx, by), part_str, font=pf, fill=(20,20,20))

        img.save(out_path, "JPEG", quality=92)
        return out_path

    # ─────────────────────────────────────────────────────────────────
    # IMAGE → VIDEO KEN BURNS
    # ─────────────────────────────────────────────────────────────────

    def _image_to_video_kenburns(self, img_path, duration, out_path, zoom_dir="in"):
        fps    = 25
        frames = int(duration * fps)
        z_expr = "min(zoom+0.0003,1.08)" if zoom_dir == "in" else "max(zoom-0.0003,1.0)"
        vf = (
            f"scale=1200:2133,"
            f"zoompan=z='{z_expr}':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)'"
            f":d={frames}:s=1080x1920:fps={fps},"
            f"setpts=PTS-STARTPTS,fps={fps}"
        )
        cmd = [
            "ffmpeg", "-y",
            "-loop", "1", "-i", img_path,
            "-vf", vf,
            "-t", str(duration),
            "-c:v", "libx264",
            "-pix_fmt", "yuv420p",
            "-preset", "fast", out_path,
        ]
        return self._run_cmd(cmd, "KenBurns")

    def _clip_to_portrait(self, clip_path, duration, out_path):
        cmd = [
            "ffmpeg", "-y", "-i", clip_path,
            "-vf", "scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,fps=25",
            "-t", str(duration), "-an",
            "-c:v", "libx264", "-pix_fmt", "yuv420p",
            "-preset", "fast", out_path,
        ]
        return self._run_cmd(cmd, "Clip→Portrait")

    # ─────────────────────────────────────────────────────────────────
    # BUILD VISUAL SEQUENCE
    # ─────────────────────────────────────────────────────────────────

    def _build_visual_sequence(self, image_paths, mood_clips,
                                total_dur, part_num, movie_name, total_parts):
        short_movie = movie_name[:22]

        all_visuals = []
        mood_idx    = 0
        for i, img in enumerate(image_paths):
            all_visuals.append(("image", img))
            if (i+1) % 3 == 0 and mood_idx < len(mood_clips):
                all_visuals.append(("clip", mood_clips[mood_idx]))
                mood_idx += 1

        n            = max(len(all_visuals), 1)
        dur_per_slot = max(3.5, min(total_dur / n, 8.0))
        segments     = []

        for idx, (vtype, vpath) in enumerate(all_visuals):
            seg = os.path.join(self.temp_dir, f"seg_{part_num}_{idx+1}.mp4")

            if vtype == "image":
                overlay = os.path.join(self.temp_dir, f"ov_{part_num}_{idx+1}.jpg")
                self._burn_badge_on_image(
                    vpath, overlay, short_movie, part_num, total_parts
                )
                ok = self._image_to_video_kenburns(
                    overlay, dur_per_slot, seg,
                    zoom_dir="in" if idx % 2 == 0 else "out"
                )
            else:
                ok = self._clip_to_portrait(vpath, dur_per_slot, seg)

            if ok and os.path.exists(seg):
                segments.append(seg)

        if not segments:
            return None

        if len(segments) == 1:
            return segments[0]

        list_file = os.path.join(self.temp_dir, f"list_{part_num}.txt")
        with open(list_file, "w") as f:
            for p in segments:
                f.write(f"file '{p}'\n")
        out = os.path.join(self.temp_dir, f"visual_{part_num}.mp4")
        ok  = self._run_cmd([
            "ffmpeg", "-y", "-f", "concat", "-safe", "0",
            "-i", list_file,
            "-c:v", "libx264", "-pix_fmt", "yuv420p",
            "-preset", "fast", out,
        ], "Concat")
        return out if ok else segments[0]

    # ─────────────────────────────────────────────────────────────────
    # PROCESS SCENE
    # ─────────────────────────────────────────────────────────────────

    def process_scene(self, scene, image_paths, mood_clips,
                      intro_frame_path=None, is_first=False):
        part_num    = scene.get("part_number", 1)
        total_parts = scene.get("total_parts", 100)
        movie_name  = scene.get("movie", "Movie")
        audio_path  = scene.get("audio_path")
        total_dur   = scene.get("duration", 0)
        script_text = scene.get("text", "")

        if not audio_path or not os.path.exists(audio_path):
            print(f"   ⚠️ Audio missing Part {part_num}")
            return None
        if not image_paths:
            print(f"   ⚠️ No images Part {part_num}")
            return None

        nosub_path  = os.path.join(self.temp_dir, f"nosub_{part_num}.mp4")
        subbed_path = os.path.join(self.temp_dir, f"subbed_{part_num}.mp4")
        final_path  = os.path.join(self.temp_dir, f"scene_{part_num}.mp4")

        # ── Step 1: Build visual (images + clips) ────────────────────
        visual = self._build_visual_sequence(
            image_paths, mood_clips, total_dur,
            part_num, movie_name, total_parts
        )
        if not visual:
            print(f"   ❌ Visual failed Part {part_num}")
            return None

        # ── Step 2: Prepend 2-sec intro clip ─────────────────────────
        if intro_frame_path and os.path.exists(intro_frame_path):
            intro_clip = self._make_intro_clip(intro_frame_path, part_num)
            if intro_clip:
                combined_list = os.path.join(
                    self.temp_dir, f"combined_list_{part_num}.txt"
                )
                combined_vid  = os.path.join(
                    self.temp_dir, f"combined_{part_num}.mp4"
                )
                with open(combined_list, "w") as f:
                    f.write(f"file '{intro_clip}'\n")
                    f.write(f"file '{visual}'\n")
                ok = self._run_cmd([
                    "ffmpeg", "-y", "-f", "concat", "-safe", "0",
                    "-i", combined_list,
                    "-c:v", "libx264", "-pix_fmt", "yuv420p",
                    "-preset", "fast", combined_vid,
                ], "Prepend intro")
                if ok:
                    visual = combined_vid

        # ── Step 3: Mix audio (voice + bg music) ─────────────────────
        try:
            voice = ffmpeg.input(audio_path)
            vis   = ffmpeg.input(visual)

            if os.path.exists(self.bg_music_path):
                bg = (
                    ffmpeg.input(self.bg_music_path, stream_loop=-1)
                    .filter("volume", 0.10)
                    .filter("atrim", duration=total_dur + 3)
                )
                audio_out = ffmpeg.filter(
                    [voice, bg], "amix", inputs=2, duration="first"
                )
            else:
                audio_out = voice

            (
                ffmpeg.output(
                    vis.video, audio_out, nosub_path,
                    vcodec="libx264", acodec="aac",
                    pix_fmt="yuv420p", preset="medium",
                    movflags="faststart",
                    **{"avoid_negative_ts": "make_zero", "shortest": None}
                ).run(overwrite_output=True, quiet=True)
            )
        except Exception as e:
            print(f"   ❌ Audio mix failed: {e}")
            return None

        # ── Step 4: Synced subtitles with character names ─────────────
        char_timings = scene.get("char_timings", [])
        actual_dur   = self.get_duration(nosub_path)

        if not char_timings and scene.get("text"):
            words    = scene["text"].split()
            dur      = max(actual_dur - 2.0, 1.0)
            char_timings = [{"tag": "NARRATOR", "text": scene["text"],
                              "start": 0.0, "end": dur}]

        srt = self._make_synced_srt(char_timings, intro_offset=2.0, scene_id=part_num)
        if srt:
            ok = self._burn_subtitles(nosub_path, srt, subbed_path)
            current = subbed_path if ok else nosub_path
        else:
            current = nosub_path

        if current != final_path:
            shutil.copy2(current, final_path)

        # ── Step 5: Split screen (brainrot format) ───────────────────
        loop_video = self._fetch_loop_video(part_num)
        if loop_video and os.path.exists(loop_video):
            split_path = self._apply_split_screen(final_path, loop_video, part_num)
            if split_path and os.path.exists(split_path):
                shutil.copy2(split_path, final_path)
                print(f"   🎬 Brainrot split screen applied!")
        else:
            print(f"   ℹ️  No loop video — normal video output")

        print(f"   ✅ Part {part_num} done ({total_dur:.1f}s + 2s intro)")
        return final_path

    # ─────────────────────────────────────────────────────────────────
    # RENDER ALL
    # ─────────────────────────────────────────────────────────────────

    def render_all_scenes(self, script_data, image_paths_list,
                           mood_clips_list, intro_frame_path=None):
        rendered = []
        for i, scene in enumerate(script_data):
            imgs  = image_paths_list[i] if i < len(image_paths_list) else []
            moods = mood_clips_list[i]  if i < len(mood_clips_list)  else []
            path  = self.process_scene(
                scene, imgs, moods,
                intro_frame_path=intro_frame_path,
                is_first=(i == 0)
            )
            if path:
                rendered.append(path)
        return rendered

    # ─────────────────────────────────────────────────────────────────
    # FINAL OUTPUT
    # ─────────────────────────────────────────────────────────────────

    def concatenate_with_transitions(
        self, video_paths,
        output_filename="final_short.mp4",
        channel_name="@MovieStoryteller",
    ):
        print("🎬 Finalizing...")
        output_path = os.path.join(self.final_dir, output_filename)
        if os.path.exists(output_path):
            try: os.remove(output_path)
            except Exception: pass

        if not video_paths:
            return None

        if len(video_paths) == 1:
            shutil.copy2(video_paths[0], output_path)
            print(f"✅ FINAL: {output_path}")
            return output_path

        inp         = ffmpeg.input(video_paths[0])
        v_stream    = inp.video
        a_stream    = inp.audio
        current_dur = self.get_duration(video_paths[0])

        for i in range(1, len(video_paths)):
            nxt      = ffmpeg.input(video_paths[i])
            next_dur = self.get_duration(video_paths[i])
            trans    = 0.5
            offset   = max(current_dur - trans, 0.1)
            v_stream = ffmpeg.filter(
                [v_stream, nxt.video], "xfade",
                transition="fade", duration=trans, offset=offset,
            )
            a_stream = ffmpeg.filter(
                [a_stream, nxt.audio], "acrossfade", d=trans,
            )
            current_dur += next_dur - trans

        try:
            (
                ffmpeg.output(
                    v_stream, a_stream, output_path,
                    vcodec="libx264", acodec="aac",
                    pix_fmt="yuv420p", preset="medium",
                    movflags="faststart",
                ).run(overwrite_output=True, quiet=False)
            )
        except Exception as e:
            print(f"❌ Final stitch error: {e}")
            return None

        print(f"✅ FINAL: {output_path}")
        return output_path
