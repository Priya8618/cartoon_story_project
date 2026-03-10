import os
import uuid
import requests
import base64
import textwrap
from django.shortcuts import render, redirect, get_object_or_404
from django.conf import settings
from django.http import HttpResponse
from .models import Story, StoryPage
from deep_translator import GoogleTranslator
from elevenlabs.client import ElevenLabs
from openai import OpenAI

from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas

# Load API clients
openai_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
eleven_client = ElevenLabs(api_key=os.getenv("ELEVENLABS_API_KEY"))
STABILITY_API_KEY = os.getenv("STABILITY_API_KEY")

def home(request):
    """Displays the homepage with the form."""
    return render(request, 'index.html')

def generate_story(request):
    """Handles the form submission and AI generation."""
    if request.method == "POST":
        char_name = request.POST.get('character_name')
        user_img = request.FILES.get('original_photo')
        lang = request.POST.get('language')

        # 1. Save Base Story Object
        story = Story.objects.create(character_name=char_name, original_photo=user_img, language=lang)
        
        # 2. Generate Story Text (8 parts, exactly 7 lines each)
        prompt = (
            f"Write a magical children's story about a brave hero named {char_name}. "
            f"The story MUST be exactly 8 paragraphs long. "
            f"Each paragraph MUST contain exactly 7 short sentences. "
            f"Separate each paragraph with a double newline."
        )
        
        response = openai_client.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "user", "content": prompt}]
        )
        
        raw_paragraphs = response.choices[0].message.content.strip().split('\n\n')
        paragraphs = [p.strip() for p in raw_paragraphs if p.strip()][:8]

        # 3. Process Each Page
        full_translated_text = ""
        user_img.seek(0)
        img_bytes = user_img.read()
        
        for i, text in enumerate(paragraphs):
            # A. Translate Text
            translator = GoogleTranslator(source='auto', target=lang)
            translated_text = translator.translate(text)
            full_translated_text += translated_text + " "

            # B. Generate Image (Fixed Syntax below)
            image_filename = f"scenes/scene_{story.id}_page_{i+1}.png"
            image_path = os.path.join(settings.MEDIA_ROOT, image_filename)
            
            response = requests.post(
                "https://api.stability.ai/v1/generation/stable-diffusion-xl-1024-v1-0/image-to-image",
                headers={
                    "Accept": "application/json",
                    "Authorization": f"Bearer {STABILITY_API_KEY}"
                },
                files={
                    "init_image": img_bytes
                },
                data={
                    "init_image_mode": "IMAGE_STRENGTH",
                    "image_strength": 0.55,
                    "text_prompts[0][text]": f"3D Pixar cartoon style, magical children's book illustration. {text[:100]}",
                    "text_prompts[0][weight]": 1,
                    "cfg_scale": 7,
                    "samples": 1,
                    "steps": 30,
                }
            )

            if response.status_code == 200:
                data = response.json()
                with open(image_path, "wb") as f:
                    f.write(base64.b64decode(data["artifacts"][0]["base64"]))
                saved_image_path = image_filename
            else:
                saved_image_path = story.original_photo.name

            # C. Save Page
            StoryPage.objects.create(
                story=story,
                page_number=i+1,
                text_content=translated_text,
                scene_image=saved_image_path
            )

        # 4. Generate Audio
        try:
            audio_generator = eleven_client.generate(
                text=full_translated_text, 
                voice="Rachel",
                model="eleven_multilingual_v2"
            )
            audio_filename = f"audio/story_{story.id}.mp3"
            audio_path = os.path.join(settings.MEDIA_ROOT, audio_filename)
            with open(audio_path, "wb") as f:
                for chunk in audio_generator:
                    f.write(chunk)
            story.audio_file = audio_filename
            story.save()
        except Exception as e:
            print(f"Audio generation failed: {e}")

        return redirect('view_storybook', story_id=story.id)
        
    return redirect('home')

def view_storybook(request, story_id):
    story = get_object_or_404(Story, id=story_id)
    pages = story.pages.all()
    return render(request, 'storybook.html', {'story': story, 'pages': pages})

def download_pdf(request, story_id):
    story = get_object_or_404(Story, id=story_id)
    pages = story.pages.all()
    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="Story_{story.id}.pdf"'
    
    p = canvas.Canvas(response, pagesize=letter)
    width, height = letter
    
    for page in pages:
        p.setFont("Helvetica-Bold", 16)
        p.drawString(50, height - 50, f"Page {page.page_number}")
        
        if page.scene_image:
            img_path = os.path.join(settings.MEDIA_ROOT, page.scene_image.name)
            if os.path.exists(img_path):
                p.drawImage(img_path, 50, height - 400, width=400, height=300)
        
        p.setFont("Helvetica", 12)
        text_obj = p.beginText(50, height - 430)
        wrapped_text = textwrap.wrap(page.text_content, width=80)
        for line in wrapped_text:
            text_obj.textLine(line)
        p.drawText(text_obj)
        p.showPage()
        
    p.save()
    return response