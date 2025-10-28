from django.contrib import messages
from django.http import HttpResponse, HttpResponseRedirect
from django.shortcuts import render

from parlaminutes.forms import TranscriptSubmissionForm
from parlaminutes.models import Minutes
from parlaminutes.tasks import generate_minutes_from_files, request_transcription


# Create your views here.
def home(request):
    context = {}

    if request.method == "POST":
        copy_from = request.POST["copy_from"]
        if copy_from:
            try:
                source_minutes = Minutes.objects.get(id=copy_from)
            except Minutes.DoesNotExist:
                messages.error(request, f"No transcript found with ID {copy_from}.")
                return HttpResponseRedirect("/")

            # Create a new Minutes instance copying relevant fields
            minutes_instance = Minutes.objects.create(
                title=request.POST.get("title", source_minutes.title),
                sound_file=source_minutes.sound_file,
                example_file=request.FILES.get(
                    "example_file", source_minutes.example_file
                ),
                transcript_file=source_minutes.transcript_file,
                transcribed_text=source_minutes.transcribed_text,
                example_minutes=request.POST.get(
                    "example_minutes", source_minutes.example_minutes
                ),
                prompt=request.POST.get("prompt", source_minutes.prompt),
            )

            generate_minutes_from_files(minutes_instance=minutes_instance)

            messages.success(
                request,
                f"Transcript copied from ID {copy_from} and queued for transcription.",
            )

            return HttpResponseRedirect("/")
        else:
            form = TranscriptSubmissionForm(request.POST, request.FILES)

            if form.is_valid():
                minutes_instance = form.save()
                request_transcription(minutes_instance=minutes_instance)

                messages.success(
                    request, "Your sound file is queued for transcription."
                )

                return HttpResponseRedirect("/")

            else:
                return HttpResponse(form.errors)  # TODO handle better

    else:
        # upload sound file form
        form_to_show = TranscriptSubmissionForm()
        context["form"] = form_to_show

        # list of minutes objects
        context["minutes_list"] = Minutes.objects.all()

        return render(request, "parlaminutes/home.html", context)


def transcript(request, minutes_id):
    context = {}

    the_minutes = Minutes.objects.get(id=minutes_id)

    context["minutes"] = the_minutes

    return render(request, "parlaminutes/transcript.html", context)
