import os
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

        # ── Sanitize and validate tags ──────────────────────────────
        def sanitize_tags(tags_list):
            """
            YouTube tag validation:
            - Max 500 chars total
            - No special chars except space & hyphen
            - Max 30 tags
            - Each tag max 30 chars
            """
            if not tags_list:
                return ["mythology", "shorts"]
            
            sanitized = []
            total_chars = 0
            
            for tag in tags_list:
                if not isinstance(tag, str):
                    continue
                
                # Remove invalid characters (keep only alphanumeric, space, hyphen)
                cleaned = ''.join(c for c in tag.lower() if c.isalnum() or c in ' -')
                cleaned = cleaned.strip()
                
                # Skip if too long or empty
                if not cleaned or len(cleaned) > 30:
                    continue
                
                # Check if adding this tag would exceed 500 char limit
                new_total = total_chars + len(cleaned) + 1  # +1 for comma
                if new_total > 500:
                    break
                
                # Skip duplicates
                if cleaned not in sanitized:
                    sanitized.append(cleaned)
                    total_chars = new_total
                
                # Max 30 tags
                if len(sanitized) >= 30:
                    break
            
            return sanitized if sanitized else ["mythology", "shorts"]

        validated_tags = sanitize_tags(tags)

        body = {
            "snippet": {
                "title": title[:100],
                "description": description,
                "tags": validated_tags,
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
