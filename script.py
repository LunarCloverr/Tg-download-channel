import os
import asyncio
from tqdm import tqdm
from telethon.sync import TelegramClient
from telethon.tl.types import MessageMediaPhoto, DocumentAttributeVideo, MessageMediaDocument
from telethon.errors import SessionPasswordNeededError
from datetime import datetime
import logging
from pathlib import Path
import json
from concurrent.futures import ThreadPoolExecutor
import aiohttp
import signal
import time

# Configuration
API_ID = 'ID'
API_HASH = 'HASH'
PHONE = 'your phone number (with country code)'
DOWNLOAD_MEDIA_TYPES = {'photo', 'video', 'all'}  # Available media types

class TerminalDownloader:
    def __init__(self):
        self.client = None
        self.download_path = Path('downloads')
        self.download_path.mkdir(exist_ok=True)
        self.setup_logging()
        self.running = True
        self.download_stats = {
            'total_files': 0,
            'downloaded_files': 0,
            'failed_files': 0,
            'start_time': None,
            'end_time': None
        }
        signal.signal(signal.SIGINT, self.signal_handler)

    def setup_logging(self):
        log_path = Path('logs')
        log_path.mkdir(exist_ok=True)
        logging.basicConfig(
            filename=log_path / f'downloader_{datetime.now():%Y%m%d_%H%M}.log',
            level=logging.INFO,
            format='%(asctime)s - %(message)s'
        )

    def signal_handler(self, signum, frame):
        print("\nOperation interrupted... Please wait.")
        self.running = False

    async def init_client(self):
        self.client = TelegramClient('session_name', API_ID, API_HASH)
        await self.client.start(PHONE)
        print("Connected to Telegram")

    async def get_channel(self, channel_input):
        try:
            if channel_input.isdigit():
                entity = await self.client.get_entity(int(channel_input))
            else:
                entity = await self.client.get_entity(channel_input)
            return entity
        except Exception as e:
            print(f"Error retrieving channel: {e}")
            return None

    async def process_media(self, message, save_path, pbar, media_type):
        if not self.running:
            return False
        
        try:
            if message.media:
                date_str = message.date.strftime('%Y%m%d_%H%M%S')
                caption = message.text or "media"
                caption = "".join(c if c.isalnum() or c in ('-', '_') else '_' for c in caption)[:30]

                # Filter by media type
                if media_type == 'photo' and isinstance(message.media, MessageMediaPhoto):
                    ext = '.jpg'
                elif media_type == 'video' and isinstance(message.media, MessageMediaDocument) and any(isinstance(attr, DocumentAttributeVideo) for attr in message.media.document.attributes):
                    ext = '.mp4'
                elif media_type == 'all':
                    if isinstance(message.media, MessageMediaPhoto):
                        ext = '.jpg'
                    elif isinstance(message.media, MessageMediaDocument) and any(isinstance(attr, DocumentAttributeVideo) for attr in message.media.document.attributes):
                        ext = '.mp4'
                    else:
                        return False
                else:
                    return False

                filename = f"{date_str}_{caption}{ext}"
                file_path = save_path / filename

                for attempt in range(2):
                    try:
                        await self.client.download_media(message.media, file=str(file_path))
                        self.download_stats['downloaded_files'] += 1
                        pbar.update(1)
                        return True
                    except Exception as e:
                        if attempt == 1:
                            logging.error(f"Error downloading {filename}: {e}")
                            self.download_stats['failed_files'] += 1
                            return False
                        await asyncio.sleep(0.5)
        except Exception as e:
            logging.error(f"Error processing media: {e}")
            self.download_stats['failed_files'] += 1
            return False
        return False

    def print_download_report(self):
        if self.download_stats['start_time'] and self.download_stats['end_time']:
            duration = self.download_stats['end_time'] - self.download_stats['start_time']
            duration_seconds = duration.total_seconds()
            
            print("\n=== Download Report ===")
            print(f"Total files found: {self.download_stats['total_files']}")
            print(f"Successfully downloaded: {self.download_stats['downloaded_files']}")
            print(f"Failed downloads: {self.download_stats['failed_files']}")
            print(f"Download time: {duration_seconds:.1f} seconds")
            
            if self.download_stats['downloaded_files'] > 0:
                speed = self.download_stats['downloaded_files'] / duration_seconds
                print(f"Average speed: {speed:.1f} files/sec")
            
            success_rate = (self.download_stats['downloaded_files'] / self.download_stats['total_files'] * 100 
                          if self.download_stats['total_files'] > 0 else 0)
            print(f"Download success rate: {success_rate:.1f}%")

    async def download_channel(self, channel_input, media_type):
        try:
            channel = await self.get_channel(channel_input)
            if not channel:
                print("Channel not found")
                return

            print(f"\nDownloading from channel: {channel.title}")
            save_path = self.download_path / channel.title
            save_path.mkdir(exist_ok=True)

            messages = await self.client.get_messages(channel, limit=None)
            media_messages = [msg for msg in messages if msg.media]

            # Filter media by type
            if media_type != 'all':
                media_messages = [msg for msg in media_messages if (media_type == 'photo' and isinstance(msg.media, MessageMediaPhoto)) or
                                                       (media_type == 'video' and isinstance(msg.media, MessageMediaDocument) and any(isinstance(attr, DocumentAttributeVideo) for attr in msg.media.document.attributes))]

            if not media_messages:
                print("No media files found")
                return

            self.download_stats['total_files'] = len(media_messages)
            self.download_stats['start_time'] = datetime.now()
            
            print(f"Found {len(media_messages)} media files")
            
            with tqdm(total=len(media_messages), desc="Downloading", 
                     unit='file', ncols=80) as pbar:
                
                tasks = [
                    self.process_media(message, save_path, pbar, media_type)
                    for message in media_messages
                ]
                
                chunk_size = 10
                for i in range(0, len(tasks), chunk_size):
                    chunk = tasks[i:i + chunk_size]
                    await asyncio.gather(*chunk)
                    
                    if not self.running:
                        print("\nDownload interrupted")
                        self.download_stats['end_time'] = datetime.now()
                        self.print_download_report()
                        return

            self.download_stats['end_time'] = datetime.now()
            self.print_download_report()
            print(f"\nFiles saved to: {save_path}")

        except Exception as e:
            print(f"Error: {e}")
        finally:
            if self.client:
                await self.client.disconnect()

async def main():
    downloader = TerminalDownloader()
    await downloader.init_client()
    
    while True:
        print("\n=== Telegram Media Downloader ===")
        channel_input = input("\nEnter channel ID or link (or 'q' to quit): ").strip()
        
        if channel_input.lower() == 'q':
            break
            
        media_type = input("\nSelect media type to download (photo/video/all): ").strip().lower()
        if media_type not in DOWNLOAD_MEDIA_TYPES:
            print("Invalid media type selection")
            continue
        
        if channel_input:
            await downloader.download_channel(channel_input, media_type)
        else:
            print("Please enter a channel ID or link")

if __name__ == "__main__":
    asyncio.run(main())
