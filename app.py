import streamlit as st
import requests
import time

# ============================================
# إعداد الصفحة
# ============================================
st.set_page_config(
    page_title="محول المحاضرات الصوتية", 
    page_icon="🎙", 
    layout="wide"
)

# ============================================
# دالة الاستعلام من Hugging Face
# ============================================
def query_whisper(audio_bytes, api_token):
    """تحويل الصوت إلى نص باستخدام Whisper"""
    
    API_URL = "https://api-inference.huggingface.co/models/openai/whisper-large-v3"
    headers = {"Authorization": f"Bearer {api_token}"}
    
    max_retries = 5
    
    for attempt in range(max_retries):
        try:
            response = requests.post(
                API_URL, 
                headers=headers, 
                data=audio_bytes,
                timeout=120
            )
            
            # النموذج يتحمل
            if response.status_code == 503:
                try:
                    result = response.json()
                    if "estimated_time" in result:
                        wait_time = min(result["estimated_time"], 60)
                        st.info(f"⏳ النموذج يتحمل... انتظر {wait_time:.0f} ثانية")
                        time.sleep(wait_time + 3)
                        continue
                except:
                    pass
                
                st.warning(f"محاولة {attempt + 1}/{max_retries}...")
                time.sleep(10)
                continue
            
            # نجح الطلب
            if response.status_code == 200:
                return response.json()
            
            # خطأ آخر
            if attempt < max_retries - 1:
                st.warning(f"محاولة {attempt + 1}/{max_retries}... انتظر قليلاً")
                time.sleep(8)
            
        except requests.exceptions.Timeout:
            if attempt < max_retries - 1:
                st.warning(f"انتهت المهلة... محاولة {attempt + 1}/{max_retries}")
                time.sleep(10)
            else:
                return {"error": "انتهت مهلة الانتظار. الملف قد يكون كبير جداً."}
                
        except Exception as e:
            if attempt == max_retries - 1:
                return {"error": str(e)}
            time.sleep(8)
    
    return {"error": "فشل بعد عدة محاولات"}

# ============================================
# دالة التلخيص البسيطة
# ============================================
def create_summary(text):
    """إنشاء ملخص بسيط من النص"""
    
    # تقسيم النص لجمل
    sentences = []
    for s in text.replace('؟', '.').replace('!', '.').split('.'):
        s = s.strip()
        if s and len(s) > 10:
            sentences.append(s + '.')
    
    if not sentences:
        return text
    
    # إذا النص قصير، نرجعه كامل
    if len(sentences) <= 5:
        return text
    
    # نأخذ أول 4 جمل وآخر 2 جمل
    summary_parts = []
    summary_parts.extend(sentences[:4])
    
    if len(sentences) > 10:
        summary_parts.append("\n[...تم اختصار الجزء الأوسط...]\n")
    
    summary_parts.extend(sentences[-2:])
    
    return ' '.join(summary_parts)

# ============================================
# واجهة التطبيق
# ============================================

# العنوان
st.title("🎙 محول المحاضرات الصوتية إلى ملخصات")
st.markdown("""
<div style='background: linear-gradient(90deg, #667eea 0%, #764ba2 100%); 
            padding: 1rem; border-radius: 10px; color: white; text-align: center;'>
    <h3>ارفع ملف صوتي وسأحوله إلى نص وملخص - مجاناً! 🎓</h3>
</div>
""", unsafe_allow_html=True)

st.write("")

# التحقق من API Token
api_token = st.secrets.get("HF_TOKEN", "")

if not api_token:
    st.error("❌ لم يتم العثور على HF_TOKEN في Secrets")
    st.info("""
    كيفية إضافة الـ Token:
    1. اذهب إلى Settings في Streamlit
    2. اختر Secrets
    3. أضف: HF_TOKEN = "your_token_here"
    """)
    st.stop()

# رفع الملف
st.subheader("📤 رفع الملف الصوتي")

col1, col2 = st.columns([2, 1])

with col1:
    audio_file = st.file_uploader(
        "اختر ملف صوتي للمحاضرة",
type=['mp3', 'mp4', 'wav', 'm4a', 'webm', 'flac', 'ogg'],
        help="الحد الأقصى: 25 MB"
    )

with col2:
    if audio_file:
        file_size_mb = len(audio_file.getvalue()) / (1024 * 1024)
        st.metric("حجم الملف", f"{file_size_mb:.1f} MB")
        
        if file_size_mb > 25:
            st.error("⚠️ الملف كبير جداً!")
            st.info("جرب ملف أصغر من 25 MB")

