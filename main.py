from telethon import TelegramClient, events
import asyncio
import os
import logging
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Setup logging
logging.basicConfig(
    level=logging.DEBUG,  # Change to logging.INFO for less verbose output
    format="%(asctime)s - %(levelname)s - %(message)s",
)

logging.info("Starting the script and loading configuration...")

API_ID = int(os.getenv("API_ID", 0))
API_HASH = str(os.getenv("API_HASH", ""))
source_ids_str = os.getenv("SOURCE_IDS", "")
source_ids = list(map(int,
                      source_ids_str.split(","))) if source_ids_str else []

if not API_ID or not API_HASH:
    logging.critical(
        "API_ID or API_HASH is missing. Please check your .env file.")
    exit(1)

logging.debug(f"Loaded API_ID: {API_ID}, Source IDs: {source_ids}")

# Keywords for source groups
group_filters = {
    (-1002409298826): ["bread"],  #source test
    (-1002383817881): [],
}

# Stop-words for source groups
group_stopwords = {
    (-1002409298826): [],
    (-1002383817881): [],
}

# Dynamic target group mapping
group_config = {
    (-1002409298826): [4537474080],  #target test
    (-1002383817881): [7753411011],  # Googlesmart to Nova
    (-1002383817881): [7497120111],  # Googlesmart to Bloom
}

# Initialize the Telegram client
logging.info("Initializing the Telegram client...")
client = TelegramClient("userbot_session", API_ID, API_HASH)
message_queue = asyncio.Queue()


# Function to get target groups for a given source group
def get_target_group_for_source(source_groups):
    """
    This function returns the target groups for a given source group.
    You can add new source-target mappings to the group_config.
    """
    if source_groups in group_config:
        return group_config[source_groups]
    else:
        return []  # Return empty list if no target group is found


# Process and forward messages
async def process_message():
    while True:
        source_id, message, target_groups = await message_queue.get()
        message_id = message.id

        logging.debug(
            f"Processing message ID {message_id} from source {source_id}.")

        # Get the name of the source group/channel
        try:
            source_entity = await client.get_entity(source_id)
            source_name = source_entity.title
        except Exception as e:
            logging.error(f"Failed to get source name for ID {source_id}: {e}")
            source_name = "Unknown Source"

        # Forward the message to the specific groups
        for group_id in target_groups:
            try:
                await client.forward_messages(group_id, message)
                logging.info(
                    f"Message ID {message_id} from '{source_name}' forwarded to group ID {group_id}."
                )
            except Exception as e:
                logging.error(
                    f"Error forwarding message to group ID {group_id} from '{source_name}': {e}"
                )

        message_queue.task_done()


# Add a new message to the queue
async def add_message_to_queue(source_id, message, target_groups):
    logging.debug(
        f"Adding message ID {message.id} to the queue for groups {target_groups}."
    )
    await message_queue.put((source_id, message, target_groups))


# Event handler for new messages


@client.on(events.NewMessage(chats=source_ids))
async def handler(event):
    message = event.message
    message_text = message.message.lower().strip() if message.message else ""
    source_id = event.chat_id

    logging.debug(
        f"New message detected in source ID {source_id}: {message_text}")

    if source_id not in source_ids:
        logging.debug(
            f"Message source {source_id} is not in the list of source_ids. Skipping."
        )
        return

    # Проверяем стоп-слова только для текущей группы-источника
    current_group_stopwords = group_stopwords.get(source_id, [])
    if current_group_stopwords and any(
            stopword.lower() in message_text
            for stopword in current_group_stopwords):
        logging.warning(
            f"Message contains a stop-word for group {source_id}. Skipping message."
        )
        return

    # Проходим по фильтрам групп
    for groups, keywords in group_filters.items():
        # Проверяем, входит ли текущая группа в конфигурацию
        if isinstance(groups, (list, tuple)):
            if source_id not in groups:
                continue
        else:
            if source_id != groups:
                continue

        # Если сообщение соответствует ключевым словам, добавляем его в очередь
        if any(keyword.lower() in message_text for keyword in keywords):
            target_groups = get_target_group_for_source(groups)
            if target_groups:
                logging.info(
                    f"Message matches filter for groups {target_groups}. Adding to queue."
                )
                await add_message_to_queue(source_id, message, target_groups)
            else:
                logging.warning(
                    f"No target groups found for source group {groups}. Skipping."
                )
        else:
            logging.debug(
                f"Message does not match filter for groups {groups}. Skipping."
            )


# Function to generate a file with group IDs
async def get_group_ids():
    logging.info("Fetching group IDs...")
    dialogs = await client.get_dialogs()
    with open("group_ids.txt", "w", encoding="utf-8") as file:
        for dialog in dialogs:
            if dialog.is_group or dialog.is_channel:
                file.write(f"Name: {dialog.name}, ID: {dialog.id}\n")
    logging.info("Group IDs have been saved to 'group_ids.txt'.")


# Main function
async def main():
    try:
        await client.start()
        logging.info("Client successfully started.")
    except Exception as e:
        logging.critical(f"Failed to start Telegram client: {e}")
        exit(1)

    await get_group_ids()
    logging.info("Starting message processing task.")
    asyncio.create_task(process_message())

    await client.run_until_disconnected()
    logging.info("Client disconnected.")


if __name__ == "__main__":
    logging.info("Running the main function...")
    asyncio.run(main())