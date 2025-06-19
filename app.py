from flask import Flask, render_template, request, jsonify, send_file, redirect, url_for, session
import openai
import io
import time
from datetime import datetime
import re
import os
from werkzeug.utils import secure_filename
import time as _time
import requests
from urllib.parse import urlparse
import yt_dlp
import traceback
import concurrent.futures

UPLOAD_FOLDER = 'static/brand_logos'
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.secret_key = 'supersecretkey'  # diperlukan untuk session

# Konfigurasi NVIDIA API
openai.api_key = "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"
openai.api_base = "https://integrate.api.nvidia.com/v1"

# Data untuk dropdown
NICHES = [
    {'value': 'fashion', 'label': '👗 Fashion'},
    {'value': 'food', 'label': '🍔 Makanan'},
    {'value': 'gadget', 'label': '📱 Gadget'},
    {'value': 'cosmetic', 'label': '💄 Kosmetik'},
    {'value': 'furniture', 'label': '🪑 Furniture'},
    {'value': 'health', 'label': '💊 Kesehatan'},
    {'value': 'education', 'label': '📚 Pendidikan'},
    {'value': 'sport', 'label': '⚽ Olahraga'}
]

TONES = [
    {'value': 'funny', 'label': '😂 Lucu'},
    {'value': 'luxury', 'label': '💎 Mewah'},
    {'value': 'educational', 'label': '🎓 Edukatif'},
    {'value': 'dramatic', 'label': '🎭 Dramatis'},
    {'value': 'inspirational', 'label': '✨ Inspiratif'}
]

DURATIONS = ['8 detik', '15 detik', '30 detik', '60 detik']
ASPECT_RATIOS = ['1:1 (Square)', '9:16 (Vertical)', '16:9 (Horizontal)']
LANGUAGES = ['Indonesia', 'English', 'Jawa', 'Sunda']

def generate_with_retry(prompt, max_retries=3):
    for attempt in range(max_retries):
        try:
            response = openai.ChatCompletion.create(
                model="nvidia/llama-3.3-nemotron-super-49b-v1",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.7,
                max_tokens=1500,
                top_p=0.9
            )
            return response.choices[0].message.content.strip()
        except Exception as e:
            print(f"Attempt {attempt + 1} failed: {e}")
            if attempt == max_retries - 1:
                raise
            time.sleep(2)

def clean_formatting(text, is_caption=False):
    # Hilangkan heading markdown (###, ####, ##, #)
    text = re.sub(r"#+ ", '', text)
    text = re.sub(r"#+", '', text)
    # Hilangkan garis tabel markdown dan karakter pipe
    text = re.sub(r"\|", '', text)
    text = re.sub(r"---+", '', text)
    # Hilangkan spasi berlebih di awal/akhir baris
    text = '\n'.join(line.strip() for line in text.split('\n'))
    # Hilangkan baris kosong berlebih
    text = re.sub(r"(\n\s*){2,}", '\n\n', text)
    # Untuk caption, pisahkan hashtag ke baris baru jika memungkinkan
    if is_caption:
        # Pisahkan baris hashtag jika ada kata 'Hashtag:'
        if 'Hashtag:' in text:
            parts = text.split('Hashtag:')
            caption = parts[0].strip()
            hashtags_raw = parts[1].strip()
            # Ambil semua kata yang diawali #
            hashtags = re.findall(r'#\w+', hashtags_raw)
            # Jika tidak ada #, ambil semua kata dan tambahkan #
            if not hashtags:
                # Ambil semua kata (tanpa spasi, tanpa karakter non-alfanumerik)
                words = re.findall(r'\w+', hashtags_raw)
                hashtags = [f'#{w}' for w in words if w]
            text = caption + '\nHashtag:\n' + ' '.join(hashtags)
        elif text.count('#') > 2:
            # Pisahkan baris pertama (caption) dan sisanya hashtag
            lines = text.split('\n')
            caption_line = lines[0]
            hashtags = []
            for line in lines[1:]:
                if '#' in line:
                    hashtags += re.findall(r'#\w+', line)
            if hashtags:
                text = caption_line + '\nHashtag:\n' + ' '.join(hashtags)
        else:
            # Deteksi baris yang kemungkinan besar adalah hashtag tanpa #
            lines = text.split('\n')
            for i, line in enumerate(lines):
                if (i > 0 and len(line.split()) >= 5 and not any('#' in w for w in line.split())):
                    # Anggap ini baris hashtag tanpa #
                    words = re.findall(r'\w+', line)
                    hashtags = [f'#{w}' for w in words if w]
                    lines[i] = ' '.join(hashtags)
                    text = '\n'.join(lines)
                    break
    # Hilangkan asterisks
    text = text.replace('*', '')
    return text

