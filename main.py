import shutil
import sys

## import argparse
import asyncio
import os
from telethon.errors import UsernameNotOccupiedError
from tqdm import tqdm
from telethon import TelegramClient
import logging

import toml

with open("config.toml", "r") as f:
    config = toml.load(f)

api_id = config["api_id"]
api_hash = config["api_hash"]
session_name = config["session_name"]
user_defined_path = config["user_defined_path"]
chat_id = config["chat_id"]


client = TelegramClient(
    session_name, api_id, api_hash
)  # Pass login parameters to telethon


## Parser for cmdline flags
# parser = argparse.ArgumentParser()


def get_download_folder():
    try:  ## for handling KeyboardInterrupt
        while True:
            global download_path
            download_path = os.path.expanduser(user_defined_path)

            if os.path.exists(download_path):
                return download_path
            else:
                print("Invalid path, please re-enter")
    except KeyboardInterrupt:
        print("Keyboard Interrupt, exiting")


# validate chat_id


async def get_chat_id_to_download_from():
    global chat_id

    try:
        await client.get_entity(chat_id)
        return True
    except (UsernameNotOccupiedError, ValueError):
        print("Invalid chat ID, Please re-enter chat ID")
        return False


## progress_bar block

import time

def make_progress_bar(total_size, label):  ## defining progress_bar
    progress_bar = tqdm(
        total=total_size, unit="B", unit_scale=True, desc=label, leave=False
    )

    last_update = {"time": time.time()}  # store last update timestamp

    def callback(current, total):
        progress_bar.total = total
        progress_bar.n = current
        now = time.time()
        if now - last_update["time"] >= 30:  # only refresh every 1 second
            progress_bar.refresh()
            last_update["time"] = now

    return callback

## producer-worker model for download

queue = asyncio.Queue()


async def producer(chat):  ##Producer
    async for message in client.iter_messages(chat):
        if message.media and getattr(message, "file", None):
            await queue.put(message)


async def worker():  ## Workers
    while True:
        message = await queue.get()
        try:  ## define filename and filesize
            file_size = message.file.size if message.file else 0
            filename = message.file.name if message.file and message.file.name else 0

            ## define progress
            callback = make_progress_bar(file_size, filename)

            ## Download files we got
            await client.download_media(
                message.media, file=download_path + "/", progress_callback=callback
            )

        except Exception as e:
            print(f"Error Downloading {message.id}: {e}")
        queue.task_done()


## MAIN


async def main():
    await client.start()  ## THIS IS AWAITABLE AND NEEDS TO HAVE AWAIT
    await client.connect()

    get_download_folder()

    await get_chat_id_to_download_from()

    workers = [asyncio.create_task(worker()) for _ in range(20)]

    await producer(chat_id)

    await queue.join()

    # cancel workers after queue is empty
    for work in workers:
        work.cancel()


## Run the main function.
if __name__ == "__main__":
    try:
        asyncio.run(main())  ## run main synchronously
    except KeyboardInterrupt:
        print("Keyboard interrupt detected, exiting")
        try:
            sys.exit(130)
        except SystemExit:
            os._exit(130)


## This reduces log generated during operation(as it should)
logging.getLogger("telethon.network.mtproto_connection").setLevel(logging.WARNING)
logging.getLogger("asyncio").setLevel(logging.ERROR)


columns = shutil.get_terminal_size((70, 24)).columns
