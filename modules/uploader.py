import os
import re
import google.auth
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request


class YouTubeUploader:

    def __init__(self):
        self.SCOPES  = ["https://www.googleapis.com/auth/youtube"]
        self.service = None

    def authenticate(self):
        try:
            creds = Credentials(
                token=None,
                refresh_token=os.getenv("YOUTUBE_REFRESH_TOKEN"),
                token_uri="https://oauth2.googleapis.com/token",
                client_id=os.getenv("YOUTUBE_CLIENT_ID"),
                client_secret=os.getenv("YOUTUBE_CLIENT_SECRET"),
                scopes=self.SCOPES,
            )
            creds.refresh(Request())
            self.service = build("youtube", "v3", credentials=creds)
            print("✅ YouTube authentication successful")
            return True
        except Exception as e:
            print(f"❌ Auth failed: {e}")
            return False

    def upload(self, video_path, title, description,
               thumbnail_path=None, tags=None, privacy="public"):

        if not os.path.exists(video_path):
            print(f"❌ Video not found: {video_path}")
            return None

        if not self.authenticate():
            return None

        # 🔧 FIX: Clean tags before sending to YouTube
        if tags:
            clean = []
            total_length = 0

            for tag in tags:
                if not tag:
                    continue

                # remove invalid characters
                tag = re.sub(r"[#@|\\/:\n\r\t]", "", tag).strip()

                if not tag:
                    continue

                # limit individual tag length
                if len(tag) > 30:
                    tag = tag[:30]

                # total tags length limit (~500 chars)
                if total_length + len(tag) + 1 > 480:
                    break

                clean.append(tag)
                total_length += len(tag) + 1

            # remove duplicates
            tags = list(dict.fromkeys(clean))

        body = {
            "snippet": {
                "title": title[:100],
                "description": description,
                "tags": tags or ["hindi story", "shorts"],
                "categoryId": "22",
            },
            "status": {
                "privacyStatus": privacy,
                "selfDeclaredMadeForKids": False,
            },
        }

        media = MediaFileUpload(video_path, chunksize=-1, resumable=True)

        try:
            print("📤 Uploading video...")
            request  = self.service.videos().insert(
                part="snippet,status", body=body, media_body=media
            )
            response = request.execute()
            video_id = response["id"]
            print(f"✅ Video uploaded: https://youtu.be/{video_id}")

            if thumbnail_path and os.path.exists(thumbnail_path):
                print("🖼️  Uploading thumbnail...")
                try:
                    self.service.thumbnails().set(
                        videoId=video_id,
                        media_body=MediaFileUpload(
                            thumbnail_path, mimetype="image/png"
                        ),
                    ).execute()
                    print("✅ Thumbnail uploaded successfully")
                except Exception as te:
                    print(f"⚠️  Thumbnail failed: {te}")
                    print("   Fix: Regenerate OAuth token with full 'youtube' scope.")

            return video_id

        except Exception as e:
            print(f"❌ Upload failed: {e}")
            return None
