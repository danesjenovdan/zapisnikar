from django import forms

from parlaminutes.models import Minutes


class TranscriptSubmissionForm(forms.ModelForm):
    class Meta:
        model = Minutes
        fields = (
            "title",
            "sound_file",
            "example_file",
            "prompt",
        )