def analyze_prompt(nama_produk, niche, tone, durasi, aspect_ratio, language, brand_name=None):
    analysis_prompt = f"""Analisis dan berikan rekomendasi spesifik untuk prompt video penjualan {nama_produk}:
    - Niche: {niche['label']}
    - Tone: {tone['label']}
    - Durasi: {durasi}
    - Aspect Ratio: {aspect_ratio}
    - Bahasa: {language}
    
    Berikan analisis dalam format:
    1. Target Audiens: [spesifik siapa target audiens]
    2. Key Message: [pesan utama yang harus disampaikan]
    3. Visual Elements: [elemen visual yang harus ditampilkan]
    4. Emotional Triggers: [pemicu emosi yang harus dihadirkan]
    5. Technical Recommendations: [rekomendasi teknis shooting]
    6. Story Arc: [alur cerita yang disarankan]
    """
    
    try:
        analysis = generate_with_retry(analysis_prompt)
        return clean_formatting(analysis)
    except:
        return f"""1. Target Audiens: Pengguna {niche['label'].lower()}
2. Key Message: Keunggulan {nama_produk}
3. Visual Elements: Produk, pengguna, dan setting {niche['label'].lower()}
4. Emotional Triggers: Kepuasan dan kepercayaan
5. Technical Recommendations: Lighting profesional, angle bervariasi
6. Story Arc: Problem - Solution - Benefit"""

def generate_veo_prompt(nama_produk, niche, tone, durasi, aspect_ratio, language, brand_name=None):
    prompt = f"Buatkan prompt VEO 3 untuk video marketing produk {nama_produk} niche {niche['label']} dengan tone {tone['label']}, durasi {durasi}, aspect ratio {aspect_ratio}, bahasa {language}. Jika ada, gunakan brand {brand_name}. Formatkan agar mudah dipakai untuk AI video generator."
    result = generate_with_retry(prompt)
    return clean_formatting(result)

def generate_narration(nama_produk, niche, tone, durasi, aspect_ratio, language, brand_name=None):
    prompt = f"Buatkan narasi video (voice over) untuk produk {nama_produk} niche {niche['label']} dengan tone {tone['label']}, durasi {durasi}, aspect ratio {aspect_ratio}, bahasa {language}. Jika ada, gunakan brand {brand_name}. Narasi harus menarik dan sesuai kebutuhan video marketing."
    result = generate_with_retry(prompt)
    return clean_formatting(result)

def generate_caption(nama_produk, niche, tone, durasi, aspect_ratio, language, brand_name=None):
    print('[DEBUG] generate_caption args:', nama_produk, niche, tone, durasi, aspect_ratio, language, brand_name)
    prompt = f"Buatkan caption dan hashtag untuk video promosi produk {nama_produk} niche {niche['label']} dengan tone {tone['label']}, durasi {durasi}, aspect ratio {aspect_ratio}, bahasa {language}. Jika ada, gunakan brand {brand_name}. Caption harus singkat, menarik, dan hashtag relevan untuk TikTok/IG/YT/FB."
    print('[DEBUG] Caption prompt:', prompt)
    result = generate_with_retry(prompt)
    print('[DEBUG] Caption result:', result)
    return clean_formatting(result, is_caption=True)