# عرض المشغل الصوتي
if audio_file:
    st.audio(audio_file)
    st.write("")
    
    # زر البدء
    if st.button("🚀 ابدأ التحويل والتلخيص", type="primary", use_container_width=True):
        
        # شريط التقدم
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        # المرحلة 1: تحويل الصوت
        status_text.text("⏳ المرحلة 1/2: تحويل الصوت إلى نص...")
        progress_bar.progress(10)
        
        try:
            audio_bytes = audio_file.getvalue()
            
            # استدعاء Whisper
            result = query_whisper(audio_bytes, api_token)
            
            progress_bar.progress(60)
            
            # معالجة النتيجة
            if "error" in result:
                st.error(f"❌ خطأ: {result['error']}")
                st.info("""
                حلول ممكنة:
                - انتظر 5 دقائق وحاول مرة أخرى
                - جرب ملف أصغر
                - تأكد من أن الملف صوتي صحيح
                """)
                st.stop()
            
            transcription_text = result.get("text", "").strip()
            
            if not transcription_text:
                st.error("❌ لم يتم التعرف على أي نص")
                st.info("تأكد من أن الملف يحتوي على كلام واضح")
                st.stop()
            
            progress_bar.progress(80)
            status_text.text("✅ تم التحويل بنجاح!")
            
            # المرحلة 2: التلخيص
            status_text.text("⏳ المرحلة 2/2: إنشاء الملخص...")
            
            summary = create_summary(transcription_text)
            
            progress_bar.progress(100)
            status_text.text("✅ اكتمل بنجاح!")
            time.sleep(1)
            progress_bar.empty()
            status_text.empty()
            
            # عرض النتائج
            st.success("🎉 تم التحويل والتلخيص بنجاح!")
            
            # النص الكامل
            with st.expander("📄 النص الكامل للمحاضرة", expanded=False):
                st.text_area(
                    "النص المستخرج:",
                    transcription_text,
                    height=300,
                    label_visibility="collapsed"
                )
            
            # الملخص
            st.subheader("📝 الملخص")
            st.info(summary)
            
            # الإحصائيات
            st.subheader("📊 الإحصائيات")
            col1, col2, col3 = st.columns(3)
            
            with col1:
                word_count = len(transcription_text.split())
                st.metric("عدد الكلمات", f"{word_count:,}")
            
            with col2:
                char_count = len(transcription_text)
                st.metric("عدد الأحرف", f"{char_count:,}")
            
            with col3:
                sentences = len([s for s in transcription_text.split('.') if s.strip()])
                st.metric("عدد الجمل", sentences)
            
            # زر التحميل
            st.subheader("💾 تحميل النتائج")
            
            full_content = f"""ملخص المحاضرة الصوتية
{'='*70}

📄 النص الكامل:
{transcription_text}

{'='*70}

📝 الملخص:
{summary}

{'='*70}

📊 الإحصائيات:
- عدد الكلمات: {word_count:,}
- عدد الأحرف: {char_count:,}
- عدد الجمل: {sentences}

{'='*70}
تم الإنشاء باستخدام: Streamlit + Hugging Face (Whisper Large V3)
"""
            
            st.download_button(
                label="📥 تحميل الملخص الكامل",
                data=full_content.encode('utf-8'),
                file_name=f"ملخص_{audio_file.name.split('.')[0]}.txt",
                mime="text/plain",
                use_container_width=True
            )
            
        except Exception as e:
            st.error(f"❌ حدث خطأ غير متوقع: {str(e)}")
st.info("حاول مرة أخرى أو جرب ملف آخر")

# الشريط الجانبي
with st.sidebar:
    st.image("https://huggingface.co/front/assets/huggingface_logo-noborder.svg", width=100)
    
    st.header("ℹ️ عن التطبيق")
    
    st.markdown("""
    ### المميزات:
    - 🎯 تحويل دقيق للصوت
    - 📝 تلخيص تلقائي
    - 💯 مجاني تماماً
    - ⚡️ سريع وسهل
    - 🔒 آمن ومحمي
    
    ### الملفات المدعومة:
    - MP3, MP4, WAV
    - M4A, WEBM, FLAC
    - OGG
    
    ### نصائح للاستخدام:
    - 📏 استخدم ملفات أقل من 25 MB
    - 🎤 تأكد من وضوح الصوت
    - ⏰ أول استخدام قد يأخذ وقت
    - 🔄 إذا فشل، حاول بعد دقائق
    """)
    
    st.divider()
    
    st.markdown("""
    ### 🔧 التقنيات المستخدمة:
    - Streamlit - واجهة التطبيق
    - Hugging Face - استضافة النماذج
    - Whisper Large V3 - تحويل الصوت
    """)
    
    st.divider()
    
    st.caption("💡 مشروع تعليمي مجاني")
    st.caption("📧 للاستفسارات والدعم")

# تذييل
st.markdown("---")
st.markdown("""
<div style='text-align: center; color: gray;'>
    <p>🎓 مشروع محول المحاضرات الصوتية | Powered by Hugging Face & Streamlit</p>
</div>
""", unsafe_allow_html=True)
