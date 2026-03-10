from django.db import models

class Story(models.Model):
    character_name = models.CharField(max_length=100)
    original_photo = models.ImageField(upload_to='uploads/')
    language = models.CharField(max_length=20)
    audio_file = models.FileField(upload_to='audio/', blank=True, null=True)
    pdf_file = models.FileField(upload_to='pdfs/', blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Story of {self.character_name} ({self.language})"

class StoryPage(models.Model):
    story = models.ForeignKey(Story, on_delete=models.CASCADE, related_name='pages')
    page_number = models.IntegerField()
    text_content = models.TextField() # This will hold the 7 lines of text
    scene_image = models.ImageField(upload_to='scenes/')

    class Meta:
        ordering = ['page_number']

    def __str__(self):
        return f"Page {self.page_number} for {self.story.character_name}"