def generate_cta(nama_produk, niche, tone, durasi, aspect_ratio, language, brand_name=None):
    prompt = f"Buatkan call-to-action (CTA) yang kuat untuk video promosi produk {nama_produk} niche {niche['label']} dengan tone {tone['label']}, durasi {durasi}, aspect ratio {aspect_ratio}, bahasa {language}. Jika ada, gunakan brand {brand_name}. CTA harus mendorong penonton untuk membeli atau mencoba produk."
    result = generate_with_retry(prompt)
    return clean_formatting(result)

def generate_content(nama_produk, niche, tone, durasi, aspect_ratio, language, brand_name=None):
    t_total = time.time()
    def get_veo():
        return generate_veo_prompt(nama_produk, niche, tone, durasi, aspect_ratio, language, brand_name)
    def get_narration():
        return generate_narration(nama_produk, niche, tone, durasi, aspect_ratio, language, brand_name)
    def get_caption():
        return generate_caption(nama_produk, niche, tone, durasi, aspect_ratio, language, brand_name)
    def get_cta():
        return generate_cta(nama_produk, niche, tone, durasi, aspect_ratio, language, brand_name)
    try:
        with concurrent.futures.ThreadPoolExecutor() as executor:
            future_veo = executor.submit(get_veo)
            future_narration = executor.submit(get_narration)
            future_caption = executor.submit(get_caption)
            future_cta = executor.submit(get_cta)
            veo_prompt = future_veo.result()
            narration = future_narration.result()
            caption = future_caption.result()
            cta = future_cta.result()
        print(f'[LOG] TOTAL waktu generate (paralel): {time.time()-t_total:.2f} detik')
        return {
            'veo_prompt': veo_prompt,
            'narration': narration,
            'caption': caption,
            'cta': cta
        }
    except Exception as e:
        print(f"Error in parallel generate_content: {str(e)}")
        traceback.print_exc()
        raise Exception(f"Gagal generate konten secara paralel: {str(e)}")

@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        nama_produk = request.form['nama_produk']
        niche = next((item for item in NICHES if item['value'] == request.form['niche']), NICHES[0])
        tone = next((item for item in TONES if item['value'] == request.form['tone']), TONES[0])
        durasi = request.form['durasi']
        aspect_ratio = request.form['aspect_ratio']
        language = request.form['language']
        
        result = generate_content(nama_produk, niche, tone, durasi, aspect_ratio, language)
        
        return render_template('index.html', 
                             niches=NICHES,
                             tones=TONES,
                             durations=DURATIONS,
                             aspect_ratios=ASPECT_RATIOS,
                             languages=LANGUAGES,
                             result=result,
                             form_data=request.form)
    
    return render_template('index.html',
                         niches=NICHES,
                         tones=TONES,
                         durations=DURATIONS,
                         aspect_ratios=ASPECT_RATIOS,
                         languages=LANGUAGES)

@app.route('/download', methods=['POST'])
def download():
    data = request.json
    content = f"""AI PROMPTER PRO - HASIL GENERATOR PROMO VIDEO
Tanggal: {data['generated_at']}
Produk: {data['nama_produk']}

=== ANALISIS PROMPT ===
{data['analysis']}

=== PROMPT VEO 3 ===
{data['veo_prompt']}

=== NARASI VIDEO ===
{data['narration']}

=== CAPTION SOSMED ===
{data['caption']}

=== CALL-TO-ACTION ===
{data['cta']}

=== INFORMASI PROYEK ===
Niche: {data['niche_label']}
Tone: {data['tone_label']}
Durasi: {data['durasi']}
Aspect Ratio: {data['aspect_ratio']}
Bahasa: {data['language']}
"""

    mem = io.BytesIO()
    mem.write(content.encode('utf-8'))
    mem.seek(0)
    
    return send_file(
        mem,
        as_attachment=True,
        download_name=f"AI_Prompter_Pro_{data['nama_produk'].replace(' ', '_')}_{datetime.now().strftime('%Y%m%d')}.txt",
        mimetype='text/plain'
    )

