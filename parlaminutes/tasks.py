import os
import time

from django.conf import settings
from django.core.files.base import ContentFile
from google import genai
from google.genai.types import Content, Part
from huey import crontab
from huey.contrib.djhuey import db_periodic_task, db_task
from langchain.chat_models import init_chat_model

from parlaminutes.models import Minutes
from parlaminutes.utils import get_temporary_file_path


def tprint(s, c=32):
    # Helper to print messages from within tasks using color, to make them
    # stand out in examples.
    print("\x1b[1;%sm%s\x1b[0m" % (c, s))


@db_task()
def generate_minutes(minutes_instance: Minutes) -> None:
    # if there is no sound file or transcript eject
    if minutes_instance.sound_file is None:
        raise ValueError("Can't generate minutes without a sound file.")
    if minutes_instance.transcribed_text is None:
        raise ValueError(
            "Can't generate minutes without a transcript, run `Minutes.queue_transcript_generation` first."
        )

    if not os.environ.get("GOOGLE_API_KEY", None):
        os.environ["GOOGLE_API_KEY"] = settings.GOOGLE_API_KEY

    if not os.environ.get("GOOGLE_API_KEY"):
        raise NotImplementedError(
            "We require the GOOGLE_API_KEY environment variable to be set. Please set it."
        )

    # prompt the model for the minutes
    model = init_chat_model("gemini-2.5-flash", model_provider="google_genai")
    model_response = model.invoke(minutes_instance.hydrated_prompt)
    minutes_instance.generated_minutes = model_response.content
    minutes_instance.save()


@db_task()
def generate_minutes_from_files(minutes_instance: Minutes) -> None:
    client = genai.Client()

    # Upload files - uporablja context manager za S3 kompatibilnost
    with get_temporary_file_path(minutes_instance.transcript_file) as transcript_path:
        transcript_file = client.files.upload(file=transcript_path)
        while transcript_file.state.name == "PROCESSING":
            time.sleep(2)
            transcript_file = client.files.get(name=transcript_file.name)

    if minutes_instance.example_file:
        with get_temporary_file_path(minutes_instance.example_file) as example_path:
            example_file = client.files.upload(file=example_path)
            while example_file.state.name == "PROCESSING":
                time.sleep(2)
                example_file = client.files.get(name=example_file.name)
    else:
        example_file = client.files.upload(file=settings.DEFAULT_EXAMPLE_FILE_PATH)
        while example_file.state.name == "PROCESSING":
            time.sleep(2)
            example_file = client.files.get(name=example_file.name)

    contents = [
        Content(
            role="user",
            parts=[
                Part.from_uri(
                    file_uri=transcript_file.uri, mime_type=transcript_file.mime_type
                ),
                Part.from_uri(
                    file_uri=example_file.uri, mime_type=example_file.mime_type
                ),
                Part.from_text(text=minutes_instance.prompt),
            ],
        )
    ]

    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=contents,
    )

    if response.text:
        minutes_instance.generated_minutes = response.text
        filename = f"llm_minutes_{minutes_instance.id}_{int(time.time())}.txt"
        minutes_instance.llm_minutes_file.save(
            filename, ContentFile(response.text.encode("utf-8")), save=False
        )
        minutes_instance.save()
        tprint(response.text)


@db_task()
def request_transcription(minutes_instance: Minutes) -> None:
    tipko_api = settings.TIPKO_API_INSTANCE
    # if there's no sound file, eject
    if minutes_instance.sound_file is None:
        raise ValueError("Can't transcribe without a sound file.")

    # Uporabi context manager za S3 kompatibilnost
    with get_temporary_file_path(minutes_instance.sound_file) as temp_path:
        task_id = tipko_api.upload(temp_path)
        minutes_instance.tipko_task_id = task_id
        minutes_instance.save()
        tprint("File successfully uploaded.")


@db_periodic_task(crontab(minute="*/5"))
def check_status_and_download_transcription() -> None:
    tipko_api = settings.TIPKO_API_INSTANCE
    waiting_minutes = Minutes.objects.filter(
        tipko_task_id__isnull=False,
        transcribed_text__isnull=True,
    )

    for minutes_instance in waiting_minutes:
        status_response = tipko_api.get_status(minutes_instance.tipko_task_id)
        if status_response["status"] == "done":
            tprint("checking transcription for", minutes_instance.id)
            texts = []
            for i in status_response["segments"]:
                texts.append(i.get("text", ""))
            minutes_instance.transcribed_text = "\n".join(texts)
            transcript_response = tipko_api.get_transcription_file(
                minutes_instance.tipko_task_id,
            )

            # Shrani file_content v transcript_file
            if transcript_response.status_code == 200:
                filename = f"transcript_{minutes_instance.tipko_task_id}.txt"
                minutes_instance.transcript_file.save(
                    filename,
                    ContentFile(transcript_response.content),  # content je že bytes
                    save=False,  # Ne shrani še, ker bomo klicali save() spodaj
                )

            minutes_instance.save()
            # generate_minutes(minutes_instance)
            generate_minutes_from_files(minutes_instance)
            tprint("Transcription downloaded and saved.")