@app.route('/generate', methods=['POST'])
def generate():
    try:
        nama_produk = request.form.get('nama_produk')
        brand_name = request.form.get('brand_name')
        brand_logo = request.files.get('brand_logo')
        niche_value = request.form.get('niche')
        tone_value = request.form.get('tone')
        durasi = request.form.get('durasi')
        aspect_ratio = request.form.get('aspect_ratio')
        language = request.form.get('language')

        # Simpan logo jika ada
        logo_url = None
        if brand_logo and brand_logo.filename:
            filename = secure_filename(brand_logo.filename)
            logo_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            brand_logo.save(logo_path)
            logo_url = url_for('static', filename=f'brand_logos/{filename}')

        niche = next((item for item in NICHES if item['value'] == niche_value), NICHES[0])
        tone = next((item for item in TONES if item['value'] == tone_value), TONES[0])

        # Progressive step simulation
        steps = ['veo', 'narration', 'caption', 'cta']
        result = {}
        for idx, step in enumerate(steps):
            if step == 'veo':
                result['veo_prompt'] = generate_content(nama_produk, niche, tone, durasi, aspect_ratio, language, brand_name)['veo_prompt']
            elif step == 'narration':
                result['narration'] = generate_content(nama_produk, niche, tone, durasi, aspect_ratio, language, brand_name)['narration']
            elif step == 'caption':
                result['caption'] = generate_content(nama_produk, niche, tone, durasi, aspect_ratio, language, brand_name)['caption']
            elif step == 'cta':
                result['cta'] = generate_content(nama_produk, niche, tone, durasi, aspect_ratio, language, brand_name)['cta']
        result['generated_at'] = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
        result['brand_name'] = brand_name
        result['brand_logo'] = logo_url
        return jsonify({'success': True, 'result': result})
    except Exception as e:
        print(traceback.format_exc())
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/analyze_video', methods=['POST'])
def analyze_video():
    try:
        video_url = request.form.get('video_url')
        if not video_url:
            return jsonify({'success': False, 'error': 'URL video tidak ditemukan'})
            
        result = analyze_video_url(video_url)
        if 'error' in result:
            return jsonify({'success': False, 'error': result['error']})
            
        return jsonify({'success': True, 'result': result})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

def analyze_video_url(url):
    """Analyze a video URL and return structured information"""
    # Validate supported platforms
    if not ("youtube.com" in url or "youtu.be" in url or "tiktok.com" in url):
        print('URL tidak didukung:', url)
        raise Exception('Saat ini hanya mendukung URL YouTube dan TikTok. Silakan masukkan link dari dua platform tersebut.')
    try:
        # Configure yt-dlp options
        ydl_opts = {
            'quiet': True,
            'no_warnings': True,
            'extract_flat': True,
        }
        
        # Extract video information
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            
            # Determine platform
            platform = "YouTube" if "youtube.com" in url or "youtu.be" in url else "TikTok"
            
            # Prepare video info
            video_info = {
                'title': info.get('title', ''),
                'platform': platform,
                'duration': info.get('duration', 0),
                'description': info.get('description', '')
            }
            
            # Generate analysis prompt
            analysis_prompt = f"""Analyze this {platform} video and provide a detailed breakdown:\n\nTitle: {video_info['title']}\nDuration: {video_info['duration']} seconds\nDescription: {video_info['description']}\n\nPlease analyze:\n1. Content Structure\n   - How is the video organized?\n   - What are the key sections/scenes?\n   - How is the story/narrative flow?\n\n2. Visual Elements\n   - What types of shots are used?\n   - How is the lighting and color scheme?\n   - What visual effects or transitions are present?\n\n3. Audio Elements\n   - What type of music/sound effects are used?\n   - How is the voice-over/narration style?\n   - How is the audio pacing?\n\n4. Engagement Techniques\n   - What hooks are used to grab attention?\n   - How is viewer retention maintained?\n   - What call-to-actions are used?\n\n5. Branding Elements\n   - How is the brand/product presented?\n   - What visual branding elements are used?\n   - How is brand messaging integrated?\n\n6. Recommendations\n   - What elements could be adapted for our content?\n   - What unique aspects make this video effective?\n   - What improvements could be made?\n\nPlease provide a detailed analysis that can help inform our content creation strategy."""

            # Get analysis from OpenAI
            analysis_response = generate_with_retry(analysis_prompt)
            
            return {
                'video_info': video_info,
                'analysis': analysis_response
            }
            
    except Exception as e:
        print(f"Error analyzing video (yt_dlp/OpenAI): {str(e)}")
        raise Exception(f"Gagal menganalisis video: {str(e)}")

@app.route('/generate_step', methods=['POST'])
def generate_step():
    try:
        step = request.form.get('step', '1')
        data = request.form.to_dict()
        print('DEBUG: Incoming data:', data)
        
        # Store form data in session
        if 'form_data' not in session:
            session['form_data'] = {}
        session['form_data'].update(data)
        
        if step in ['1', 'init']:
            # Analyze video reference if provided
            video_url = data.get('video_reference')
            video_analysis = None
            if video_url:
                try:
                    video_analysis = analyze_video_url(video_url)
                except Exception as e:
                    print(f"Error analyzing video: {str(e)}")
                    traceback.print_exc()
                    return jsonify({'error': f'Gagal menganalisis video: {str(e)}'})
            try:
                # Convert niche and tone from value to dict
                niche_value = data.get('niche', '')
                tone_value = data.get('tone', '')
                niche = next((item for item in NICHES if item['value'] == niche_value), {'label': niche_value, 'value': niche_value})
                tone = next((item for item in TONES if item['value'] == tone_value), {'label': tone_value, 'value': tone_value})
                # Generate content
                result = generate_content(
                    data.get('nama_produk', ''),
                    niche,
                    tone,
                    data.get('durasi', ''),
                    data.get('aspect_ratio', ''),
                    data.get('language', ''),
                    data.get('brand_name', '')
                )
            except Exception as e:
                print(f"Error generating content: {str(e)}")
                traceback.print_exc()
                return jsonify({'error': f'Gagal generate konten: {str(e)}'})
            if video_analysis:
                result['video_analysis'] = video_analysis
            print('DEBUG: Result to return:', result)
            result['success'] = True
            return jsonify(result)
        elif step in ['veo', 'narration', 'caption', 'cta']:
            # Handle per-step generation for progressive UI
            form_data = request.form.to_dict()
            print('[DEBUG] form_data caption:', form_data)
            niche = next((item for item in NICHES if item['value'] == form_data.get('niche', '')), {'label': form_data.get('niche', ''), 'value': form_data.get('niche', '')})
            tone = next((item for item in TONES if item['value'] == form_data.get('tone', '')), {'label': form_data.get('tone', ''), 'value': form_data.get('tone', '')})
            args = (
                form_data.get('nama_produk', ''),
                niche,
                tone,
                form_data.get('durasi', ''),
                form_data.get('aspect_ratio', ''),
                form_data.get('language', ''),
                form_data.get('brand_name', '')
            )
            if step == 'veo':
                result = generate_veo_prompt(*args)
                session['veo'] = result
                return jsonify({'success': True, 'result': result})
            elif step == 'narration':
                result = generate_narration(*args)
                session['narration'] = result
                return jsonify({'success': True, 'result': result})
            elif step == 'caption':
                result = generate_caption(*args)
                session['caption'] = result
                return jsonify({'success': True, 'result': result})
            elif step == 'cta':
                result = generate_cta(*args)
                session['cta'] = result
                # Gabungkan semua hasil ke all_status
                all_status = {
                    'veo': {'result': session.get('veo', '')},
                    'narration': {'result': session.get('narration', '')},
                    'caption': {'result': session.get('caption', '')},
                    'cta': {'result': result},
                    'generated_at': datetime.now().strftime("%d/%m/%Y %H:%M:%S"),
                    'brand_name': form_data.get('brand_name', ''),
                    'brand_logo': form_data.get('brand_logo', '')
                }
                return jsonify({'success': True, 'all_status': all_status})
        else:
            print('DEBUG: Invalid step:', step)
            return jsonify({'error': 'Step tidak valid.'})
    except Exception as e:
        print(f"Error in generate_step: {str(e)}")
        traceback.print_exc()
        return jsonify({'error': f'Error di server: {str(e)}'})

if __name__ == '__main__':
    app.run(debug=True)